"""relevance.classify の回帰テスト（実データの判定事例を固定する）

本線に入れるべきもの / 入れてはいけないものを、実際に観測した見出しで固定している。
辞書を触ったら必ず流すこと。

実行: python tools_test_relevance.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from relevance import classify, TIER_PRODUCT, TIER_PERIPHERAL, TIER_EXCLUDE  # noqa: E402

passed = failed = 0


def check(expected, title, note=""):
    global passed, failed
    r = classify(title)
    if r["tier"] == expected:
        passed += 1
        print(f"  OK   [{expected:10s}] {title[:54]}")
    else:
        failed += 1
        print(f"  FAIL [{expected:10s}→{r['tier']}] {title[:54]}\n"
              f"       理由: {r['reason']} {note}")


print("■ 本線に入れるべきもの（商品リリース）")
check(TIER_PRODUCT, "「円貨建・一時払養老保険」の発売について")
check(TIER_PRODUCT, "メットライフ生命、一時払終身保険「サニーガーデン プライム」を発売運用通貨、利率保証期間")
check(TIER_PRODUCT, "大和証券を通じ、『ロングドリームNEXT』を販売開始", "商品名詞なし・ペットネームのみ")
check(TIER_PRODUCT, "りそなグループ４行を通じ、『未来の布石』を販売開始")
check(TIER_PRODUCT, "太陽生命、株式会社東北銀行を通じ、『長生きＭｙ介護』の販売を開始")
check(TIER_PRODUCT, "「救Ｑ隊Ｃｕｂｅ」の発売等について")
check(TIER_PRODUCT, "商品改定　ラインナップを増やしリニューアル！『ハイブリッド あんしん ライフ２プラス』")
check(TIER_PRODUCT, "変額保険（有期型）『いろどる、みらい』を改定")
check(TIER_PRODUCT, "諸利率の改定について", "「利率」が商品性の裏付け")
check(TIER_PRODUCT, "保険金据置利率等の改定について")
check(TIER_PRODUCT, "『こだわり変額保険v2』で「世界分散」特別勘定をリニューアル")
check(TIER_PRODUCT, "「保険契約者代理特約」の取扱い開始のお知らせ")
check(TIER_PRODUCT, "「災害保障期間付平準定期保険（無配当）」の改定・販売再開について")

print("\n■ 本線に入れてはいけないもの（アプリ・非保険サービス）")
check(TIER_PERIPHERAL,
      "日々の“できごと・気持ち”を記録・振り返るアプリへ自分らしいウェルビーイングを育む"
      "「シアフル」のデザイン・機能を全面リニューアル～１万人の価値観データにもとづく19 種類のタイプ診断も搭載～",
      "2026-09-14 に誤って通知した実例")
check(TIER_PERIPHERAL, "マイナンバーカードを活用した新サービス「大樹らくらく手続きナビ」の開始について")
check(TIER_PERIPHERAL, "企業の経営課題を多角的に支援する、一体的な非保険ソリューションの提供を開始")
check(TIER_PERIPHERAL, "太陽生命と益田信用組合、生命保険の共同募集を開始")

print("\n■ 除外すべきもの（広報・CSR・人事・IR・災害対応）")
check(TIER_EXCLUDE, "新CM「Play,Support.『スポーツが教えてくれた』篇」の放映開始について")
check(TIER_EXCLUDE, "第37回「創作四字熟語」募集開始 ～感じたことを漢字に託す2026～")
check(TIER_EXCLUDE, "「進学応援奨学金 supported by 日本生命」2026年度の募集開始について")
check(TIER_EXCLUDE, "役員報酬制度の改定ならびに役員向け株式報酬制度の一部改定に関するお知らせ")
check(TIER_EXCLUDE, "「令和8年熊本地震」の被災者の方々に対する各種特別取扱いについて")
check(TIER_EXCLUDE, "日本生命保険相互会社によるメディカル・データ・ビジョン株式会社の株券等に対する公開買付けの開始")
check(TIER_EXCLUDE, "「ＰＧＦ生命マイページ」利用規約改定のお知らせ")
check(TIER_EXCLUDE, "『こだわり変額保険v2』の累計販売件数10万件突破のお知らせ")
check(TIER_EXCLUDE, "「ニッセイ医療費白書」の提供開始について")
check(TIER_EXCLUDE, "公式ホームページ一部リニューアルのお知らせ")
check(TIER_EXCLUDE, "明治生命館1階・2階リニューアルオープン(展示エリア拡充、カフェ設置)のお知らせ")

print(f"\n結果: {passed} passed / {failed} failed")
sys.exit(1 if failed else 0)
