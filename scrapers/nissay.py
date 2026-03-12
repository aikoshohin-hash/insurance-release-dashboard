"""日本生命スクレイパー（JS描画対応：APIエンドポイント直接アクセス）"""

import json
import re
import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class NissayScraper(BaseScraper):
    company_key = "nissay"
    company_name = COMPANIES["nissay"]["name"]
    base_url = COMPANIES["nissay"]["base_url"]

    # 日本生命はJS描画のため、まずHTML内のJSON / APIを探す
    # フォールバック: HTMLから取得可能なリンクを収集

    def fetch_releases(self, category: str = "B") -> list[dict]:
        pages = COMPANIES[self.company_key]["pages"]
        if category not in pages:
            return []

        releases = []
        for url in pages[category]:
            # まず通常のHTTPリクエストで試行
            soup = self._get(url)

            # JS template内のデータを解析
            entries = self._parse_static(soup, category)
            if entries:
                releases.extend(entries)
            else:
                # JS描画で空の場合、JSON APIを探索
                entries = self._try_json_api(category)
                releases.extend(entries)

        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(releases)}件")
        return releases

    def _parse_static(self, soup, category: str) -> list[dict]:
        """静的HTML部分からエントリを抽出（フォールバック）"""
        entries = []
        for li in soup.select("li.m-link-list-release__item"):
            a_tag = li.select_one("a.m-link-list-release__link")
            if not a_tag:
                continue
            time_tag = li.select_one("time.m-link-list-release__date")
            date_str = time_tag.get("datetime", "") if time_tag else ""
            title_span = li.select_one("span.m-link-list-release__text")
            title = title_span.get_text(strip=True) if title_span else a_tag.get_text(strip=True)
            href = self._absolute_url(a_tag.get("href", ""))
            entries.append(self._make_entry(date_str, title, href, category))
        return entries

    def _try_json_api(self, category: str) -> list[dict]:
        """JSON APIエンドポイントを試行"""
        entries = []
        # 一般的なAPIパターンを試行
        api_urls = [
            f"https://www.nissay.co.jp/kaisha/{'news' if category == 'B' else 'topics'}/json/list.json",
            f"https://www.nissay.co.jp/api/{'news' if category == 'B' else 'topics'}/",
        ]
        for api_url in api_urls:
            try:
                import time
                elapsed = time.time() - self._last_request_time
                if elapsed < 1.0:
                    time.sleep(1.0 - elapsed)
                resp = self.session.get(api_url, timeout=10)
                self._last_request_time = time.time()
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        for item in data:
                            date_str = item.get("date", "")
                            title = item.get("title", "")
                            href = item.get("url", item.get("link", ""))
                            if href:
                                href = self._absolute_url(href)
                            entries.append(self._make_entry(date_str, title, href, category))
                    break
            except Exception:
                continue

        # APIが見つからない場合、ホームページのニュースセクションから取得
        if not entries:
            entries = self._parse_homepage(category)

        return entries

    def _parse_homepage(self, category: str) -> list[dict]:
        """ホームページのニュースセクションから取得"""
        entries = []
        soup = self._get("https://www.nissay.co.jp/")
        # ホームページのニュースリスト
        for li in soup.select("ul.m-link-list-release li, ul.p-top-news__list li"):
            a_tag = li.select_one("a")
            if not a_tag:
                continue
            time_tag = li.select_one("time")
            date_str = time_tag.get("datetime", time_tag.get_text(strip=True)) if time_tag else ""
            # タイトル
            title_el = li.select_one(".m-link-list-release__text, .p-top-news__text, .text")
            title = title_el.get_text(strip=True) if title_el else a_tag.get_text(strip=True)
            href = self._absolute_url(a_tag.get("href", ""))
            entries.append(self._make_entry(date_str, title, href, category))
        return entries
