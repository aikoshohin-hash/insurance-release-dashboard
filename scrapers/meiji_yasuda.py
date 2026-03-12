"""明治安田生命スクレイパー v2"""

import re
import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class MeijiYasudaScraper(BaseScraper):
    company_key = "meiji-yasuda"
    company_name = COMPANIES["meiji-yasuda"]["name"]
    base_url = COMPANIES["meiji-yasuda"]["base_url"]

    def fetch_releases(self, category: str = "B") -> list[dict]:
        pages = COMPANIES[self.company_key]["pages"]
        if category not in pages:
            return []

        releases = []
        for base_url in pages[category]:
            soup = self._get(base_url)
            releases.extend(self._parse_page(soup, category))

            # ページネーション
            pagination = soup.select_one("div.c-pagination, nav.pagination")
            if pagination:
                for a_tag in pagination.select("a"):
                    href = a_tag.get("href", "")
                    if re.match(r"index_\d+\.html", href):
                        page_url = base_url.rstrip("/") + "/" + href if not href.startswith("http") else href
                        page_soup = self._get(page_url)
                        releases.extend(self._parse_page(page_soup, category))

        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(releases)}件")
        return releases

    def _parse_page(self, soup, category: str) -> list[dict]:
        """リリース一覧ページのパース"""
        entries = []

        # パターン1: p-news-list
        for li in soup.select("ul.p-news-list--2 > li, ul.p-news-list > li"):
            a_tag = li.select_one("a.p-news-list__item, a")
            if not a_tag:
                continue

            date_div = li.select_one("div.p-news-list__item-date, .date")
            date_str = date_div.get_text(strip=True) if date_div else ""

            title_tag = li.select_one(
                "p.p-news-list__item-text-pdf, p.p-news-list__item-text, .title"
            )
            title = title_tag.get_text(strip=True) if title_tag else a_tag.get_text(strip=True)

            href = self._absolute_url(a_tag.get("href", ""))
            entries.append(self._make_entry(date_str, title, href, category))

        # パターン2: topics (/profile/news/topics/) 用
        # <li><a href="..."><span class="date">2026/03/05</span><span class="title">タイトル</span></a></li>
        if not entries:
            for li in soup.select("ul li"):
                a_tag = li.select_one("a")
                if not a_tag:
                    continue
                date_span = a_tag.select_one("span.date")
                title_span = a_tag.select_one("span.title")
                if not date_span or not title_span:
                    continue
                date_str = date_span.get_text(strip=True)
                title = title_span.get_text(strip=True)
                href = self._absolute_url(a_tag.get("href", ""))
                entries.append(self._make_entry(date_str, title, href, category))

        return entries
