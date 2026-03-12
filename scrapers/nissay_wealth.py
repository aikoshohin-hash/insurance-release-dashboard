"""ニッセイ・ウェルス生命スクレイパー v2"""

import re
import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class NissayWealthScraper(BaseScraper):
    company_key = "nissay-wealth"
    company_name = COMPANIES["nissay-wealth"]["name"]
    base_url = COMPANIES["nissay-wealth"]["base_url"]

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
        """トグルセクション内のリリースリストを解析"""
        entries = []
        # tpl-toggle セクション内の各エントリ
        for toggle in soup.select("div.tpl-toggle"):
            for li in toggle.select("ul.tpl-news-list__list li.item"):
                a_tag = li.select_one("a")
                if not a_tag:
                    continue

                date_p = li.select_one("p.date")
                date_str = date_p.get_text(strip=True) if date_p else ""

                cat_label = ""
                label_p = li.select_one("p.label")
                if label_p:
                    cat_label = label_p.get_text(strip=True)

                title_p = li.select_one("p.text")
                title = title_p.get_text(strip=True) if title_p else a_tag.get_text(strip=True)

                href = self._absolute_url(a_tag.get("href", ""))
                entries.append(self._make_entry(date_str, title, href, category))

        # tpl-toggle が無い場合のフォールバック
        if not entries:
            for li in soup.select("ul.tpl-news-list__list li.item, ul.news-list li"):
                a_tag = li.select_one("a")
                if not a_tag:
                    continue
                date_el = li.select_one("p.date, .date, time")
                date_str = date_el.get_text(strip=True) if date_el else ""
                title = a_tag.get_text(strip=True)
                href = self._absolute_url(a_tag.get("href", ""))
                entries.append(self._make_entry(date_str, title, href, category))

        return entries
