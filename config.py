"""保険会社リリース取得ツール v3 - 設定

会社の追加・変更は companies.py で行ってください。
"""

import os
from datetime import datetime, date

from companies import get_companies_dict, get_company_count

# ── ディレクトリ ──
PROJECT_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")

# ── リクエスト設定 ──
REQUEST_DELAY = 1.0       # リクエスト間隔（秒）
REQUEST_TIMEOUT = 30      # タイムアウト（秒）
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ── 抽出期間 ──
DATE_FROM = date(2025, 10, 1)
DATE_TO = date.today()

# ── Google Sheets ──
SPREADSHEET_ID = "15OqmNLhP1Tq04OiDZaTpYdWIjN8JKK6n0SZuaRrj5qA"
GSHEET_CREDENTIALS = os.path.join(PROJECT_DIR, "credentials.json")

# ── GitHub Pages 連携 ──
# セットアップ後に自動設定されます
GITHUB_OWNER = "aikoshohin-hash"   # GitHubユーザー名
GITHUB_REPO = "insurance-release-dashboard"    # リポジトリ名

# ── フィルタキーワード ──
KEYWORDS_JA = ["販売", "発売", "取扱", "開始", "改定"]
KEYWORDS_EN = ["launch", "release", "start", "begin", "revise", "update"]

# 商品/サービス判定用の補助キーワード（見出しにメインキーワードが無くても抽出）
PRODUCT_KEYWORDS = [
    "保険商品", "新商品", "商品改定", "機能強化", "レベルアップ",
    "付帯サービス", "サービス開始", "サービス改定", "機能拡張",
    "仕様変更", "改善", "提供開始", "提供停止", "名称変更",
    "取扱開始", "販売開始", "発売開始",
    "新発売", "リニューアル", "バージョンアップ",
    "ペットネーム", "予定利率", "届出",
]

# ── 年度ヘルパー ──
def current_fiscal_year() -> int:
    now = datetime.now()
    return now.year if now.month >= 4 else now.year - 1


# ── カテゴリ定義 ──
CATEGORY_LABELS = {
    "A": "お知らせ",
    "B": "ニュースリリース",
    "C": "プレスリリース",
}

# ── 対象会社 ──
# ※ 会社の追加・変更は companies.py で行ってください
COMPANIES = get_companies_dict()
