"""保険会社リリース自動取得ツール v3 - メインエントリポイント

v3 新機能:
  - ニュース価値スコアリング & ランキング
  - 商品分析コメンタリー（商品タイプ・アクション分類）
  - 人気度（★）推定
  - Streamlit ダッシュボード対応

使い方:
  python main.py                       # 全社取得→スコアリング→Excel出力→Google Sheets
  python main.py --no-gsheet           # Google Sheets連携なし
  python main.py --company sumitomo    # 特定会社のみ
  python main.py --schedule 09:00      # 毎日9時に自動実行
  python main.py --dashboard           # ダッシュボード起動
  python main.py --simple              # v2互換（スコアリングなし）
"""

import sys
import os
import argparse
import logging
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(__file__))

from config import COMPANIES, CATEGORY_LABELS, DATE_FROM, DATE_TO, GITHUB_OWNER, GITHUB_REPO
from scrapers import SCRAPER_MAP
from filter import filter_releases
from scorer import score_categorized
from analyzer import analyze_categorized
from exporter import export_categorized_excel, export_csv
from html_report import generate_html_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def fetch_all_categorized(
    companies: list[str] | None = None,
) -> dict[str, list[dict]]:
    """全社のリリースをカテゴリ別に取得・フィルタリング

    Returns:
        {"A": [...], "B": [...], "C": [...]}
    """
    if companies is None:
        companies = list(SCRAPER_MAP.keys())

    # カテゴリ別の生データ
    raw_by_cat: dict[str, list[dict]] = {"A": [], "B": [], "C": []}

    for key in companies:
        if key not in SCRAPER_MAP:
            logger.warning(f"不明な会社キー: {key}")
            continue

        scraper = SCRAPER_MAP[key]()
        company_cfg = COMPANIES.get(key, {})
        available_cats = company_cfg.get("pages", {}).keys()

        for cat in ("A", "B", "C"):
            if cat not in available_cats:
                continue
            try:
                entries = scraper.fetch_releases(category=cat)
                # カテゴリラベル付与
                for e in entries:
                    e["category"] = cat
                raw_by_cat[cat].extend(entries)
            except Exception as e:
                logger.error(f"[{scraper.company_name}] カテゴリ{cat} 取得エラー: {e}")

        # 取得件数表示
        total = sum(
            len(raw_by_cat[c])
            for c in ("A", "B", "C")
            if any(e.get("company") == scraper.company_name for e in raw_by_cat[c])
        )

    # カテゴリ別にフィルタリング
    result = {}
    for cat in ("A", "B", "C"):
        filtered = filter_releases(raw_by_cat[cat])
        result[cat] = filtered
        logger.info(
            f"カテゴリ{cat}({CATEGORY_LABELS[cat]}): "
            f"{len(raw_by_cat[cat])}件 → フィルタ後 {len(filtered)}件"
        )

    return result


def run(
    companies: list[str] | None = None,
    upload_gsheet: bool = True,
    simple_mode: bool = False,
) -> str | None:
    """メイン実行: 取得 → フィルタ → スコアリング → 分析 → Excel出力 → Google Sheets"""

    print(f"\n{'='*60}")
    print(f"  保険会社リリース自動取得ツール v3")
    print(f"  対象期間: {DATE_FROM} ～ {DATE_TO}")
    print(f"{'='*60}\n")

    # 1. 全社取得 & フィルタリング
    categorized = fetch_all_categorized(companies)

    total = sum(len(v) for v in categorized.values())
    print(f"\n--- 抽出結果サマリー ---")
    for cat in ("A", "B", "C"):
        print(f"  カテゴリ{cat}（{CATEGORY_LABELS[cat]}）: {len(categorized[cat])}件")
    print(f"  合計: {total}件\n")

    if total == 0:
        print("抽出対象なし。")
        return None

    # 2. スコアリング & 商品分析（v3）
    if not simple_mode:
        print("--- スコアリング & 商品分析 ---")
        categorized = score_categorized(categorized)
        categorized = analyze_categorized(categorized)

        # ランク別サマリー
        all_entries = [e for entries in categorized.values() for e in entries]
        rank_counts = {}
        for e in all_entries:
            r = e.get("rank_label", "D")
            rank_counts[r] = rank_counts.get(r, 0) + 1

        print("  ランク分布:")
        for rank in ("S", "A", "B", "C", "D"):
            cnt = rank_counts.get(rank, 0)
            if cnt > 0:
                print(f"    {rank}ランク: {cnt}件")

        # 上位ニュース表示
        top_entries = sorted(all_entries, key=lambda x: x.get("score", 0), reverse=True)[:5]
        if top_entries:
            print(f"\n--- TOP {len(top_entries)} ニュース ---")
            for i, e in enumerate(top_entries, 1):
                stars = "★" * e.get("popularity", 1) + "☆" * (5 - e.get("popularity", 1))
                print(f"  {i}. [{e.get('rank_label', '?')}] "
                      f"スコア:{e.get('score', 0):5.1f} {stars}")
                print(f"     {e.get('company', '')} - {e.get('title', '')}")
                if e.get("product_type"):
                    print(f"     商品タイプ: {e.get('product_type')}")
                if e.get("commentary"):
                    commentary = e.get("commentary", "")
                    if len(commentary) > 80:
                        commentary = commentary[:77] + "..."
                    print(f"     分析: {commentary}")
                print()

    # 3. Excel出力 (output/ と test/ の両方)
    filepath = export_categorized_excel(categorized, enhanced=not simple_mode)
    print(f"Excel出力: {filepath}")

    # testフォルダにもコピー
    import shutil
    test_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)))
    test_copy = os.path.join(test_dir, os.path.basename(filepath))
    try:
        shutil.copy2(filepath, test_copy)
        print(f"testフォルダ: {test_copy}")
    except Exception as e:
        logger.debug(f"testフォルダへのコピー失敗: {e}")

    # 3.5 HTMLレポート生成（スマホ・他PC閲覧用）
    if not simple_mode:
        html_path = generate_html_report(
            categorized,
            gh_owner=GITHUB_OWNER,
            gh_repo=GITHUB_REPO,
        )
        print(f"HTMLレポート: {html_path}")
        html_copy = os.path.join(test_dir, os.path.basename(html_path))
        try:
            shutil.copy2(html_path, html_copy)
            print(f"testフォルダ: {html_copy}")
        except Exception as e:
            logger.debug(f"HTMLコピー失敗: {e}")

    # 4. Google Sheets アップロード
    if upload_gsheet:
        try:
            from gsheet_uploader import upload_to_gsheet
            sheet_name = date.today().strftime("%Y/%m/%d")
            url = upload_to_gsheet(categorized, sheet_name)
            print(f"Google Sheets: {url}")
        except FileNotFoundError:
            print(
                "\n[INFO] Google Sheets連携: credentials.json が見つかりません。"
                "\n  サービスアカウントの認証ファイルをプロジェクトルートに配置してください。"
                "\n  → Excel出力は正常に完了しています。"
            )
        except Exception as e:
            logger.error(f"Google Sheets アップロード失敗: {e}")
            print(f"\n[WARN] Google Sheets連携失敗: {e}")
            print("  → Excel出力は正常に完了しています。")

    # 5. ダッシュボード案内
    if not simple_mode:
        print(f"\n{'='*60}")
        print("  ダッシュボードで詳細を確認できます:")
        print("  streamlit run dashboard.py")
        print(f"{'='*60}\n")

    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="保険会社リリース自動取得ツール v3",
    )
    parser.add_argument(
        "--company", nargs="+", choices=list(SCRAPER_MAP.keys()),
        help="取得対象の会社（省略時は全社）",
    )
    parser.add_argument(
        "--no-gsheet", action="store_true",
        help="Google Sheetsへのアップロードをスキップ",
    )
    parser.add_argument(
        "--schedule", metavar="HH:MM",
        help="スケジュール実行（例: 09:00）",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="対象会社一覧を表示",
    )
    parser.add_argument(
        "--simple", action="store_true",
        help="v2互換モード（スコアリング・分析なし）",
    )
    parser.add_argument(
        "--dashboard", action="store_true",
        help="Streamlit ダッシュボードを起動",
    )

    args = parser.parse_args()

    if args.list:
        print("\n対象会社一覧 (13社):")
        for key, info in COMPANIES.items():
            cats = ", ".join(info.get("pages", {}).keys())
            print(f"  {key:22s} {info['name']:20s} カテゴリ: {cats}")
        return

    if args.dashboard:
        import subprocess
        dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.py")
        print("ダッシュボードを起動します...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", dashboard_path])
        return

    upload = not args.no_gsheet

    if args.schedule:
        from scheduler import run_scheduled
        run_scheduled(
            lambda: run(args.company, upload, args.simple),
            args.schedule,
        )
    else:
        run(args.company, upload, args.simple)


if __name__ == "__main__":
    main()
