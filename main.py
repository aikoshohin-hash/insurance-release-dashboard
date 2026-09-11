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
from enricher import enrich_entries, format_enrich_report
from scorer import score_categorized
from analyzer import analyze_categorized
from notifier import detect_new, format_detect_report, notify
from exporter import export_categorized_excel, export_csv
from html_report import generate_html_report
from health_checker import check_health, format_health_report, save_health_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def fetch_all_categorized(
    companies: list[str] | None = None,
) -> tuple[dict[str, list[dict]], dict[str, int], dict[str, int], dict[str, list[str]], list[dict]]:
    """全社のリリースをカテゴリ別に取得・フィルタリング

    Returns:
        (
          categorized,          # {"A": [...], "B": [...], "C": [...]} 本線＋周辺
          raw_by_company,       # {会社名: 取得件数}
          filtered_by_company,  # {会社名: フィルタ後件数}
          errors_by_company,    # {会社名: [エラーメッセージ, ...]}
          excluded,             # 除外されたエントリ（理由付き。検証用に保持）
        )
    """
    if companies is None:
        companies = list(SCRAPER_MAP.keys())

    # カテゴリ別の生データ
    raw_by_cat: dict[str, list[dict]] = {"A": [], "B": [], "C": []}

    # 会社別の統計（ヘルスチェック用）
    raw_by_company:      dict[str, int]        = {}
    errors_by_company:   dict[str, list[str]]  = {}

    for key in companies:
        if key not in SCRAPER_MAP:
            logger.warning(f"不明な会社キー: {key}")
            continue

        scraper = SCRAPER_MAP[key]()
        company_cfg = COMPANIES.get(key, {})
        available_cats = company_cfg.get("pages", {}).keys()
        company_name = scraper.company_name
        raw_by_company[company_name] = 0
        errors_by_company[company_name] = []

        for cat in ("A", "B", "C"):
            if cat not in available_cats:
                continue
            try:
                entries = scraper.fetch_releases(category=cat)
                for e in entries:
                    e["category"] = cat
                raw_by_cat[cat].extend(entries)
                raw_by_company[company_name] = raw_by_company.get(company_name, 0) + len(entries)
            except Exception as e:
                msg = f"カテゴリ{cat}: {e}"
                logger.error(f"[{company_name}] {msg}")
                errors_by_company[company_name].append(msg)

    # カテゴリ別にフィルタリング（除外分も理由付きで受け取る）
    result: dict[str, list[dict]] = {}
    excluded_all: list[dict] = []
    for cat in ("A", "B", "C"):
        kept, excluded = filter_releases(raw_by_cat[cat])
        result[cat] = kept
        excluded_all.extend(excluded)
        logger.info(
            f"カテゴリ{cat}({CATEGORY_LABELS[cat]}): "
            f"{len(raw_by_cat[cat])}件 → 本線・周辺 {len(kept)}件 / 除外 {len(excluded)}件"
        )

    # 会社別フィルタ後件数を集計
    filtered_by_company: dict[str, int] = {name: 0 for name in raw_by_company}
    for entries in result.values():
        for e in entries:
            name = e.get("company", "")
            if name in filtered_by_company:
                filtered_by_company[name] += 1

    return result, raw_by_company, filtered_by_company, errors_by_company, excluded_all


def run(
    companies: list[str] | None = None,
    upload_gsheet: bool = True,
    simple_mode: bool = False,
    no_enrich_cache: bool = False,
) -> str | None:
    """メイン実行: 取得 → フィルタ → スコアリング → 分析 → Excel出力 → Google Sheets"""

    print(f"\n{'='*60}")
    print(f"  保険会社リリース自動取得ツール v3")
    print(f"  対象期間: {DATE_FROM} ～ {DATE_TO}")
    print(f"{'='*60}\n")

    # 1. 全社取得 & フィルタリング
    categorized, raw_by_company, filtered_by_company, errors_by_company, excluded = \
        fetch_all_categorized(companies)

    total = sum(len(v) for v in categorized.values())
    print(f"\n--- 抽出結果サマリー ---")
    for cat in ("A", "B", "C"):
        print(f"  カテゴリ{cat}（{CATEGORY_LABELS[cat]}）: {len(categorized[cat])}件")
    print(f"  本線・周辺 合計: {total}件 / 除外: {len(excluded)}件\n")

    # 除外の内訳（ゲートが効きすぎていないかを毎回目視できるようにする）
    if excluded:
        noise_counts: dict[str, int] = {}
        for e in excluded:
            k = e.get("noise_kind", "?")
            noise_counts[k] = noise_counts.get(k, 0) + 1
        print("  除外の内訳:")
        for k, c in sorted(noise_counts.items(), key=lambda x: -x[1])[:8]:
            print(f"    {k}: {c}件")
        print()

    # 1.5 ヘルスチェック（アラート表示）
    health_list = check_health(raw_by_company, filtered_by_company, errors_by_company)
    print(format_health_report(health_list))
    save_health_json(health_list)

    if total == 0:
        print("抽出対象なし。")
        return None

    # 2. 本文/PDF エンリッチ → スコアリング → 分析（v4）
    if not simple_mode:
        print("--- 本文エンリッチ（HTML/PDF を読んで事実を抽出） ---")
        flat = [e for entries in categorized.values() for e in entries]
        _, enrich_stats = enrich_entries(flat, use_cache=not no_enrich_cache)
        print(format_enrich_report(enrich_stats))

        print("\n--- スコアリング & 商品分析 ---")
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

        n_product = sum(1 for e in all_entries if e.get("tier") == "PRODUCT")
        n_focus   = sum(1 for e in all_entries if e.get("focus_labels"))
        print(f"  本線(商品リリース): {n_product}件 / "
              f"うち一時払・銀行窓販軸に触れるもの: {n_focus}件")

        # 上位ニュース表示
        top_entries = sorted(all_entries, key=lambda x: x.get("score", 0), reverse=True)[:5]
        if top_entries:
            print(f"\n--- TOP {len(top_entries)} ニュース ---")
            for i, e in enumerate(top_entries, 1):
                stars = "★" * e.get("popularity", 1) + "☆" * (5 - e.get("popularity", 1))
                focus = "/".join(e.get("focus_labels") or []) or "-"
                print(f"  {i}. [{e.get('rank_label', '?')}] "
                      f"スコア:{e.get('score', 0):5.1f} {stars}  軸:{focus}")
                print(f"     {e.get('company', '')} - {e.get('title', '')[:70]}")
                if e.get("fact_line"):
                    print(f"     事実: {e['fact_line'][:100]}")
                if e.get("implication"):
                    print(f"     含意: {e['implication'][:90]}")
                if e.get("comparison"):
                    print(f"     比較: {e['comparison'][:90]}")
                print()

    # 2.5 新規検知 & 通知（台帳 data/seen.json と突き合わせる）
    if not simple_mode:
        print("--- 新規検知 & 通知 ---")
        flat = [e for entries in categorized.values() for e in entries]
        new_items, detect_stats = detect_new(flat, excluded)
        print(format_detect_report(detect_stats))
        print(f"  {notify(new_items, detect_stats)}\n")

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
            excluded=excluded,
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
    parser.add_argument(
        "--no-enrich-cache", action="store_true",
        help="本文エンリッチのキャッシュを使わず全件取り直す（抽出ルール変更時に使用）",
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
            lambda: run(args.company, upload, args.simple, args.no_enrich_cache),
            args.schedule,
        )
    else:
        run(args.company, upload, args.simple, args.no_enrich_cache)


if __name__ == "__main__":
    main()
