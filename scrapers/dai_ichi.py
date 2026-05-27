"""第一生命スクレイパー

データ取得方針:
  - 当年ニュース: common_v2/html/news/index.html （jQuery $.load() で動的挿入される軽量HTML）
  - 前年アーカイブ: /company/news/{year}.html   （同じ ul.textNews 構造）

HTML構造:
  <ul class="textNews">
    <li class="clearfix">
      <p class="textNews-date">2026/05/18</p>
      <p class="textNews-title">
        <a class="textNews-title-pdf" href="/company/news/pdf/2026_008.pdf">タイトル</a>
      </p>
    </li>
    ...
  </ul>
"""

import logging
from datetime import date

from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)

_BASE = "https://www.dai-ichi-life.co.jp"
# 当年ニュース（jQuery で動的ロードされる軽量HTML）
_CURRENT_URL  = _BASE + "/common_v2/html/news/index.html"
# 前年アーカイブ（同じ ul.textNews 構造）
_ARCHIVE_TPL  = _BASE + "/company/news/{year}.html"


class DaiIchiScraper(BaseScraper):
    company_key  = "dai-ichi"
    company_name = COMPANIES["dai-ichi"]["name"]
    base_url     = _BASE

    def fetch_releases(self, category: str = "B") -> list[dict]:
        """当年 + 前年の2ページ分を取得する。

        カテゴリはA/B統合（サイト側で区別なし）のため
        呼び出し元のカテゴリにかかわらず同データを返す。
        重複は filter.py の dedup で除去される。
        """
        entries: list[dict] = []

        # 1) 当年ニュース（common_v2 の軽量HTML）
        soup = self._get(_CURRENT_URL)
        entries.extend(self._parse(soup, category))

        # 2) 前年アーカイブ
        prev_year = date.today().year - 1
        archive_url = _ARCHIVE_TPL.format(year=prev_year)
        soup2 = self._get(archive_url)
        entries.extend(self._parse(soup2, category))

        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(entries)}件")
        return entries

    def _parse(self, soup, category: str) -> list[dict]:
        """ul.textNews を解析してエントリリストを返す。"""
        entries = []
        for li in soup.select("ul.textNews li.clearfix"):
            date_el  = li.select_one("p.textNews-date")
            title_el = li.select_one("p.textNews-title a")
            if not date_el or not title_el:
                continue

            date_str = date_el.get_text(strip=True)   # "2026/05/18"
            title    = title_el.get_text(strip=True)
            href     = title_el.get("href", "")
            if href and not href.startswith("http"):
                href = _BASE + href

            entries.append(self._make_entry(date_str, title, href, category))

        return entries
