"""三井住友海上プライマリー生命スクレイパー v2"""

import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class MSPrimaryScraper(BaseScraper):
    company_key = "ms-primary"
    company_name = COMPANIES["ms-primary"]["name"]
    base_url = COMPANIES["ms-primary"]["base_url"]

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
        for article in soup.select("article.news__article"):
            a_tag = article.select_one("a")
            if not a_tag:
                continue

            time_tag = article.select_one("time.news__date")
            date_str = ""
            if time_tag:
                date_str = time_tag.get("datetime", time_tag.get_text(strip=True))

            cat_tag = article.select_one("div.news__category i")
            cat_label = cat_tag.get_text(strip=True) if cat_tag else ""

            title_tag = article.select_one("h3.news__title")
            if title_tag:
                filesize = title_tag.select_one("i.news__filesize")
                if filesize:
                    filesize.decompose()
                title = title_tag.get_text(strip=True)
            else:
                title = a_tag.get_text(strip=True)

            href = self._absolute_url(a_tag.get("href", ""))
            entries.append(self._make_entry(date_str, title, href, category))

        return entries
