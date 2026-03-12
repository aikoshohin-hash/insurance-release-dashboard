"""保険会社リリース取得ツール v2 - 設定"""

import os
from datetime import datetime, date

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

# ── 対象会社（13社） ──
COMPANIES = {
    "sumitomo": {
        "name": "住友生命",
        "base_url": "https://www.sumitomolife.co.jp",
        "pages": {
            "A": ["https://www.sumitomolife.co.jp/infolist/"],
            "B": ["https://www.sumitomolife.co.jp/about/newsrelease/2025.html"],
        },
    },
    "nissay": {
        "name": "日本生命",
        "base_url": "https://www.nissay.co.jp",
        "pages": {
            "A": ["https://www.nissay.co.jp/kaisha/topics/"],
            "B": ["https://www.nissay.co.jp/kaisha/news/"],
        },
    },
    "nissay-wealth": {
        "name": "ニッセイ・ウェルス生命",
        "base_url": "https://www.nw-life.co.jp",
        "pages": {
            "A": ["https://www.nw-life.co.jp/news/info/"],
            "B": ["https://www.nw-life.co.jp/news/release/"],
        },
    },
    "taiju": {
        "name": "大樹生命",
        "base_url": "https://www.taiju-life.co.jp",
        "pages": {
            "B": ["https://www.taiju-life.co.jp/corporate/news/"],
        },
    },
    "meiji-yasuda": {
        "name": "明治安田生命",
        "base_url": "https://www.meijiyasuda.co.jp",
        "pages": {
            "A": ["https://www.meijiyasuda.co.jp/profile/news/topics/"],
            "B": ["https://www.meijiyasuda.co.jp/profile/news/release/2025/"],
        },
    },
    "ms-primary": {
        "name": "三井住友海上プライマリー生命",
        "base_url": "https://www.ms-primary.com",
        "pages": {
            "A": ["https://www.ms-primary.com/news/info/2025/"],
            "B": ["https://www.ms-primary.com/news/ir/2025/"],
        },
    },
    "metlife": {
        "name": "メットライフ生命",
        "base_url": "https://www.metlife.co.jp",
        "pages": {
            "A": ["https://www.metlife.co.jp/about/info/"],
            "C": ["https://www.metlife.co.jp/about/press/"],
        },
    },
    "taiyo": {
        "name": "太陽生命",
        "base_url": "https://www.taiyo-seimei.co.jp",
        "pages": {
            "A": ["https://www.taiyo-seimei.co.jp/wr2/json/news.json"],
            "B": ["https://www.taiyo-seimei.co.jp/wr2/json/release.json"],
        },
    },
    "pgf": {
        "name": "PGF生命",
        "base_url": "https://www.pgf-life.co.jp",
        "pages": {
            "A": ["https://www.pgf-life.co.jp/is/news/NB100.do?TYPE=2"],
            "B": ["https://www.pgf-life.co.jp/is/news/NB100.do?TYPE=1"],
        },
    },
    "sonylife": {
        "name": "ソニー生命",
        "base_url": "https://www.sonylife.co.jp",
        "pages": {
            "A": ["https://www.sonylife.co.jp/info/"],
            "B": ["https://www.sonylife.co.jp/company/news/2025/"],
        },
    },
    "orix": {
        "name": "オリックス生命",
        "base_url": "https://www.orixlife.co.jp",
        "pages": {
            "A": ["https://www.orixlife.co.jp/about/notice/"],
            "B": ["https://www.orixlife.co.jp/about/news/"],
        },
    },
    "td-financial": {
        "name": "T&Dフィナンシャル生命",
        "base_url": "https://www.tdf-life.co.jp",
        "pages": {
            "B": ["https://www.tdf-life.co.jp/newsrelease/index.php?nendo=2025"],
        },
    },
    "manulife": {
        "name": "マニュライフ生命",
        "base_url": "https://www.manulife.co.jp",
        "pages": {
            "A": ["https://www.manulife.co.jp/ja/individual/about/news-list.html"],
            "B": ["https://www.manulife.co.jp/ja/individual/about/newsroom.html"],
        },
    },
}
