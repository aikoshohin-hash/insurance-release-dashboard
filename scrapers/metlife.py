"""メットライフ生命スクレイパー"""

import re
import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class MetlifeScraper(BaseScraper):
    company_key = "metlife"
    company_name = COMPANIES["metlife"]["name"]
    base_url = COMPANIES["metlife"]["base_url"]

    def fetch_releases(self, category: str = "C") -> list[dict]:
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
        """AEM構造: <p><b>日付</b> <a href="...">タイトル</a></p>"""
        entries = []

        # メインコンテンツ内のp要素を走査
        content = soup.select_one("section.wysiwyg-rte, div.parsys, div.content, main")
        if not content:
            content = soup

        for p in content.find_all("p"):
            b_tag = p.find("b")
            a_tag = p.find("a")
            if not b_tag or not a_tag:
                continue

            date_text = b_tag.get_text(strip=True)
            # 日付形式チェック: YYYY.M.D
            if not re.match(r"\d{4}\.\d{1,2}\.\d{1,2}", date_text):
                continue

            title = a_tag.get_text(strip=True)
            # PDFサイズ表記を除去
            title = re.sub(r"\s*\(PDF[^)]*\)\s*$", "", title)

            href = a_tag.get("href", "")
            if href and not href.startswith("http"):
                href = f"https://www.metlife.co.jp{href}"

            entries.append(self._make_entry(date_text, title, href, category))

        return entries
