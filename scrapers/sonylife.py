"""ソニー生命スクレイパー"""

import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class SonylifeScraper(BaseScraper):
    company_key = "sonylife"
    company_name = COMPANIES["sonylife"]["name"]
    base_url = COMPANIES["sonylife"]["base_url"]

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
        """ul.c-date-list からエントリ取得"""
        entries = []
        for li in soup.select("ul.c-date-list > li.c-date-list__item"):
            date_span = li.select_one("span.c-date-list__item__date")
            link_span = li.select_one("span.c-date-list__item__link")
            if not link_span:
                continue

            a_tag = link_span.select_one("a")
            if not a_tag:
                continue

            date_str = date_span.get_text(strip=True) if date_span else ""
            title = a_tag.get_text(strip=True)
            href = self._absolute_url(a_tag.get("href", ""))

            entries.append(self._make_entry(date_str, title, href, category))

        return entries
