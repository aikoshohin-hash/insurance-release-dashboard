"""ニュース価値スコアリング & ランキングモジュール

各リリースに対して以下の観点でスコアを付与:
  - キーワード重要度（新発売 > 改定 > お知らせ）
  - 鮮度（新しいほど高スコア）
  - カテゴリ重要度（プレスリリース > ニュースリリース > お知らせ）
  - 会社規模/ブランド力
  - 商品性（一時払い関連は高評価）

スコアは 0〜100 の範囲で正規化される。
"""

import re
import logging
from datetime import date, datetime

from config import DATE_FROM

logger = logging.getLogger(__name__)


# ── スコア重み設定 ──

# キーワード重要度（出現で加点）
KEYWORD_SCORES = {
    # 最重要: 新商品関連
    "新発売": 30,
    "新商品": 30,
    "販売開始": 28,
    "発売開始": 28,
    "発売": 25,
    "販売": 22,
    "取扱開始": 25,
    "提供開始": 22,
    # 重要: 改定・変更
    "改定": 18,
    "商品改定": 20,
    "リニューアル": 20,
    "バージョンアップ": 18,
    "機能強化": 15,
    "機能拡張": 15,
    "レベルアップ": 12,
    # 一般
    "開始": 10,
    "取扱": 10,
    "仕様変更": 8,
    "名称変更": 6,
    "届出": 5,
    "予定利率": 15,
}

# 一時払い保険関連キーワード（追加加点）
ICHIJI_KEYWORDS = [
    "一時払", "一時払い", "定額年金", "変額年金",
    "外貨建", "ドル建", "豪ドル", "円建",
    "終身保険", "養老保険", "個人年金",
    "据置", "ターゲット", "定期支払",
]

# カテゴリスコア
CATEGORY_SCORES = {
    "C": 15,  # プレスリリース（最重要）
    "B": 10,  # ニュースリリース
    "A": 5,   # お知らせ
}

# 会社ブランド力（業界プレゼンス基準）
COMPANY_BRAND_SCORES = {
    "住友生命": 14,
    "日本生命": 15,
    "明治安田生命": 14,
    "メットライフ生命": 13,
    "ソニー生命": 12,
    "オリックス生命": 11,
    "三井住友海上プライマリー生命": 12,
    "ニッセイ・ウェルス生命": 10,
    "大樹生命": 9,
    "太陽生命": 9,
    "PGF生命": 8,
    "T&Dフィナンシャル生命": 8,
    "マニュライフ生命": 11,
}


def _parse_date(date_str: str) -> date | None:
    """日付文字列を date に変換"""
    if not date_str:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", date_str)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def score_recency(date_str: str) -> float:
    """鮮度スコア（0〜15）: 直近の方が高い"""
    d = _parse_date(date_str)
    if d is None:
        return 5.0  # 不明は中間値

    today = date.today()
    delta = (today - d).days

    if delta <= 7:
        return 15.0
    elif delta <= 14:
        return 13.0
    elif delta <= 30:
        return 11.0
    elif delta <= 60:
        return 8.0
    elif delta <= 90:
        return 5.0
    else:
        return 2.0


def score_keyword(title: str) -> float:
    """キーワード重要度スコア（0〜30）"""
    best = 0.0
    for kw, sc in KEYWORD_SCORES.items():
        if kw in title:
            best = max(best, sc)
    return best


def score_ichiji(title: str) -> float:
    """一時払い保険関連スコア（0〜15）"""
    count = sum(1 for kw in ICHIJI_KEYWORDS if kw in title)
    if count >= 3:
        return 15.0
    elif count == 2:
        return 12.0
    elif count == 1:
        return 8.0
    return 0.0


def score_category(category: str) -> float:
    """カテゴリスコア（0〜15）"""
    return CATEGORY_SCORES.get(category, 5.0)


def score_brand(company: str) -> float:
    """会社ブランドスコア（0〜15）"""
    return COMPANY_BRAND_SCORES.get(company, 7.0)


def estimate_popularity(entry: dict) -> int:
    """人気度推定（★1〜5）

    キーワード注目度 + カテゴリ + 会社ブランド + 一時払い関連度を
    総合的に判定して ★ 数で返す。
    """
    title = entry.get("title", "")
    score = 0.0

    # 新商品系は注目度高い
    new_product_kws = ["新発売", "新商品", "販売開始", "発売開始", "取扱開始", "提供開始"]
    if any(kw in title for kw in new_product_kws):
        score += 3.0

    # 一時払い/年金保険系は銀行窓販で注目度高い
    ichiji_count = sum(1 for kw in ICHIJI_KEYWORDS if kw in title)
    score += min(ichiji_count * 0.8, 2.0)

    # カテゴリ
    cat = entry.get("category", "")
    if cat == "C":
        score += 1.0
    elif cat == "B":
        score += 0.5

    # 会社ブランド
    brand = COMPANY_BRAND_SCORES.get(entry.get("company", ""), 7)
    score += brand / 15.0

    # ★に変換（1〜5）
    stars = min(5, max(1, round(score)))
    return stars


def compute_score(entry: dict) -> dict:
    """エントリに対して総合スコアを算出

    Returns:
        entry に以下のキーを追加:
          - score: 総合スコア（0〜100）
          - score_detail: スコア内訳
          - popularity: 人気度（★1〜5）
          - rank_label: ランクラベル（S/A/B/C/D）
    """
    title = entry.get("title", "")
    date_str = entry.get("date", "")
    category = entry.get("category", "")
    company = entry.get("company", "")

    # 各スコア算出
    s_keyword = score_keyword(title)
    s_recency = score_recency(date_str)
    s_ichiji = score_ichiji(title)
    s_category = score_category(category)
    s_brand = score_brand(company)

    # 合計（最大 100 = 30 + 15 + 15 + 15 + 15 + 10ボーナス）
    total = s_keyword + s_recency + s_ichiji + s_category + s_brand

    # ボーナス: PDF直リンクがある場合
    url = entry.get("url", "")
    if url.endswith(".pdf"):
        total += 5.0

    # 100で上限
    total = min(100.0, total)

    # ランクラベル
    if total >= 75:
        rank = "S"
    elif total >= 60:
        rank = "A"
    elif total >= 45:
        rank = "B"
    elif total >= 30:
        rank = "C"
    else:
        rank = "D"

    entry["score"] = round(total, 1)
    entry["score_detail"] = {
        "keyword": round(s_keyword, 1),
        "recency": round(s_recency, 1),
        "ichiji": round(s_ichiji, 1),
        "category": round(s_category, 1),
        "brand": round(s_brand, 1),
    }
    entry["popularity"] = estimate_popularity(entry)
    entry["rank_label"] = rank

    return entry


def score_and_rank(entries: list[dict]) -> list[dict]:
    """エントリリスト全体にスコアを付与し、スコア降順でソート"""
    scored = [compute_score(e) for e in entries]
    scored.sort(key=lambda x: x.get("score", 0), reverse=True)

    # 順位付与
    for i, e in enumerate(scored, 1):
        e["rank"] = i

    return scored


def score_categorized(categorized: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """カテゴリ別データ全体にスコアリング＆ランキングを適用"""
    result = {}
    for cat, entries in categorized.items():
        result[cat] = score_and_rank(entries)
    return result
