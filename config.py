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

# ブラウザ一式ヘッダ
#  Akamai / Incapsula 系 WAF は「ヘッダ群の総合的なブラウザらしさ」で判定するため、
#  User-Agent だけを差し替えても突破できない（Accept が特に効く）。
#  アフラック生命が手元では取得でき CI からだけ 0 件になる事象への対処。
#  Accept-Encoding は送らない（自動展開しないクライアントでの事故を避けるため）。
BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# ── 抽出期間 ──
#  v3 は date(2025,10,1) をハードコードしていたため、窓が延び続けて
#  11か月・113件が毎朝ほぼ同じ顔で並ぶ状態になっていた。
#  v4 はローリング窓にする（LOOKBACK_MONTHS で調整可能）。
LOOKBACK_MONTHS = int(os.environ.get("LOOKBACK_MONTHS", "12"))


def _months_ago(months: int, base: date | None = None) -> date:
    """base から months か月前の同日（月末調整あり）を返す。"""
    b = base or date.today()
    total = (b.year * 12 + (b.month - 1)) - months
    y, m = divmod(total, 12)
    m += 1
    # 月末調整（3/31 の3か月前は 12/31、2月は末日に丸める）
    day = b.day
    while day > 28:
        try:
            return date(y, m, day)
        except ValueError:
            day -= 1
    return date(y, m, day)


DATE_FROM = _months_ago(LOOKBACK_MONTHS)
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
