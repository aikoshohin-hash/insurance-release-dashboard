"""太陽生命スクレイパー（JSON API直接アクセス）"""

import re
import json
import time
import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class TaiyoScraper(BaseScraper):
    company_key = "taiyo"
    company_name = COMPANIES["taiyo"]["name"]
    base_url = COMPANIES["taiyo"]["base_url"]

    def fetch_releases(self, category: str = "B") -> list[dict]:
        pages = COMPANIES[self.company_key]["pages"]
        if category not in pages:
            return []

        releases = []
        for url in pages[category]:
            if url.endswith(".json"):
                releases.extend(self._parse_json(url, category))
            else:
                soup = self._get(url)
                releases.extend(self._parse_html(soup, category))

        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(releases)}件")
        return releases

    def _parse_json(self, url: str, category: str) -> list[dict]:
        """JSON APIから取得"""
        entries = []
        elapsed = time.time() - self._last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        logger.info(f"[{self.company_name}] GET {url}")
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            self._last_request_time = time.time()
            data = resp.json()
        except Exception as e:
            logger.warning(f"[{self.company_name}] JSON取得失敗: {e}")
            return entries

        if category == "A":
            # news.json: {"news": [...], "important_news": [...]}
            items = data.get("news", []) + data.get("important_news", [])
        else:
            # release.json: {"release": [...]}
            items = data.get("release", [])

        for item in items:
            date_str = item.get("date", "")
            title = item.get("title", "")
            link = item.get("link", "")

            # 相対パスを絶対に変換
            if link and not link.startswith("http"):
                if link.startswith("../"):
                    # PDF相対パス: ../pdf/... → /company/notice/pdf/...
                    if category == "A":
                        link = f"https://www.taiyo-seimei.co.jp/company/notice/{link.replace('../', '')}"
                    else:
                        link = f"https://www.taiyo-seimei.co.jp/company/notice/{link.replace('../', '')}"
                else:
                    link = self._absolute_url(link)

            # ファイルサイズ除去
            title = re.sub(r"（PDF\s*[\d.]+KB）", "", title).strip()

            entries.append(self._make_entry(date_str, title, link, category))

        return entries

    def _parse_html(self, soup, category: str) -> list[dict]:
        """HTMLフォールバック"""
        entries = []
        for dd in soup.select("dl.news > dd, dl.js-press > dd"):
            date_span = dd.select_one("span.data")
            link_span = dd.select_one("span.txt a")
            if not link_span:
                continue
            date_str = date_span.get_text(strip=True) if date_span else ""
            title = link_span.get_text(strip=True)
            href = self._absolute_url(link_span.get("href", ""))
            entries.append(self._make_entry(date_str, title, href, category))
        return entries
