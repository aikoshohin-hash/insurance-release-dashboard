"""本文エンリッチメント — リリース本文/PDF を読んで事実を構造化する層

v3 までは **タイトル文字列しか見ていなかった**。そのため
「サニーガーデン プライムを発売」は分かっても、
何通貨で・積立利率いくらで・どのチャネルで・いつから売るのかは
ダッシュボード上に一切現れなかった。

v4 はリリース本文（HTML）と PDF を実際に取得し、次を抽出する:

    商品名 / 商品種別 / 一時払か平準払か / 通貨 / 利率(数値) /
    販売開始日 / 販売チャネル / 取扱金融機関

抽出は正規表現＋辞書で行う。GitHub Actions 上に LLM は無く、
また毎日走る処理に外部 API 依存を持ち込みたくないため。

【公開リポジトリ前提の設計】
    このリポジトリは PUBLIC のため、他社サイトの本文全文は保存しない。
    保存するのは抽出後の構造化フィールドと、根拠として最小限の抜粋
    （利率などの数値を含む文。最大 EXCERPT_MAX 字 × EXCERPT_LIMIT 本）だけ。

【キャッシュ】
    data/enrichment.json に URL キーで蓄積し、CI から commit back する。
    同じ URL を毎日取りに行かないため、および利率の時系列比較を
    将来できるようにするため（取得日を必ず残す）。
"""

from __future__ import annotations

import json
import logging
import os
import re
import ssl
import time
from datetime import date, datetime
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

from config import BROWSER_HEADERS

logger = logging.getLogger(__name__)

PROJECT_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR      = os.path.join(PROJECT_DIR, "data")
CACHE_PATH    = os.path.join(DATA_DIR, "enrichment.json")

EXCERPT_MAX   = 120   # 抜粋1本あたりの最大文字数
EXCERPT_LIMIT = 3     # 抜粋の最大本数
BODY_LIMIT    = 60000 # 解析対象とする本文の最大文字数
TIMEOUT       = 45    # product-scout の実測に合わせる（CIは手元より遅い）
HOST_DELAY    = 1.5   # 同一ホストへの最小間隔（秒）

# WAF ブロックページの本文マーカー（掴まされた HTML を本文として保存しないため）
BLOCK_MARKERS = (
    "Pardon Our Interruption",
    "Access Denied",
    "Request unsuccessful",
    "アクセスが拒否されました",
    "しばらく時間をおいてから",
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  抽出辞書
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 商品種別（判定順が重要。長い語を先に置く）
PRODUCT_KINDS: list[tuple[str, str]] = [
    (r"一時払(い)?終身",                       "一時払終身"),
    (r"一時払(い)?養老",                       "一時払養老"),
    (r"一時払(い)?個人年金|一時払(い)?年金",   "一時払年金"),
    (r"変額個人年金|変額年金",                 "変額年金"),
    (r"変額保険|変額終身",                     "変額保険"),
    (r"定額(個人)?年金",                       "定額年金"),
    (r"個人年金",                              "個人年金"),
    (r"養老保険",                              "養老保険"),
    (r"学資保険|こども保険|子ども保険",        "学資保険"),
    (r"介護保険|認知症保険",                   "介護・認知症"),
    (r"がん保険|癌保険",                       "がん保険"),
    (r"医療保険",                              "医療保険"),
    (r"就業不能|所得補償",                     "就業不能"),
    (r"定期保険",                              "定期保険"),
    (r"終身保険",                              "終身保険"),
    (r"団体保険|団体年金",                     "団体保険"),
]

# 通貨
CURRENCIES: list[tuple[str, str]] = [
    (r"米ドル|ドル建|USドル|Ｕ?Ｓ?ドル",   "米ドル"),
    (r"豪ドル|オーストラリアドル",         "豪ドル"),
    (r"ニュージーランドドル|NZドル",       "NZドル"),
    (r"ユーロ",                            "ユーロ"),
    (r"英ポンド|ポンド建",                 "英ポンド"),
    (r"円建|円貨建|円貨",                  "円"),
    (r"指定通貨|通貨選択|複数通貨|多通貨", "通貨選択型"),
]

# 利率（種別 + 数値）
#  種別は接頭辞を任意にして「各利率」「利率」も拾う。
#  第一生命「各利率を年 0.3％から年 0.85％へ引き上げます」が
#  種別リストに無いせいで取れていなかったため（v4.1で修正）。
RATE_PATTERN = re.compile(
    r"((?:予定|積立|最低保証|据置|すえ置|据え置|上乗せ|適用|参考|目標|各種|各)?利率"
    r"|割引率|年金積立金の?利率)"
    r"[^0-9%％]{0,30}?"
    r"([0-9]{1,2}(?:\.[0-9]{1,4})?)\s*[%％]"
)

# 利率そのものではなく「幅」「範囲」を述べている箇所は利率として採らない。
#  例:「指標金利の上下1.0％の範囲で決定します」は積立利率が1.0%という意味ではない。
RATE_FALSE_CONTEXT = re.compile(r"範囲|上下|以内|程度|幅|前後|加減")

# 利率改定「年0.3％から年0.85％へ引き上げ」
RATE_CHANGE_PATTERN = re.compile(
    r"([0-9]{1,2}(?:\.[0-9]{1,4})?)\s*[%％]\s*(?:から|→|->)\s*"
    r"(?:年\s*)?([0-9]{1,2}(?:\.[0-9]{1,4})?)\s*[%％]"
)

# 利率改定の表組み。
#  ラベルの並び順は社によって逆になる:
#     メットライフ 「改定後 現行」 → 年 2.25% 年 1.00%
#     日本生命     「現行 改定後」 → 年0.01%  年0.60%
#  よって **値の位置ではなくラベルの順序を読んでから** 新旧を割り当てる。
#  （固定順で読んでいたため日本生命2件が新旧逆になっていた。v4.1で修正）
_NEW_LABELS = ("改定後", "変更後", "新利率")
_OLD_LABELS = ("現行", "改定前", "従来", "変更前", "旧利率")
_LABEL_ALT  = "|".join(_NEW_LABELS + _OLD_LABELS)
_NUM        = r"([0-9]{1,2}(?:\.[0-9]{1,4})?)\s*[%％]"

# 形1: ラベルが隣り合って並び、その後に値が2つ続く表ヘッダ形式
RATE_HEADER_PAIR = re.compile(
    rf"({_LABEL_ALT})[^0-9%％\n]{{0,10}}({_LABEL_ALT})"
    rf"[^0-9]{{0,40}}?{_NUM}[^0-9]{{0,20}}?{_NUM}"
)
# 形2: ラベルごとに行が分かれ、各行の先頭に値が来る形式
RATE_ROW_OLD = re.compile(rf"(?:{'|'.join(_OLD_LABELS)})[^\n]{{0,40}}?{_NUM}")
RATE_ROW_NEW = re.compile(rf"(?:{'|'.join(_NEW_LABELS)})[^\n]{{0,40}}?{_NUM}")

# 販売チャネル
CHANNELS: list[tuple[str, str]] = [
    (r"銀行|信用金庫|信用組合|労働金庫|窓口販売|窓販|金融機関代理店", "銀行窓販"),
    (r"証券会社|証券を通じ|証券株式会社",                            "証券"),
    (r"保険代理店|代理店チャネル|来店型",                            "代理店"),
    (r"営業職員|営業社員|ライフプランナー|生涯設計デザイナー|"
     r"ＭＹリンク|MYリンク|コンサルタント",                          "営業職員"),
    (r"インターネット|オンライン申込|Web申込|ＷＥＢ申込|ネット申込", "インターネット"),
    (r"郵便局|かんぽ",                                               "郵便局"),
]

# 取扱金融機関名
BANK_PATTERN = re.compile(
    r"([一-龥ぁ-んァ-ヶー々A-Za-z株式会社]{2,14})"
    r"(銀行|信用金庫|信用組合|労働金庫|信託銀行)"
)
# 捕捉した接頭辞から会社名だけを取り出すための削り込み
#   「グループの株式会社りそな」→「りそな」
BANK_PREFIX_SPLIT = re.compile(r"[のをはがと、。：:／/・\s]")
BANK_PREFIX_STRIP = re.compile(r"^(株式会社|グループ|各|同|当)")
# 誤検出しやすい一般語（「〜の銀行」等）
BANK_STOPWORDS = {
    "当該", "各", "同", "上記", "取扱", "提携", "地方", "都市", "本",
    "株式会社", "グループ", "当社", "他", "系", "系列", "複数",
}

# 販売開始日
SALE_START_PATTERNS = [
    re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
               r"\s*(?:から|より)\s*(?:の)?\s*(?:販売|取扱|発売|提供|お取扱)"),
    re.compile(r"(?:販売|発売|取扱)開始(?:日)?\s*[:：]?\s*"
               r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
]

# 払方
SINGLE_PREMIUM = re.compile(r"一時払")
LEVEL_PREMIUM  = re.compile(r"平準払|月払|年払|半年払|月々|毎月払")

# 商品名候補（括弧括り）
PETNAME_PATTERN = re.compile(r"[「『]([^」』]{2,40})[」』]")
# 商品名として採らない括弧内の語
PETNAME_STOPWORDS = re.compile(
    r"お知らせ|について|注意|重要|ご案内|見出し|参考|以下|注記|"
    r"正式名称|愛称|ペットネーム|株式会社|プレスリリース|"
    # PDF の定型文言（末尾の注記に必ず現れ、商品名として誤検出される）
    r"保護機構|契約のしおり|約款|募集文書|サービス業|生命保険協会|"
    r"金融庁|お問い合わせ|ご相談|注意喚起"
)


_KINDS_C   = [(re.compile(p), v) for p, v in PRODUCT_KINDS]
_CURR_C    = [(re.compile(p), v) for p, v in CURRENCIES]
_CHAN_C    = [(re.compile(p), v) for p, v in CHANNELS]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  取得
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class LegacyTLSAdapter(HTTPAdapter):
    """暗号スイート要件の緩いサーバ向けアダプタ。

    ソニー生命は SSL handshake failure を返すが、これは証明書検証の問題ではなく
    **暗号スイート要件**（product-scout での実測）。verify=False では解決せず、
    安全性だけが落ちる。SECLEVEL を下げたコンテキストで握手する。
    証明書の検証自体は有効なまま維持する。
    """

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class BodyFetcher:
    """本文取得器。ホスト単位でレート制限し、HTML/PDF を素の文字列に落とす。"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)
        self.session.mount("https://", LegacyTLSAdapter())
        self._last_by_host: dict[str, float] = {}

    def fetch(self, url: str) -> tuple[str, str]:
        """(本文テキスト, 種別) を返す。失敗時は ("", 理由)。"""
        if not url or not url.startswith("http"):
            return "", "no-url"

        host = urlparse(url).netloc
        last = self._last_by_host.get(host, 0.0)
        wait = HOST_DELAY - (time.time() - last)
        if wait > 0:
            time.sleep(wait)

        # Akamai 系は同一サイト内遷移に見えるかどうかも見るため Referer を添える
        headers = {"Referer": f"https://{host}/", "Sec-Fetch-Site": "same-origin"}

        try:
            resp = self.session.get(url, timeout=TIMEOUT, headers=headers)
            self._last_by_host[host] = time.time()
            if resp.status_code != 200:
                return "", f"http-{resp.status_code}"
        except requests.RequestException as e:
            self._last_by_host[host] = time.time()
            return "", f"error-{type(e).__name__}"

        ctype = (resp.headers.get("Content-Type") or "").lower()

        if "pdf" in ctype or url.lower().endswith(".pdf"):
            return self._pdf_text(resp.content), "pdf"
        return self._html_text(resp), "html"

    @staticmethod
    def _html_text(resp: requests.Response) -> str:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.content, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        for marker in BLOCK_MARKERS:
            if marker in text[:2000]:
                return ""
        return text[:BODY_LIMIT]

    @staticmethod
    def _pdf_text(content: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            logger.warning("pypdf 未インストール: PDF本文をスキップします")
            return ""
        import io

        try:
            reader = PdfReader(io.BytesIO(content))
            parts = []
            for page in reader.pages[:20]:      # 20ページで打ち切り
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    continue
            return "\n".join(parts)[:BODY_LIMIT]
        except Exception as e:
            logger.debug(f"PDF解析失敗: {e}")
            return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  抽出
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _clean(text: str) -> str:
    """全角空白・改行の連続をならす。"""
    t = text.replace("　", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t


def extract_facts(title: str, body: str) -> dict:
    """タイトル＋本文から構造化フィールドを抽出する。

    タイトルは常に見る（本文が取れなくてもタイトルだけで分かることは多い）。
    本文はあれば上書き・補強する。
    """
    title = title or ""
    body  = _clean(body or "")
    both  = f"{title}\n{body}"

    facts: dict = {
        "product_names":  [],
        "product_kind":   "",
        "payment":        "",
        "currencies":     [],
        "rates":          [],
        "rate_change":    None,
        "sale_start":     "",
        "channels":       [],
        "banks":          [],
        "is_single_premium": False,
        "is_bank_channel":   False,
        "is_fx":             False,
        "is_variable":       False,
        "excerpts":       [],
    }

    # ── 商品名 ──
    #  タイトルの括弧括りを最優先。タイトルに無いときだけ本文にフォールバックするが、
    #  本文の先頭には「当社」「アセットオーナー」のような無関係な括弧語が並ぶため、
    #  フォールバック時は商品名詞を含む括弧だけを商品名として認める。
    names: list[str] = []
    for m in PETNAME_PATTERN.finditer(title):
        name = m.group(1).strip()
        if len(name) >= 2 and not PETNAME_STOPWORDS.search(name) and name not in names:
            names.append(name)

    if not names:
        for m in PETNAME_PATTERN.finditer(body[:3000]):
            name = m.group(1).strip()
            if len(name) < 2 or PETNAME_STOPWORDS.search(name):
                continue
            if not re.search(r"保険|年金|共済|終身|養老|特約", name):
                continue
            if name not in names:
                names.append(name)

    facts["product_names"] = names[:4]

    # ── 商品種別 ──
    for pat, kind in _KINDS_C:
        if pat.search(both):
            facts["product_kind"] = kind
            break

    # ── 払方 ──
    if SINGLE_PREMIUM.search(both):
        facts["payment"] = "一時払"
        facts["is_single_premium"] = True
    elif LEVEL_PREMIUM.search(both):
        facts["payment"] = "平準払"

    # ── 通貨 ──
    for pat, cur in _CURR_C:
        if pat.search(both) and cur not in facts["currencies"]:
            facts["currencies"].append(cur)
    facts["is_fx"] = any(
        c in facts["currencies"] for c in ("米ドル", "豪ドル", "NZドル", "ユーロ", "英ポンド")
    ) or "通貨選択型" in facts["currencies"]

    facts["is_variable"] = bool(re.search(r"変額|特別勘定|指数連動", both))

    # ── 利率（数値。根拠の抜粋も残す） ──
    seen_rates = set()
    for m in RATE_PATTERN.finditer(both):
        kind, val = m.group(1), m.group(2)
        # 「上下1.0％の範囲で」等、幅を述べているだけの箇所は利率ではない
        if RATE_FALSE_CONTEXT.search(m.group(0)):
            continue
        try:
            fval = float(val)
        except ValueError:
            continue
        if not (0.0 < fval <= 30.0):      # 明らかな誤検出を弾く
            continue
        key = (kind, fval)
        if key in seen_rates:
            continue
        seen_rates.add(key)
        facts["rates"].append({"kind": kind, "value": fval})

        if len(facts["excerpts"]) < EXCERPT_LIMIT:
            s = max(0, m.start() - 40)
            facts["excerpts"].append(both[s:m.end() + 20].replace("\n", " ")[:EXCERPT_MAX])
    facts["rates"] = facts["rates"][:8]

    # 利率改定（旧→新）
    mc, pair = None, None

    # 形1: ラベルが隣接した表ヘッダ。先に出たラベルが先に出た値に対応する。
    m1 = RATE_HEADER_PAIR.search(both)
    if m1:
        first_label = m1.group(1)
        v1, v2 = m1.group(3), m1.group(4)
        if first_label in _NEW_LABELS:
            pair = (v2, v1)      # (旧, 新)
        else:
            pair = (v1, v2)
        mc = m1

    # 形2: 行ごとにラベルが立つ表
    if pair is None:
        mo, mn = RATE_ROW_OLD.search(both), RATE_ROW_NEW.search(both)
        if mo and mn:
            pair = (mo.group(1), mn.group(1))
            mc = mn

    # 形3: 文中の「0.3％から年0.85％へ引き上げ」
    if pair is None:
        m3 = RATE_CHANGE_PATTERN.search(both)
        if m3:
            pair = (m3.group(1), m3.group(2))
            mc = m3

    if mc and pair:
        try:
            old_v, new_v = float(pair[0]), float(pair[1])
            # 新旧が同値になるのは表の読み違いのことが多く、
            # かつ同値なら情報が無い。黙って落とす方が誤報より良い。
            if old_v != new_v and 0.0 <= old_v <= 30.0 and 0.0 < new_v <= 30.0:
                facts["rate_change"] = {
                    "from": old_v,
                    "to": new_v,
                    "direction": "引き上げ" if new_v > old_v else
                                 "引き下げ" if new_v < old_v else "据え置き",
                }
                if len(facts["excerpts"]) < EXCERPT_LIMIT:
                    s = max(0, mc.start() - 40)
                    facts["excerpts"].append(
                        both[s:mc.end() + 20].replace("\n", " ")[:EXCERPT_MAX]
                    )
        except ValueError:
            pass

    # ── 販売開始日 ──
    for pat in SALE_START_PATTERNS:
        m = pat.search(both)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                facts["sale_start"] = date(y, mo, d).strftime("%Y/%m/%d")
            except ValueError:
                pass
            break

    # ── チャネル ──
    for pat, ch in _CHAN_C:
        if pat.search(both) and ch not in facts["channels"]:
            facts["channels"].append(ch)
    facts["is_bank_channel"] = "銀行窓販" in facts["channels"]

    # ── 取扱金融機関 ──
    banks: list[str] = []
    for m in BANK_PATTERN.finditer(both):
        prefix, suffix = m.group(1), m.group(2)
        # 「グループの株式会社りそな」のような前置きを削って社名だけにする
        prefix = BANK_PREFIX_SPLIT.split(prefix)[-1]
        prefix = BANK_PREFIX_STRIP.sub("", prefix)
        if prefix in BANK_STOPWORDS or len(prefix) < 2:
            continue
        name = prefix + suffix
        if name not in banks:
            banks.append(name)
    facts["banks"] = banks[:12]

    return facts


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  キャッシュ付きエンリッチ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_cache() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"エンリッチキャッシュ読込失敗: {e}")
        return {}


def save_cache(cache: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    # キー安定ソート・非圧縮で保存（gitのdelta圧縮を効かせ、差分を読めるようにする）
    with open(CACHE_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)


def enrich_entries(
    entries: list[dict],
    max_fetch: int | None = None,
    use_cache: bool = True,
) -> tuple[list[dict], dict]:
    """エントリ群に本文由来の事実を付与する。

    Args:
        entries:   対象エントリ（本線＋周辺のみ渡すこと。ノイズは取りに行かない）
        max_fetch: 1回の実行で新規取得する上限（None=無制限）
        use_cache: data/enrichment.json を使うか

    Returns:
        (エントリ, 統計)
    """
    cache   = load_cache() if use_cache else {}
    fetcher = BodyFetcher()
    stats   = {"cached": 0, "fetched": 0, "failed": 0, "skipped": 0}
    today   = datetime.now().strftime("%Y-%m-%d")

    for e in entries:
        url = e.get("url", "")
        hit = cache.get(url) if url else None

        if hit and hit.get("facts"):
            facts = hit["facts"]
            stats["cached"] += 1
            e["enriched_at"] = hit.get("fetched_at", "")
            e["body_status"] = hit.get("body_status", "cached")
        elif max_fetch is not None and stats["fetched"] >= max_fetch:
            facts = extract_facts(e.get("title", ""), "")
            stats["skipped"] += 1
            e["enriched_at"] = ""
            e["body_status"] = "skipped"
        else:
            body, kind = fetcher.fetch(url)
            if body:
                stats["fetched"] += 1
                status = kind
            else:
                stats["failed"] += 1
                status = kind or "empty"
            facts = extract_facts(e.get("title", ""), body)
            if url:
                cache[url] = {
                    "fetched_at":  today,
                    "body_status": status,
                    "body_chars":  len(body),
                    "title":       e.get("title", ""),
                    "company":     e.get("company", ""),
                    "facts":       facts,
                }
            e["enriched_at"] = today
            e["body_status"] = status

        e["facts"] = facts

    if use_cache:
        save_cache(cache)

    return entries, stats


def format_enrich_report(stats: dict) -> str:
    return (
        f"  本文エンリッチ: キャッシュ {stats['cached']}件 / "
        f"新規取得 {stats['fetched']}件 / 取得失敗 {stats['failed']}件 / "
        f"上限スキップ {stats['skipped']}件"
    )
