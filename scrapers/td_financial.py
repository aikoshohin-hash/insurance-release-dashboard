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

        # span.date ごとに日付を取得し、同じ親要素内の dd > a をリンクとして抽出
        # HTML構造: <li> <span class="date"><dt>日付</dt></span> <dd><ul><li class="link-container"><a>...</a></li></ul></dd> </li>
        for date_span in soup.select("span.date"):
            dt = date_span.select_one("dt")
            date_str = dt.get_text(strip=True) if dt else date_span.get_text(strip=True)

            # 親要素の dd からリンクを取得
            parent = date_span.parent
            if not parent:
                continue
            dd = parent.find("dd")
            if not dd:
                continue

            for a_tag in dd.select("a"):
                raw_title = a_tag.get_text(strip=True)
                title = re.sub(r"\s*[\(（]\d+KB[\)）]\s*$", "", raw_title)
                href = a_tag.get("href", "")
                if not href.startswith("http"):
                    href = f"https://www.tdf-life.co.jp/newsrelease/{href}"
                entries.append(self._make_entry(date_str, title, href, category))

        return entries
