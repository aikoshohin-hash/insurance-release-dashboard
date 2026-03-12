"""オリックス生命スクレイパー"""

import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class OrixScraper(BaseScraper):
    company_key = "orix"
    company_name = COMPANIES["orix"]["name"]
    base_url = COMPANIES["orix"]["base_url"]

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
        """corporate-info 形式を解析

        構造:
          <div class="corporate-info">
            <div class="corporate-info--col">
              <p class="corporate-info__date">2026年02月17日</p>
              <div class="link-list__wrap">
                <ul class="link-list"><li><a class="link-list__icon-arrow07">タイトル</a></li></ul>
              </div>
            </div>
          </div>
        """
        entries = []

        for info_block in soup.select("div.corporate-info"):
            date_el = info_block.select_one("p.corporate-info__date")
            date_str = date_el.get_text(strip=True) if date_el else ""

            for a_tag in info_block.select("a.link-list__icon-arrow07"):
                title = a_tag.get_text(strip=True)
                href = self._absolute_url(a_tag.get("href", ""))
                entries.append(self._make_entry(date_str, title, href, category))

        return entries
