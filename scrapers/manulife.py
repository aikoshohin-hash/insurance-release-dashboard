"""マニュライフ生命スクレイパー（Akamai WAF保護あり → ベストエフォート）"""

import re
import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class ManulifeScraper(BaseScraper):
    company_key = "manulife"
    company_name = COMPANIES["manulife"]["name"]
    base_url = COMPANIES["manulife"]["base_url"]

    def fetch_releases(self, category: str = "B") -> list[dict]:
        pages = COMPANIES[self.company_key]["pages"]
        if category not in pages:
            return []

        releases = []
        for url in pages[category]:
            soup = self._get(url)

            # WAFブロック検出
            page_text = soup.get_text()
            if "Access Denied" in page_text or "edgesuite" in str(soup) or len(page_text.strip()) < 100:
                logger.warning(
                    f"[{self.company_name}] Akamai WAFによりブロック。"
                    f"ブラウザでの手動確認が必要です。 URL: {url}"
                )
                continue

            releases.extend(self._parse_page(soup, category))

        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(releases)}件")
        return releases

    def _parse_page(self, soup, category: str) -> list[dict]:
        entries = []

        # パターン1: テーブル形式
        for tr in soup.select("table tr"):
            tds = tr.select("td")
            if len(tds) < 2:
                continue
            date_str = tds[0].get_text(strip=True)
            if not re.match(r"\d{4}", date_str):
                continue
            a_tag = tds[-1].select_one("a")
            title = a_tag.get_text(strip=True) if a_tag else tds[-1].get_text(strip=True)
            href = self._absolute_url(a_tag.get("href", "")) if a_tag else ""
            entries.append(self._make_entry(date_str, title, href, category))

        # パターン2: リスト形式
        if not entries:
            for li in soup.select("ul li"):
                a_tag = li.select_one("a")
                if not a_tag:
                    continue
                date_el = li.select_one("time, .date, span.date")
                date_str = date_el.get("datetime", date_el.get_text(strip=True)) if date_el else ""
                title = a_tag.get_text(strip=True)
                href = self._absolute_url(a_tag.get("href", ""))
                entries.append(self._make_entry(date_str, title, href, category))

        return entries
