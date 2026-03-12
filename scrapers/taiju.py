"""大樹生命スクレイパー"""

import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class TaijuScraper(BaseScraper):
    company_key = "taiju"
    company_name = COMPANIES["taiju"]["name"]
    base_url = COMPANIES["taiju"]["base_url"]

    def fetch_releases(self, category: str = "B") -> list[dict]:
        pages = COMPANIES[self.company_key]["pages"]
        if category not in pages:
            return []

        releases = []
        for url in pages[category]:
            soup = self._get(url)
            releases.extend(self._parse_page(soup, category))

        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(releases)}件")
        return releases

    def _parse_page(self, soup, category: str) -> list[dict]:
        """ul.news-release__list からエントリ取得"""
        entries = []
        for li in soup.select("ul.news-release__list > li.news-release__list-item"):
            a_tag = li.select_one("a.news-release__list-item-anchor, a.news-release__list-item-anchor--pdf")
            if not a_tag:
                continue

            time_tag = li.select_one("time.news-release__list-item-date")
            date_str = ""
            if time_tag:
                date_str = time_tag.get("datetime", time_tag.get_text(strip=True))

            title_span = li.select_one("span.news-release__list-item-title")
            title = title_span.get_text(strip=True) if title_span else a_tag.get_text(strip=True)

            href = self._absolute_url(a_tag.get("href", ""))
            entries.append(self._make_entry(date_str, title, href, category))

        return entries
