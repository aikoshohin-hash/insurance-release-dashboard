"""新規検知 & 通知 — 「前回までに見ていないリリース」だけを知らせる層

【なぜ台帳が要るのか】
    v3 の「新着」は *リリース日付が3日以内* という代用品だった。これだと
      ・2週間前の日付で今日サイトに載った記事は一度も新着にならない
      ・同じ記事が3日間ずっと新着として出続ける（＝毎日同じメールが届く）
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

【送信】
    SMTP の設定（環境変数）があればメールを送る。無ければ送らず、
    本文を output/notify.md に書き出すだけにする（GitHub Issue 起票用）。
    パスワード類はコードにもリポジトリにも置かない。GitHub Secrets 経由でのみ受け取る。
"""

from __future__ import annotations

import json
import logging
import os
import re
import smtplib
import ssl
import unicodedata
from datetime import date, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from html import escape

logger = logging.getLogger(__name__)

PROJECT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(PROJECT_DIR, "data")
SEEN_PATH    = os.path.join(DATA_DIR, "seen.json")
OUTPUT_DIR   = os.path.join(PROJECT_DIR, "output")
NOTIFY_MD    = os.path.join(OUTPUT_DIR, "notify.md")
NOTIFY_JSON  = os.path.join(OUTPUT_DIR, "notify.json")

FRESH_DAYS   = int(os.environ.get("NOTIFY_FRESH_DAYS", "14"))

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

    def _rec_of(e: dict) -> dict | None:
        url = e.get("url") or ""
        return (by_url.get(url) if url else None) or by_title.get(_title_key(e))

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
#  文面
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


def _one_line_facts(e: dict) -> str:
    return e.get("fact_line") or ""


def build_markdown(items: list[dict]) -> str:
    lines = [f"新規に検知したリリース {len(items)}件（スコア順）", ""]
    for e in items:
        rank  = e.get("rank_label", "-")
        focus = " ".join(f"`{x}`" for x in (e.get("focus_labels") or []))
        act   = e.get("action_type") or ""
        lines.append(f"### [{rank}] {e.get('company','')} — {e.get('title','')}")
        meta = f"{e.get('date','')} ｜ {act}" + (f" ｜ {focus}" if focus else "")
        lines.append(meta)
        if _one_line_facts(e):
            lines.append(f"- 事実: {_one_line_facts(e)}")
        if e.get("implication"):
            lines.append(f"- 含意: {e['implication']}")
        if e.get("comparison"):
            lines.append(f"- 比較: {e['comparison']}")
        if e.get("url"):
            lines.append(f"- 原文: {e['url']}")
        lines.append("")
    lines.append(f"ダッシュボード: {DASHBOARD_URL}")
    return "\n".join(lines)


def build_text(items: list[dict]) -> str:
    """プレーンテキスト版（HTML を表示しないメーラー向け）。"""
    md = build_markdown(items)
    return md.replace("### ", "■ ").replace("`", "")


_RANK_COLOR = {"S": "#c0392b", "A": "#d35400", "B": "#2c6fbb", "C": "#7f8c8d", "D": "#95a5a6"}


def build_html(items: list[dict]) -> str:
    rows = []
    for e in items:
        rank = e.get("rank_label", "-")
        color = _RANK_COLOR.get(rank, "#7f8c8d")
        badges = "".join(
            f'<span style="background:#0b7a55;color:#fff;border-radius:3px;'
            f'padding:1px 6px;margin-right:4px;font-size:12px">{escape(x)}</span>'
            for x in (e.get("focus_labels") or [])
        )
        act = e.get("action_type") or ""
        if act:
            badges = (f'<span style="background:#1f3f77;color:#fff;border-radius:3px;'
                      f'padding:1px 6px;margin-right:4px;font-size:12px">{escape(act)}</span>'
                      + badges)
        title = escape(e.get("title", ""))
        if e.get("url"):
            title = f'<a href="{escape(e["url"])}" style="color:#1a4f9c">{title}</a>'
        detail = ""
        for label, key in (("事実", "fact_line"), ("含意", "implication"), ("比較", "comparison")):
            if e.get(key):
                detail += (f'<div style="margin-top:4px;color:#333"><b>{label}:</b> '
                           f'{escape(e[key])}</div>')
        rows.append(
            f'<tr><td style="vertical-align:top;padding:10px 8px;border-bottom:1px solid #e5e7eb">'
            f'<span style="display:inline-block;min-width:22px;text-align:center;font-weight:700;'
            f'color:#fff;background:{color};border-radius:3px">{escape(rank)}</span></td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;font-size:14px">'
            f'<div style="color:#666;font-size:12px">{escape(e.get("company",""))} ｜ '
            f'{escape(e.get("date",""))}</div>'
            f'<div style="margin:3px 0;font-weight:600">{title}</div>'
            f'<div>{badges}</div>{detail}</td></tr>'
        )
    return (
        '<div style="font-family:Meiryo,\'Hiragino Sans\',sans-serif;max-width:760px">'
        f'<p style="font-size:14px">新規に検知したリリース <b>{len(items)}件</b>（スコア順）</p>'
        '<table style="border-collapse:collapse;width:100%">' + "".join(rows) + '</table>'
        f'<p style="font-size:13px;margin-top:16px">ダッシュボード: '
        f'<a href="{DASHBOARD_URL}">{DASHBOARD_URL}</a></p>'
        '<p style="font-size:11px;color:#999">このメールは GitHub Actions から自動送信されています。'
        '前回までに見たことのないリリースだけを通知します。</p></div>'
    )


def write_notify_files(items: list[dict], stats: dict) -> None:
    """通知内容を output/ に書き出す（Issue 起票・Actions サマリー・検証用）。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(NOTIFY_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {"count": len(items), "subject": build_subject(items) if items else "",
             "stats": stats},
            f, ensure_ascii=False, indent=1,
        )
    if items:
        with open(NOTIFY_MD, "w", encoding="utf-8", newline="\n") as f:
            f.write(build_markdown(items))
    elif os.path.exists(NOTIFY_MD):
        os.remove(NOTIFY_MD)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  送信
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def smtp_config() -> dict | None:
    """環境変数から SMTP 設定を読む。必須が欠けていれば None。

        SMTP_HOST      例: smtp.gmail.com
        SMTP_PORT      例: 465（SSL）/ 587（STARTTLS）。既定 465
        SMTP_USER      送信アカウント
        SMTP_PASSWORD  アプリパスワード（GitHub Secrets からのみ渡す）
        MAIL_TO        宛先。カンマ区切りで複数可
        MAIL_FROM      差出人（省略時は SMTP_USER）
    """
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    pwd  = os.environ.get("SMTP_PASSWORD", "")
    to   = [a.strip() for a in os.environ.get("MAIL_TO", "").split(",") if a.strip()]
    if not (host and user and pwd and to):
        return None
    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT", "465") or 465),
        "user": user,
        "password": pwd,
        "to": to,
        "from": os.environ.get("MAIL_FROM", "").strip() or user,
    }


def send_email(items: list[dict], cfg: dict) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = build_subject(items)
    msg["From"]    = formataddr(("保険リリース通知", cfg["from"]))
    msg["To"]      = ", ".join(cfg["to"])
    msg.attach(MIMEText(build_text(items), "plain", "utf-8"))
    msg.attach(MIMEText(build_html(items), "html", "utf-8"))

    ctx = ssl.create_default_context()
    if cfg["port"] == 465:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=ctx, timeout=30) as s:
            s.login(cfg["user"], cfg["password"])
            s.sendmail(cfg["from"], cfg["to"], msg.as_string())
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as s:
            s.starttls(context=ctx)
            s.login(cfg["user"], cfg["password"])
            s.sendmail(cfg["from"], cfg["to"], msg.as_string())


def notify(items: list[dict], stats: dict) -> str:
    """通知の実行。戻り値は結果の一行説明。

    送信に失敗しても例外を上に投げない（台帳は既に保存済みなので、
    ここで落とすとダッシュボードのデプロイまで止まってしまうため）。
    失敗は戻り値とログで知らせ、CI 側で失敗 Issue にする。
    """
    write_notify_files(items, stats)
    if not items:
        return "通知なし（新規0件）"

    cfg = smtp_config()
    if cfg is None:
        return f"メール未設定のため送信せず（新規{len(items)}件の本文は output/notify.md）"

    try:
        send_email(items, cfg)
        return f"メール送信: {len(items)}件 → {len(cfg['to'])}宛先"
    except Exception as e:
        logger.error(f"メール送信失敗: {type(e).__name__}: {e}")
        with open(os.path.join(OUTPUT_DIR, "notify_error.txt"), "w", encoding="utf-8") as f:
            f.write(f"{type(e).__name__}: {e}\n")
        return f"メール送信失敗: {type(e).__name__}"
