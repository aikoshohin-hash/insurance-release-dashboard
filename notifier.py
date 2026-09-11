"""新規検知 & 通知 — 「前回までに見ていないリリース」だけを知らせる層

【なぜ台帳が要るのか】
    v3 の「新着」は *リリース日付が3日以内* という代用品だった。これだと
      ・2週間前の日付で今日サイトに載った記事は一度も新着にならない
      ・同じ記事が3日間ずっと新着として出続ける（＝毎日同じ通知が届く）
    となり、通知の土台として使えない。

    そこで data/seen.json に「一度でも見たリリース」を初回検知日付きで記録し、
    CI から commit back する。台帳に無いものだけが新規。

【不変条件】（product-scout の diff_watch と同じ規律）
    1. 台帳が無い初回実行はベースライン作成のみ。通知しない。
    2. 台帳に1件も無い会社の初出もベースライン扱い。通知しない。
       （スクレイパーを直した社・新しく追加した社の過去記事が
         一斉に「新規」として押し寄せるのを防ぐ）
    3. 台帳からは削除しない。取得に失敗した日に消すと、復旧した日に
       全件が新規として再通知されるため。
    4. 同一性は URL と（会社名＋見出し）の **どちらか** が一致すれば既知とみなす。
       URL の組み立てを直した場合（太陽生命 /company/notice/ → /wr2/）に
       全件が新規化するのを防ぐため。
    5. リリース日付が FRESH_DAYS より古い未知エントリは、黙って台帳に記録するだけ。
       サイト側がアーカイブを再掲した日に古い記事が大量通知されるのを防ぐため。
    6. 除外（ノイズ）判定のエントリも台帳には記録する。
       ゲートの辞書を直して本線に昇格したときに「新規」扱いされないようにするため。

【通知の経路】
    新規があった日だけ output/notify.md（本文）と output/notify_title.txt（件名）を
    書き出し、ワークフローがそれを GitHub Issue として起票する。
    GitHub がリポジトリを Watch しているアカウントの登録メールへ通知メールを送る。

    当初は Gmail の SMTP（アプリパスワード）で直送する設計だったが、
    アプリパスワードは送信専用ではなくメールボックスの読み取りにも使え、
    漏れたときの被害が用途に比べて大きすぎるため採らなかった（2026-09-11 ユーザー判断）。
    この方式は秘密情報を一切使わない。
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from datetime import date, timedelta

logger = logging.getLogger(__name__)

PROJECT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(PROJECT_DIR, "data")
SEEN_PATH    = os.path.join(DATA_DIR, "seen.json")
OUTPUT_DIR   = os.path.join(PROJECT_DIR, "output")
NOTIFY_MD    = os.path.join(OUTPUT_DIR, "notify.md")
NOTIFY_TITLE = os.path.join(OUTPUT_DIR, "notify_title.txt")
NOTIFY_JSON  = os.path.join(OUTPUT_DIR, "notify.json")
TEST_MD      = os.path.join(OUTPUT_DIR, "notify_test.md")
TEST_TITLE   = os.path.join(OUTPUT_DIR, "notify_test_title.txt")

FRESH_DAYS   = int(os.environ.get("NOTIFY_FRESH_DAYS", "14"))

# Issue 本文の上限は 65,536 字。1件あたり 600 字程度なので余裕を見て件数で切る。
# 大量に来た日はサイト構造の変化を疑うべき日でもある。
MAX_ISSUE_ITEMS = 30

# 通知に載せる範囲。PRODUCT=商品リリースのみ / PERIPHERAL=周辺も含める
NOTIFY_TIERS = set(
    t.strip() for t in os.environ.get("NOTIFY_TIERS", "PRODUCT").split(",") if t.strip()
)

DASHBOARD_URL = os.environ.get(
    "DASHBOARD_URL",
    "https://aikoshohin-hash.github.io/insurance-release-dashboard/",
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  台帳
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _norm_title(title: str) -> str:
    """見出しの同一性判定用の正規化（全角半角・空白・記号の揺れを吸収）。"""
    t = unicodedata.normalize("NFKC", title or "")
    t = re.sub(r"\[[\d,.]+\s*[KM]B\]", "", t)          # 「[1,344KB]」等のサイズ表記
    t = re.sub(r"[\s　「」『』【】（）()\"'“”・、。！!？?～〜\-－—]", "", t)
    return t[:80]


def _title_key(entry: dict) -> str:
    return f"{entry.get('company', '')}|{_norm_title(entry.get('title', ''))}"


def load_seen() -> dict | None:
    """台帳を読む。存在しなければ None（= 初回ベースライン）。"""
    if not os.path.exists(SEEN_PATH):
        return None
    try:
        with open(SEEN_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        # 読めない台帳で走ると全件が新規になる。止めて人に知らせる方が安全。
        raise RuntimeError(f"data/seen.json が読めません: {e}") from e


def save_seen(seen: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SEEN_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(seen, f, ensure_ascii=False, indent=1, sort_keys=True)


def _parse_date(s: str) -> date | None:
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def detect_new(
    entries: list[dict],
    excluded: list[dict] | None = None,
    today: date | None = None,
) -> tuple[list[dict], dict]:
    """台帳と突き合わせて新規エントリを返し、台帳を更新して保存する。

    Args:
        entries:  本線＋周辺（スコア・分析済み）
        excluded: 除外エントリ（台帳に記録するだけで通知対象にはしない）

    Returns:
        (通知すべき新規エントリ, 統計)
    """
    today = today or date.today()
    today_s = today.strftime("%Y-%m-%d")
    fresh_from = today - timedelta(days=FRESH_DAYS)

    seen = load_seen()
    baseline = seen is None
    if baseline:
        seen = {"created_at": today_s, "by_url": {}, "by_title": {}}

    by_url   = seen.setdefault("by_url", {})
    by_title = seen.setdefault("by_title", {})

    known_companies = {v.get("company") for v in by_title.values()}

    stats = {
        "baseline": baseline, "new": 0, "notify": 0,
        "silent_old": 0, "silent_company_baseline": 0, "silent_tier": 0,
    }
    to_notify: list[dict] = []

    def _is_known(e: dict) -> bool:
        url = e.get("url") or ""
        return (url and url in by_url) or (_title_key(e) in by_title)

    def _rec_of(e: dict) -> dict | None:
        url = e.get("url") or ""
        return (by_url.get(url) if url else None) or by_title.get(_title_key(e))

    def _record(e: dict, tier: str, quiet: bool = False) -> None:
        rec = {
            "first_seen": today_s,
            "company":    e.get("company", ""),
            "date":       e.get("date", ""),
            "title":      (e.get("title") or "")[:120],
            "tier":       tier,
        }
        # 「到着を観測した」のではなく、ベースライン作成等で既存分として
        # 取り込んだだけの記録。検知日を新着判定に使ってはいけない印。
        if quiet:
            rec["baseline"] = True
        url = e.get("url") or ""
        if url:
            by_url.setdefault(url, rec)
        by_title.setdefault(_title_key(e), rec)

    # 本線・周辺
    for e in entries:
        if _is_known(e):
            rec = _rec_of(e) or {}
            # ベースライン由来の記録は検知日を持たないものとして扱う
            # （ダッシュボード側はリリース日付で新着を判定する）
            e["first_seen"] = "" if rec.get("baseline") else rec.get("first_seen", "")
            continue
        stats["new"] += 1
        tier = e.get("tier", "PRODUCT")
        company = e.get("company", "")
        d = _parse_date(e.get("date", ""))

        quiet = True
        if baseline:
            pass
        elif company not in known_companies:
            stats["silent_company_baseline"] += 1
        elif d is not None and d < fresh_from:
            stats["silent_old"] += 1
        else:
            # ここから先は「今日到着を観測した」本物の新規
            quiet = False
            if tier in NOTIFY_TIERS:
                to_notify.append(e)
            else:
                stats["silent_tier"] += 1

        e["first_seen"] = "" if quiet else today_s
        _record(e, tier, quiet=quiet)

    # 除外分は記録だけ
    for e in excluded or []:
        if not _is_known(e):
            _record(e, "EXCLUDE")

    seen["updated_at"] = today_s
    save_seen(seen)

    to_notify.sort(key=lambda x: -x.get("score", 0))
    stats["notify"] = len(to_notify)
    return to_notify, stats


def format_detect_report(stats: dict) -> str:
    if stats["baseline"]:
        return (f"  新規検知: 初回のため台帳を作成しました（{stats['new']}件を既知として登録）。"
                f"通知は次回から。")
    return (
        f"  新規検知: 未知 {stats['new']}件 → 通知 {stats['notify']}件 "
        f"（古い日付 {stats['silent_old']} / 会社初出 {stats['silent_company_baseline']} / "
        f"通知対象外の区分 {stats['silent_tier']} は記録のみ）"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  文面（GitHub Issue = GitHub が Markdown を HTML にしてメールで届ける）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_subject(items: list[dict], today: date | None = None) -> str:
    today = today or date.today()
    top = sum(1 for e in items if e.get("rank_label") in ("S", "A"))
    focus = sum(1 for e in items if e.get("focus_labels"))
    head = f"【保険リリース】新規{len(items)}件"
    tail = []
    if top:
        tail.append(f"S/A {top}件")
    if focus:
        tail.append(f"一時払・銀行窓販 {focus}件")
    return head + (f"（{' / '.join(tail)}）" if tail else "") + f" {today:%Y/%m/%d}"


def _safe(text: str) -> str:
    """Issue 本文に他社サイトの文字列をそのまま流し込むための無害化。

    「@xxx」は GitHub 上で実在ユーザーへのメンションになり、その人に通知が飛ぶ。
    リリース見出しに「@nifty」のような語が入ることがあるため全角に置き換える。
    """
    return (text or "").replace("@", "＠")


def build_markdown(items: list[dict]) -> str:
    shown = items[:MAX_ISSUE_ITEMS]
    lines = [f"新規に検知した商品リリース **{len(items)}件**（スコア順）", ""]
    for e in shown:
        rank  = e.get("rank_label", "-")
        focus = " ".join(f"`{x}`" for x in (e.get("focus_labels") or []))
        act   = e.get("action_type") or ""
        lines.append(f"### [{rank}] {_safe(e.get('company',''))} — {_safe(e.get('title',''))}")
        meta = f"{e.get('date','')} ｜ {act}" + (f" ｜ {focus}" if focus else "")
        lines.append(meta)
        lines.append("")
        if e.get("fact_line"):
            lines.append(f"- **事実**: {_safe(e['fact_line'])}")
        if e.get("implication"):
            lines.append(f"- **含意**: {_safe(e['implication'])}")
        if e.get("comparison"):
            lines.append(f"- **比較**: {_safe(e['comparison'])}")
        if e.get("url"):
            lines.append(f"- 原文: {e['url']}")
        lines.append("")
    if len(items) > len(shown):
        lines.append(f"ほか {len(items) - len(shown)}件はダッシュボードで確認してください。"
                     "一度にこれだけ来た日は、サイト側の構造変更も疑ってください。")
        lines.append("")
    lines.append(f"ダッシュボード: {DASHBOARD_URL}")
    lines.append("")
    lines.append("<sub>GitHub Actions が自動起票。前回までに見たことのないリリースだけを通知します。"
                 "読んだら Close してください。</sub>")
    return "\n".join(lines)


def build_text(items: list[dict]) -> str:
    """プレーンテキスト版（ログ・確認用）。"""
    return build_markdown(items).replace("### ", "■ ").replace("`", "").replace("**", "")


def _write(path: str, text: str) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _remove(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


def notify(items: list[dict], stats: dict) -> str:
    """新規があれば Issue 起票用の件名・本文を output/ に書き出す。

    実際の起票はワークフローの gh issue create が行う（GITHUB_TOKEN のみで完結）。
    新規0件の日は前回の出力を消しておく（古い本文で誤って起票しないため）。
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(NOTIFY_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {"count": len(items), "subject": build_subject(items) if items else "",
             "stats": stats},
            f, ensure_ascii=False, indent=1,
        )
    if not items:
        _remove(NOTIFY_MD)
        _remove(NOTIFY_TITLE)
        return "通知なし（新規0件）"
    _write(NOTIFY_MD, build_markdown(items))
    _write(NOTIFY_TITLE, build_subject(items))
    return f"Issue 起票用に出力: 新規{len(items)}件（output/notify.md）"


def write_test_notify(entries: list[dict], n: int = 3) -> str:
    """通知経路の疎通確認用。台帳には触れず、現在の本線上位 n 件を【テスト】として出力する。

    台帳に全件が既知として載っている状態では手動実行しても新規0件になり、
    実際に通知メールが届くかを確かめる手段が無いため。
    """
    sample = sorted(
        [e for e in entries if e.get("tier") == "PRODUCT"],
        key=lambda x: -x.get("score", 0),
    )[:n]
    if not sample:
        return "テスト通知: 材料（本線のリリース）が0件"
    _write(TEST_MD, "> **これはテスト通知です。** 通知経路の確認のため、"
                    "現在の上位を新規扱いで流しています（台帳は変わりません）。\n\n"
                    + build_markdown(sample))
    _write(TEST_TITLE, "【テスト】" + build_subject(sample))
    return f"テスト通知: {len(sample)}件を output/notify_test.md に出力"
