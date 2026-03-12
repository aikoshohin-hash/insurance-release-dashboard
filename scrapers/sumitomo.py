"""住友生命スクレイパー"""

import re
import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class SumitomoScraper(BaseScraper):
    company_key = "sumitomo"
    company_name = COMPANIES["sumitomo"]["name"]
    base_url = COMPANIES["sumitomo"]["base_url"]

    def fetch_releases(self, category: str = "B") -> list[dict]:
        pages = COMPANIES[self.company_key]["pages"]
        if category not in pages:
            return []

        releases = []
        for url in pages[category]:
            soup = self._get(url)
            if category == "A":
                releases.extend(self._parse_infolist(soup))
            else:
                releases.extend(self._parse_newsrelease(soup))

        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(releases)}件")
        return releases

    def _parse_infolist(self, soup) -> list[dict]:
        """お知らせ一覧ページ (ul.list-topic-01)"""
        entries = []
        for li in soup.select("ul.list-topic-01 > li"):
            a_tag = li.select_one("a")
            if not a_tag:
                continue
            text = a_tag.get_text(strip=True)
            # 日付抽出: "2026年2月9日　..." 形式
            m = re.match(r"(\d{4}年\d{1,2}月\d{1,2}日)\s*(.*)", text)
            if m:
                date_str, title = m.group(1), m.group(2)
            else:
                date_str, title = "", text
            href = self._absolute_url(a_tag.get("href", ""))
            entries.append(self._make_entry(date_str, title, href, "A"))
        return entries

    def _parse_newsrelease(self, soup) -> list[dict]:
        """ニュースリリース年度ページ: <li><em>日付</em><a>タイトル</a></li>"""
        entries = []
        # パターン1: <em>日付</em> + <a>タイトル</a>
        for li in soup.select("ul li"):
            em_tag = li.select_one("em")
            a_tag = li.select_one("a")
            if not em_tag or not a_tag:
                continue
            date_text = em_tag.get_text(strip=True)
            # 日付っぽいかチェック
            if not re.search(r"\d{4}年", date_text):
                continue
            title = a_tag.get_text(strip=True)
            href = self._absolute_url(a_tag.get("href", ""))
            entries.append(self._make_entry(date_text, title, href, "B"))

        # パターン2: フォールバック (span.date + a)
        if not entries:
            for li in soup.select("ul.c-nav-news-01 > li, ul.list-news-01 > li"):
                date_el = li.select_one("span.c-nav-news-contents-data, span.data, .date")
                a_tag = li.select_one("a")
                if not a_tag:
                    continue
                date_str = date_el.get_text(strip=True) if date_el else ""
                title = a_tag.get_text(strip=True)
                href = self._absolute_url(a_tag.get("href", ""))
                entries.append(self._make_entry(date_str, title, href, "B"))
        return entries
