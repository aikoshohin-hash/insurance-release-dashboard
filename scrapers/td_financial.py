"""T&Dフィナンシャル生命スクレイパー v2"""

import re
import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class TDFinancialScraper(BaseScraper):
    company_key = "td-financial"
    company_name = COMPANIES["td-financial"]["name"]
    base_url = COMPANIES["td-financial"]["base_url"]

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
        entries = []
        news_list = soup.select_one("ul.list-info-01")
        if not news_list:
            return entries

        for li in news_list.find_all("li", recursive=False):
            date_el = li.select_one("span.date dt") or li.select_one("span.date")
            if not date_el:
                continue
            date_str = date_el.get_text(strip=True)

            for link_li in li.select("li.link-container"):
                a_tag = link_li.select_one("a")
                if not a_tag:
                    continue
                raw_title = a_tag.get_text(strip=True)
                title = re.sub(r"\s*\(\d+KB\)\s*$", "", raw_title)
                href = a_tag.get("href", "")
                if not href.startswith("http"):
                    href = f"https://www.tdf-life.co.jp/newsrelease/{href}"
                entries.append(self._make_entry(date_str, title, href, category))

        return entries
