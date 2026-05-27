"""対象会社マスタ - 会社の追加・変更はここだけで完結

新しい会社を追加する手順:
  1. COMPANY_LIST に辞書を追加（下記テンプレートを参照）
  2. scrapers/ に対応するスクレイパーを作成
  3. scrapers/__init__.py にインポートを追加
  → config / scorer / dashboard に自動反映されます

テンプレート:
  {
      "key":          "example",                # 英字キー（ファイル名にも使用）
      "name":         "〇〇生命",               # 表示名（日本語）
      "base_url":     "https://www.example.co.jp",
      "pages": {
          "A": ["https://www.example.co.jp/news/"],    # お知らせ
          "B": ["https://www.example.co.jp/release/"],  # ニュースリリース
          # "C": ["..."],                                # プレスリリース（あれば）
      },
      "brand_score":  10,          # ブランド力 0-15（業界プレゼンス基準）
      "scraper":      "example",   # scrapers/ 内のモジュール名（.py不要）
      "enabled":      True,        # False で一時無効化（スクレイパー未実装等）
      "notes":        "",          # 備考（SSL問題、WAFブロック等）
  },
"""

from datetime import date as _date


def _year_urls(template: str) -> list[str]:
    """年度ベースのURLを前年・当年の2件生成する。

    例: template="https://example.com/news/{year}/"
        → ["https://example.com/news/2025/", "https://example.com/news/2026/"]

    年をまたぐデータ取得漏れを防ぐため、常に前年と当年の両方を返す。
    """
    cur = _date.today().year
    return [template.format(year=cur - 1), template.format(year=cur)]


def _nendo_urls(template: str) -> list[str]:
    """日本の年度（4月始まり）ベースのURLを前年度・当年度の2件生成する。

    例: template="https://example.com/news/?nendo={year}"
    4月以降は当年度、3月以前は前年度が「現在の年度」となる。
    """
    today = _date.today()
    cur_nendo = today.year if today.month >= 4 else today.year - 1
    return [template.format(year=cur_nendo - 1), template.format(year=cur_nendo)]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  対象会社一覧（13社） - 2026/03 時点
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPANY_LIST = [
    # ── 大手生保 ──
    {
        "key":          "nissay",
        "name":         "日本生命",
        "base_url":     "https://www.nissay.co.jp",
        "pages": {
            "A": ["https://www.nissay.co.jp/kaisha/topics/"],
            "B": ["https://www.nissay.co.jp/kaisha/news/"],
        },
        "brand_score":  15,
        "scraper":      "nissay",
        "enabled":      True,
        "notes":        "JS描画サイト。内部JSON API経由で全件取得可能",
    },
    {
        "key":          "sumitomo",
        "name":         "住友生命",
        "base_url":     "https://www.sumitomolife.co.jp",
        "pages": {
            "A": ["https://www.sumitomolife.co.jp/infolist/"],
            "B": ["https://www.sumitomolife.co.jp/infolist/"],
        },
        "brand_score":  14,
        "scraper":      "sumitomo",
        "enabled":      True,
        "notes":        "サイトリニューアルでA/B統合ページ。カテゴリ別にフィルタ",
    },
    {
        "key":          "meiji-yasuda",
        "name":         "明治安田生命",
        "base_url":     "https://www.meijiyasuda.co.jp",
        "pages": {
            "A": ["https://www.meijiyasuda.co.jp/profile/news/topics/"],
            "B": _year_urls("https://www.meijiyasuda.co.jp/profile/news/release/{year}/"),
        },
        "brand_score":  14,
        "scraper":      "meiji_yasuda",
        "enabled":      True,
        "notes":        "年度別URL（前年・当年を自動取得）",
    },

    # ── 外資系 ──
    {
        "key":          "metlife",
        "name":         "メットライフ生命",
        "base_url":     "https://www.metlife.co.jp",
        "pages": {
            "A": ["https://www.metlife.co.jp/about/info/"],
            "C": ["https://www.metlife.co.jp/about/press/"],
        },
        "brand_score":  13,
        "scraper":      "metlife",
        "enabled":      True,
        "notes":        "",
    },
    {
        "key":          "manulife",
        "name":         "マニュライフ生命",
        "base_url":     "https://www.manulife.co.jp",
        "pages": {
            "A": ["https://www.manulife.co.jp/ja/individual/about/newsrelease.html"],
            "B": ["https://www.manulife.co.jp/ja/individual/about/newsrelease.html"],
        },
        "brand_score":  11,
        "scraper":      "manulife",
        "enabled":      True,
        "notes":        "Akamai WAF保護。HTTP失敗時はキャッシュ(output/manulife_cache.json)から読み込み",
    },

    # ── 銀行窓販特化 ──
    {
        "key":          "ms-primary",
        "name":         "三井住友海上プライマリー生命",
        "base_url":     "https://www.ms-primary.com",
        "pages": {
            "A": _year_urls("https://www.ms-primary.com/news/info/{year}/"),
            "B": _year_urls("https://www.ms-primary.com/news/ir/{year}/"),
        },
        "brand_score":  12,
        "scraper":      "ms_primary",
        "enabled":      True,
        "notes":        "年度別URL（前年・当年を自動取得）",
    },
    {
        "key":          "nissay-wealth",
        "name":         "ニッセイ・ウェルス生命",
        "base_url":     "https://www.nw-life.co.jp",
        "pages": {
            "A": ["https://www.nw-life.co.jp/news/info/"],
            "B": ["https://www.nw-life.co.jp/news/release/"],
        },
        "brand_score":  10,
        "scraper":      "nissay_wealth",
        "enabled":      True,
        "notes":        "",
    },
    {
        "key":          "pgf",
        "name":         "PGF生命",
        "base_url":     "https://www.pgf-life.co.jp",
        "pages": {
            "A": ["https://www.pgf-life.co.jp/is/news/NB100.do?TYPE=2"],
            "B": ["https://www.pgf-life.co.jp/is/news/NB100.do?TYPE=1"],
        },
        "brand_score":  8,
        "scraper":      "pgf",
        "enabled":      True,
        "notes":        "",
    },
    {
        "key":          "td-financial",
        "name":         "T&Dフィナンシャル生命",
        "base_url":     "https://www.tdf-life.co.jp",
        "pages": {
            "B": _nendo_urls("https://www.tdf-life.co.jp/newsrelease/index.php?nendo={year}"),
        },
        "brand_score":  8,
        "scraper":      "td_financial",
        "enabled":      True,
        "notes":        "年度別URL・nendoパラメータ（前年度・当年度を自動取得）",
    },

    # ── その他 ──
    {
        "key":          "sonylife",
        "name":         "ソニー生命",
        "base_url":     "https://www.sonylife.co.jp",
        "pages": {
            "A": ["https://www.sonylife.co.jp/info/"],
            "B": _year_urls("https://www.sonylife.co.jp/company/news/{year}/"),
        },
        "brand_score":  12,
        "scraper":      "sonylife",
        "enabled":      True,
        "notes":        "SSL問題あり。curl フォールバックで取得。年度別URL（前年・当年を自動取得）",
    },
    {
        "key":          "orix",
        "name":         "オリックス生命",
        "base_url":     "https://www.orixlife.co.jp",
        "pages": {
            "A": ["https://www.orixlife.co.jp/about/notice/"],
            "B": ["https://www.orixlife.co.jp/about/news/"],
        },
        "brand_score":  11,
        "scraper":      "orix",
        "enabled":      True,
        "notes":        "",
    },
    {
        "key":          "taiju",
        "name":         "大樹生命",
        "base_url":     "https://www.taiju-life.co.jp",
        "pages": {
            "B": ["https://www.taiju-life.co.jp/corporate/news/"],
        },
        "brand_score":  9,
        "scraper":      "taiju",
        "enabled":      True,
        "notes":        "",
    },
    {
        "key":          "taiyo",
        "name":         "太陽生命",
        "base_url":     "https://www.taiyo-seimei.co.jp",
        "pages": {
            "A": ["https://www.taiyo-seimei.co.jp/wr2/json/news.json"],
            "B": ["https://www.taiyo-seimei.co.jp/wr2/json/release.json"],
        },
        "brand_score":  9,
        "scraper":      "taiyo",
        "enabled":      True,
        "notes":        "カテゴリA(news.json)は日付なし→フィルタで除外される",
    },

    # ── 追加会社（2026/05 実装） ──
    {
        "key":          "dai-ichi",
        "name":         "第一生命",
        "base_url":     "https://www.dai-ichi-life.co.jp",
        "pages": {
            "B": ["https://www.dai-ichi-life.co.jp/company/news/"],
        },
        "brand_score":  15,
        "scraper":      "dai_ichi",
        "enabled":      True,
        "notes":        "当年: common_v2/html/news/index.html / 前年: /company/news/{year}.html",
    },
    {
        "key":          "aflac",
        "name":         "アフラック生命",
        "base_url":     "https://www.aflac.co.jp",
        "pages": {
            "B": ["https://www.aflac.co.jp/corp/profile/news/"],
        },
        "brand_score":  13,
        "scraper":      "aflac",
        "enabled":      True,
        "notes":        "年度別URL: /corp/profile/news/{year}/ (前年・当年を自動取得)",
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ヘルパー関数 - config.py / scorer.py から参照
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_enabled_companies() -> list[dict]:
    """有効な会社のリストを返す"""
    return [c for c in COMPANY_LIST if c.get("enabled", True)]


def get_companies_dict() -> dict:
    """config.py の COMPANIES 互換辞書を返す（有効な会社のみ）"""
    result = {}
    for c in get_enabled_companies():
        result[c["key"]] = {
            "name": c["name"],
            "base_url": c["base_url"],
            "pages": c["pages"],
        }
    return result


def get_brand_scores() -> dict:
    """scorer.py の COMPANY_BRAND_SCORES 互換辞書を返す（全会社）"""
    return {c["name"]: c["brand_score"] for c in COMPANY_LIST}


def get_company_names() -> list[str]:
    """有効な会社名一覧（表示用）"""
    return [c["name"] for c in get_enabled_companies()]


def get_company_count() -> int:
    """有効な会社数"""
    return len(get_enabled_companies())


def get_company_notes() -> dict:
    """備考付き会社一覧（ステータス確認用）"""
    return {
        c["name"]: {
            "enabled": c.get("enabled", True),
            "notes": c.get("notes", ""),
            "categories": list(c["pages"].keys()),
        }
        for c in COMPANY_LIST
    }


def print_company_list():
    """会社一覧をコンソール表示（デバッグ用）"""
    enabled = get_enabled_companies()
    disabled = [c for c in COMPANY_LIST if not c.get("enabled", True)]

    print(f"\n{'='*60}")
    print(f" 対象会社一覧 ({len(enabled)}社 稼働中 / {len(disabled)}社 無効)")
    print(f"{'='*60}")
    print(f"{'No':>3} {'会社名':<20} {'キー':<16} {'カテゴリ':<8} {'ブランド':>6} {'備考'}")
    print(f"{'-'*3} {'-'*20} {'-'*16} {'-'*8} {'-'*6} {'-'*20}")

    for i, c in enumerate(enabled, 1):
        cats = ",".join(sorted(c["pages"].keys()))
        notes = c.get("notes", "")
        print(f"{i:3} {c['name']:<20} {c['key']:<16} {cats:<8} {c['brand_score']:>6} {notes}")

    if disabled:
        print(f"\n--- 無効（未実装） ---")
        for c in disabled:
            print(f"  - {c['name']} ({c['key']}): {c.get('notes', '')}")

    print()


if __name__ == "__main__":
    print_company_list()
