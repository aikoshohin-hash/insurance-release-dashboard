"""リリース抽出フィルタリングモジュール"""

import re
from datetime import date, datetime

from config import KEYWORDS_JA, KEYWORDS_EN, PRODUCT_KEYWORDS, DATE_FROM, DATE_TO


def parse_date(date_str: str) -> date | None:
    """様々な日付形式を date オブジェクトに変換"""
    if not date_str:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue

    # "2025年10月1日" 形式
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", date_str)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def is_in_date_range(
    date_str: str,
    date_from: date = DATE_FROM,
    date_to: date = DATE_TO,
) -> bool:
    """日付が抽出対象期間内かどうか判定"""
    d = parse_date(date_str)
    if d is None:
        return True  # 日付不明の場合は含める（手動確認用）
    return date_from <= d <= date_to


def match_keywords(title: str) -> str | None:
    """見出しにキーワードが含まれているか判定し、マッチしたキーワードを返す"""
    for kw in KEYWORDS_JA:
        if kw in title:
            return kw
    title_lower = title.lower()
    for kw in KEYWORDS_EN:
        if kw in title_lower:
            return kw
    return None


def match_product_service(title: str) -> str | None:
    """商品/サービス関連のキーワードに合致するか判定"""
    for kw in PRODUCT_KEYWORDS:
        if kw in title:
            return kw
    return None


def filter_release(entry: dict) -> dict | None:
    """リリースエントリをフィルタリング

    条件に合致する場合は抽出理由を付与して返す。
    合致しない場合は None を返す。
    """
    title = entry.get("title", "")
    date_str = entry.get("date", "")

    # 日付フィルタ
    if not is_in_date_range(date_str):
        return None

    # キーワードマッチ
    kw = match_keywords(title)
    if kw:
        entry["reason"] = f"キーワード一致: 「{kw}」"
        return entry

    # 商品/サービス改定マッチ
    pk = match_product_service(title)
    if pk:
        entry["reason"] = f"商品/サービス改定・開始に該当: 「{pk}」"
        return entry

    return None


def filter_releases(releases: list[dict]) -> list[dict]:
    """リリースリスト全体をフィルタリング"""
    filtered = []
    seen = set()

    for entry in releases:
        result = filter_release(entry.copy())
        if result is None:
            continue

        # 重複排除（URL + タイトルの組合せ）
        dedup_key = (result.get("url", ""), result.get("title", ""))
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        filtered.append(result)

    # 日付降順ソート
    filtered.sort(key=lambda x: x.get("date", ""), reverse=True)
    return filtered
