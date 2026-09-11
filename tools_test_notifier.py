"""notifier.py の不変条件テスト（実サイトにもメールサーバにも触れない）

実行: python tools_test_notifier.py
"""
import os
import sys
import tempfile
from datetime import date
from email import message_from_string
from email.header import decode_header, make_header
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notifier  # noqa: E402

TMP = tempfile.mkdtemp(prefix="notifier_test_")
notifier.DATA_DIR = TMP
notifier.SEEN_PATH = os.path.join(TMP, "seen.json")
notifier.OUTPUT_DIR = TMP
notifier.NOTIFY_MD = os.path.join(TMP, "notify.md")
notifier.NOTIFY_JSON = os.path.join(TMP, "notify.json")

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

print("12. 文面の組み立て")
subj = notifier.build_subject([new1], TODAY)
check("件名に件数と日付", "新規1件" in subj and "2026/09/11" in subj, subj)
html = notifier.build_html([dict(new1, title="<script>x</script>")])
check("HTML がエスケープされる", "<script>" not in html)
check("本文にダッシュボードURL", notifier.DASHBOARD_URL in notifier.build_text([new1]))

print("13. SMTP 未設定なら送らない")
with mock.patch.dict(os.environ, {}, clear=True):
    check("設定なし→None", notifier.smtp_config() is None)
    msg = notifier.notify([new1], {"baseline": False})
    check("未設定メッセージ", "未設定" in msg, msg)
    check("notify.md が出力される", os.path.exists(notifier.NOTIFY_MD))

print("14. SMTP 設定ありなら送る（サーバはモック）")
env = {"SMTP_HOST": "smtp.example.com", "SMTP_PORT": "465", "SMTP_USER": "u@example.com",
       "SMTP_PASSWORD": "dummy", "MAIL_TO": "a@example.com, b@example.com"}
with mock.patch.dict(os.environ, env, clear=True), \
        mock.patch("smtplib.SMTP_SSL") as fake:
    msg = notifier.notify([new1], {"baseline": False})
    server = fake.return_value.__enter__.return_value
    check("login された", server.login.called)
    check("sendmail された", server.sendmail.called)
    if server.sendmail.called:
        frm, to, raw = server.sendmail.call_args[0]
        check("宛先2件", to == ["a@example.com", "b@example.com"], to)
        parsed = message_from_string(raw)
        subj = str(make_header(decode_header(parsed["Subject"])))
        check("日本語件名が復号できる", "保険リリース" in subj, subj)
    check("送信メッセージ", "メール送信" in msg, msg)

print("15. 送信に失敗しても例外を投げない（デプロイを止めない）")
with mock.patch.dict(os.environ, env, clear=True), \
        mock.patch("smtplib.SMTP_SSL", side_effect=OSError("connection refused")):
    msg = notifier.notify([new1], {"baseline": False})
    check("失敗を戻り値で返す", "失敗" in msg, msg)

print("16. テスト送信は台帳に触れず、本線上位を【テスト送信】で送る")
before = open(notifier.SEEN_PATH, encoding="utf-8").read()
pool = [dict(new1, score=90), dict(orix2, score=80), dict(peri, score=99),
        dict(base[0], score=70), dict(base[1], score=60)]
with mock.patch.dict(os.environ, env, clear=True), \
        mock.patch("smtplib.SMTP_SSL") as fake:
    msg = notifier.send_test(pool)
    server = fake.return_value.__enter__.return_value
    raw = server.sendmail.call_args[0][2] if server.sendmail.called else ""
    subj = str(make_header(decode_header(message_from_string(raw)["Subject"]))) if raw else ""
    check("件名に【テスト送信】", subj.startswith("【テスト送信】"), subj)
    check("本線3件（周辺は除く）", "3件" in msg, msg)
check("台帳は変わらない", open(notifier.SEEN_PATH, encoding="utf-8").read() == before)
with mock.patch.dict(os.environ, {}, clear=True):
    check("Secrets 未登録なら送らない", "未登録" in notifier.send_test(pool))

print("17. 失敗内容（公開Issueに載る）からアドレスを伏せる")
import smtplib as _s
err = _s.SMTPRecipientsRefused({"a@example.com": (550, b"no such user"),
                                "b@example.com": (550, b"no such user")})
with mock.patch.dict(os.environ, env, clear=True), \
        mock.patch("smtplib.SMTP_SSL", side_effect=err):
    notifier.notify([new1], {"baseline": False})
text = open(os.path.join(TMP, "notify_error.txt"), encoding="utf-8").read()
check("宛先アドレスが残らない", "@example.com" not in text, text)
check("エラー種別は残る", "SMTPRecipientsRefused" in text, text)

print(f"\n結果: {passed} passed / {failed} failed")
sys.exit(1 if failed else 0)
