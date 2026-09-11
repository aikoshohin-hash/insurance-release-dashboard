"""enricher.extract_facts の回帰テスト（ネットワークに触れない）

実データで誤判定した事例をそのまま固定している。抽出ルールを触ったら必ず流すこと。
ルールを変えたら enricher.EXTRACTOR_VERSION も上げる（キャッシュ済み分に反映させるため）。

実行: python tools_test_enricher.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enricher import extract_facts  # noqa: E402

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  OK   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}  {detail}")


print("1. 円建て商品を外貨建てにしない（明治安田 2026/08/27 の実例）")
f = extract_facts(
    "「円貨建・一時払養老保険」の発売について",
    "２０２６年１０月１日から、「円貨建・一時払養老保険」＜５年ごと利差配当付一時払特別養老保険"
    "（指定通貨建）＞（以下、「本商品」）を提携金融機関にて発売します。本商品は、為替の影響を"
    "受けない円貨建ての一時払特別養老保険であり… 指定通貨 円 市場価格調整 あり",
)
check("通貨は円のみ", f["currencies"] == ["円"], f["currencies"])
check("外貨建フラグなし", f["is_fx"] is False)
check("提携金融機関 → 銀行窓販", "銀行窓販" in f["channels"], f["channels"])
check("一時払", f["is_single_premium"] is True)

print("2. 豪ドルだけの商品に米ドルを付けない")
f = extract_facts("豪ドル建一時払終身保険『テスト』を発売", "本商品は豪ドル建の一時払終身保険です。")
check("豪ドルのみ", f["currencies"] == ["豪ドル"], f["currencies"])
check("外貨建", f["is_fx"] is True)

print("3. 複数外貨から選べる商品")
f = extract_facts("『みらいの恵み』を販売開始", "契約通貨は米ドル・豪ドルから通貨を選択いただけます。")
check("米ドル・豪ドル・通貨選択型", set(f["currencies"]) == {"米ドル", "豪ドル", "通貨選択型"},
      f["currencies"])
check("外貨建", f["is_fx"] is True)

print("4. 「指定通貨」だけでは外貨扱いしない（指定先が米ドルなら米ドル）")
f = extract_facts("一時払終身保険『X』を発売", "正式名称：積立利率変動型一時払終身保険（指定通貨建）"
                  " 指定通貨 米ドル")
check("米ドルのみ（通貨選択型ではない）", f["currencies"] == ["米ドル"], f["currencies"])

print("5. 利率改定表はラベルの並び順を読む")
f = extract_facts("保険金据置利率等の改定について",
                  "利率*1 現行 改定後 \n改定幅 \n保険金据置利率 \n年0.01% \n年0.60% \n+0.59pt")
check("現行→改定後（日本生命型）", f["rate_change"] and (f["rate_change"]["from"], f["rate_change"]["to"])
      == (0.01, 0.6), f["rate_change"])
f = extract_facts("年金支払開始後の予定利率（米ドル）の改定について",
                  "予定利率を以下のとおり引き上げ \n改定後 現行 \n年 2.25% 年 1.00%")
check("改定後→現行（メットライフ型）", f["rate_change"] and (f["rate_change"]["from"], f["rate_change"]["to"])
      == (1.0, 2.25), f["rate_change"])
f = extract_facts("団体年金保険一般勘定の上乗せ利率の改定について",
                  "改定前 0.95% 0.95% 0.75%\n改定後 1.10% 1.10% 1.10%")
check("行ごとのラベル（団体年金型）", f["rate_change"] and (f["rate_change"]["from"], f["rate_change"]["to"])
      == (0.95, 1.1), f["rate_change"])
f = extract_facts("すえ置金等の利率の改定について", "各利率を年 0.3％から年 0.85％へ引き上げます。")
check("文中の「AからBへ」", f["rate_change"] and f["rate_change"]["direction"] == "引き上げ",
      f["rate_change"])

print("6. 幅・範囲の記述を利率と誤認しない")
f = extract_facts("『みのり充実』を販売開始",
                  "積立利率は、据置期間および契約通貨に応じた指標金利の上下1.0％の範囲で決定します。")
check("利率なし", f["rates"] == [], f["rates"])

print("7. 取扱金融機関名の切り出し")
f = extract_facts("りそなグループ４行を通じ、『未来の布石』を販売開始",
                  "りそなグループの株式会社りそな銀行、埼玉りそな銀行、関西みらい銀行、みなと銀行で取扱います。")
check("前置きを削って社名だけ", f["banks"][:4] == ["りそな銀行", "埼玉りそな銀行", "関西みらい銀行", "みなと銀行"],
      f["banks"])

print("8. ひらがなの行名を助詞と取り違えない")
f = extract_facts("太陽生命、はばたき信用組合を通じ、『長生きＭｙ介護』の販売を開始", "")
check("はばたき信用組合", "はばたき信用組合" in f["banks"], f["banks"])
f = extract_facts("太陽生命と益田信用組合、生命保険の共同募集を開始", "")
check("「〇〇と」の前置きは切る → 益田信用組合", f["banks"] == ["益田信用組合"], f["banks"])
f = extract_facts("『X』を販売開始", "みなと銀行、あいち銀行、大光銀行で取扱います。")
check("みなと・あいち・大光", f["banks"] == ["みなと銀行", "あいち銀行", "大光銀行"], f["banks"])

print("9. 通貨名の無い「指定通貨建」は中立の印だけ残し、外貨と断定しない（NW ロングドリームNEXT）")
f = extract_facts("大和証券を通じ、『ロングドリームNEXT』を販売開始",
                  "正式名称：積立金区分型終身保険特約（確定積増型）付指定通貨建特別終身保険 "
                  "毎年、指定通貨建で一定額を一生涯受け取れます。")
check("通貨は「指定通貨」", f["currencies"] == ["指定通貨"], f["currencies"])
check("外貨建フラグは立てない", f["is_fx"] is False)

print(f"\n結果: {passed} passed / {failed} failed")
sys.exit(1 if failed else 0)
