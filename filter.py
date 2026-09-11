"""リリース抽出フィルタリング v4

v3 は KEYWORDS_JA の部分一致で「通す/通さない」を決め、通さなかったものは
黙って捨てていた。そのため
  ・裸の「開始」で広報ニュースが大量に通る
  ・逆に取りこぼしても誰も気づけない
という二重の問題があった。

v4 は判定を relevance.py に委ね、**除外したものも理由付きで返す**。
除外分はダッシュボードの「除外ログ」タブに出す。ゲートが正しく効いているかを
人が毎日検証できなければ、ゲートは信用できないため。
"""

from __future__ import annotations

import re
from datetime import date, datetime

from config import DATE_FROM, DATE_TO
from relevance import classify, TIER_EXCLUDE


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
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def is_in_date_range(
    date_str: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> bool:
    """日付が抽出対象期間内かどうか判定"""
    d = parse_date(date_str)
    if d is None:
        return False  # 日付不明のエントリは除外（誤表示防止）
    return (date_from or DATE_FROM) <= d <= (date_to or DATE_TO)


def filter_releases(releases: list[dict]) -> tuple[list[dict], list[dict]]:
    """リリースリストを「本線＋周辺」と「除外」に分ける。

    Returns:
        (kept, excluded)
          kept     : PRODUCT / PERIPHERAL。entry["relevance"] に判定結果が入る
          excluded : EXCLUDE。理由付き。件数把握と検証のために保持する
    """
    kept: list[dict] = []
    excluded: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for raw in releases:
        entry = raw.copy()
        title = entry.get("title", "")

        # 日付フィルタ（期間外は集計にも載せない）
        if not is_in_date_range(entry.get("date", "")):
            continue

        # 重複排除（URL + タイトルの組合せ）
        dedup_key = (entry.get("url", ""), title)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        rel = classify(title)
        entry["relevance"] = rel
        entry["tier"]      = rel["tier"]
        entry["reason"]    = rel["reason"]

        if rel["tier"] == TIER_EXCLUDE:
            entry["noise_kind"] = rel.get("noise_kind", "")
            excluded.append(entry)
        else:
            kept.append(entry)

    kept.sort(key=lambda x: x.get("date", ""), reverse=True)
    excluded.sort(key=lambda x: x.get("date", ""), reverse=True)
    return kept, excluded
