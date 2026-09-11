"""notifier.py の不変条件テスト（実サイトにも GitHub にも触れない）

実行: python tools_test_notifier.py
"""
import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notifier  # noqa: E402

TMP = tempfile.mkdtemp(prefix="notifier_test_")
notifier.DATA_DIR = TMP
notifier.SEEN_PATH = os.path.join(TMP, "seen.json")
notifier.OUTPUT_DIR = TMP
notifier.NOTIFY_MD = os.path.join(TMP, "notify.md")
notifier.NOTIFY_TITLE = os.path.join(TMP, "notify_title.txt")
notifier.NOTIFY_JSON = os.path.join(TMP, "notify.json")
notifier.TEST_MD = os.path.join(TMP, "notify_test.md")
notifier.TEST_TITLE = os.path.join(TMP, "notify_test_title.txt")

TODAY = date(2026, 9, 11)
passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  OK   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}  {detail}")


def read(p):
    return open(p, encoding="utf-8").read()


def E(company, title, url, d="2026/09/10", tier="PRODUCT", **kw):
    e = {"company": company, "title": title, "url": url, "date": d, "tier": tier,
         "score": 70, "rank_label": "A", "action_type": "販売開始",
         "focus_labels": ["一時払", "銀行窓販"], "fact_line": "テスト事実"}
    e.update(kw)
    return e


base = [
    E("太陽生命", "『長生きＭｙ介護』の販売を開始", "https://x/company/notice/pdf/a.pdf"),
    E("日本生命", "保険金据置利率等の改定について", "https://n/1.pdf"),
]
excl = [E("住友生命", "新企業CM「拡・保険」篇を放映開始", "https://s/cm.html", tier="EXCLUDE")]

print("1. 初回はベースラインのみ")
items, st = notifier.detect_new([dict(x) for x in base], [dict(x) for x in excl], TODAY)
check("通知0件", items == [], items)
check("baseline フラグ", st["baseline"] is True)
check("台帳が作成された", os.path.exists(notifier.SEEN_PATH))

print("2. 同じ内容の2回目は新規0件")
items, st = notifier.detect_new([dict(x) for x in base], [dict(x) for x in excl], TODAY)
check("新規0", st["new"] == 0 and items == [], st)

print("3. 既知の会社の新しい商品リリースは通知される")
new1 = E("日本生命", "新商品「テスト終身」の発売について", "https://n/2.pdf")
items, st = notifier.detect_new([dict(x) for x in base] + [new1], [], TODAY)
check("1件通知", len(items) == 1 and items[0]["url"] == "https://n/2.pdf", st)
check("first_seen が今日", items and items[0]["first_seen"] == "2026-09-11")

print("4. 翌日は同じものを再通知しない")
items, st = notifier.detect_new([dict(x) for x in base] + [new1], [], TODAY)
check("再通知なし", items == [], items)

print("5. 台帳に無い会社の初出はベースライン扱い")
orix = E("オリックス生命", "「新医療保険」の発売", "https://o/1.pdf")
items, st = notifier.detect_new([dict(x) for x in base] + [orix], [], TODAY)
check("通知なし", items == [], items)
check("会社初出としてカウント", st["silent_company_baseline"] == 1, st)
orix2 = E("オリックス生命", "「新がん保険」の発売", "https://o/2.pdf")
items, st = notifier.detect_new([dict(x) for x in base] + [orix, orix2], [], TODAY)
check("2件目からは通知される", len(items) == 1, st)

print("6. 日付の古い未知エントリは記録のみ（アーカイブ再掲対策）")
old = E("日本生命", "「旧商品」の発売", "https://n/old.pdf", d="2026/05/01")
items, st = notifier.detect_new([old], [], TODAY)
check("通知なし", items == [], items)
check("古い日付としてカウント", st["silent_old"] == 1, st)

print("7. URL の組み立てを直しても見出しが同じなら既知（太陽生命のケース）")
moved = E("太陽生命", "『長生きＭｙ介護』の販売を開始", "https://x/wr2/pdf/a.pdf")
items, st = notifier.detect_new([moved], [], TODAY)
check("新規扱いしない", st["new"] == 0, st)

print("8. 全角半角・括弧の揺れは同一視")
jitter = E("日本生命", "保険金据置利率等の改定について [1,344KB]", "https://n/1b.pdf")
items, st = notifier.detect_new([jitter], [], TODAY)
check("新規扱いしない", st["new"] == 0, st)

print("9. 周辺(PERIPHERAL)は既定では通知しない")
peri = E("日本生命", "マイページ新サービス開始", "https://n/p.html", tier="PERIPHERAL")
items, st = notifier.detect_new([peri], [], TODAY)
check("通知なし", items == [], items)
check("区分対象外としてカウント", st["silent_tier"] == 1, st)

print("10. 除外から本線に昇格しても新規扱いしない（辞書修正時の誤通知対策）")
promoted = dict(excl[0], tier="PRODUCT")
items, st = notifier.detect_new([promoted], [], TODAY)
check("新規扱いしない", st["new"] == 0, st)

print("11. 新着判定用の first_seen（ベースライン由来は空＝リリース日付で判定させる）")
b0 = dict(base[1])
notifier.detect_new([b0], [], TODAY)
check("ベースライン由来は空", b0.get("first_seen") == "", b0.get("first_seen"))
n0 = dict(new1)
notifier.detect_new([n0], [], TODAY)
check("観測した新規は検知日", n0.get("first_seen") == "2026-09-11", n0.get("first_seen"))
o0 = dict(orix)
notifier.detect_new([o0], [], TODAY)
check("会社初出（記録のみ）も空", o0.get("first_seen") == "", o0.get("first_seen"))
p0 = dict(peri)
notifier.detect_new([p0], [], TODAY)
check("区分対象外でも到着は観測したので検知日", p0.get("first_seen") == "2026-09-11",
      p0.get("first_seen"))

print("12. 件名と本文")
subj = notifier.build_subject([new1], TODAY)
check("件名に件数と日付", "新規1件" in subj and "2026/09/11" in subj, subj)
md = notifier.build_markdown([new1])
check("本文に原文URL", "https://n/2.pdf" in md)
check("本文にダッシュボードURL", notifier.DASHBOARD_URL in md)

print("13. 見出しの @ でメンションが飛ばない")
at = E("日本生命", "「＠nifty」ではなく @nifty と書かれたリリース", "https://n/at.pdf",
       fact_line="@someone 宛")
md = notifier.build_markdown([at])
check("本文に半角 @ が残らない", "@" not in md.replace(notifier.DASHBOARD_URL, ""), md[:200])

print("14. 新規ありの日は件名・本文を出力、0件の日は前回分を消す")
msg = notifier.notify([new1], {"baseline": False})
check("本文ファイル", os.path.exists(notifier.NOTIFY_MD), msg)
check("件名ファイル", read(notifier.NOTIFY_TITLE).startswith("【保険リリース】新規1件"))
msg = notifier.notify([], {"baseline": False})
check("0件で本文を消す", not os.path.exists(notifier.NOTIFY_MD), msg)
check("0件で件名を消す", not os.path.exists(notifier.NOTIFY_TITLE))

print("15. 大量の日は件数で切り、構造変更を疑う注記を付ける")
many = [E("日本生命", f"「商品{i}」の発売", f"https://n/m{i}.pdf") for i in range(45)]
md = notifier.build_markdown(many)
check("掲載は上限まで", md.count("### ") == notifier.MAX_ISSUE_ITEMS, md.count("### "))
check("残件数の注記", "ほか 15件" in md)
check("Issue 本文の上限内", len(md) < 65000, len(md))

print("16. テスト通知は台帳に触れず、本線上位を【テスト】で出力")
before = read(notifier.SEEN_PATH)
pool = [dict(new1, score=90), dict(orix2, score=80), dict(peri, score=99),
        dict(base[0], score=70), dict(base[1], score=60)]
msg = notifier.write_test_notify(pool)
check("件名に【テスト】", read(notifier.TEST_TITLE).startswith("【テスト】【保険リリース】"))
check("本線3件（周辺は除く）", read(notifier.TEST_MD).count("### ") == 3, msg)
check("テストである旨の注記", "これはテスト通知です" in read(notifier.TEST_MD))
check("台帳は変わらない", read(notifier.SEEN_PATH) == before)

print(f"\n結果: {passed} passed / {failed} failed")
sys.exit(1 if failed else 0)
