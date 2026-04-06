"""マニュライフ生命スクレイパー v3 - キャッシュフォールバック方式

Akamai WAF保護のため、通常のHTTPリクエストでは403ブロックされる。
対策:
  1. まず通常のHTTPリクエストを試行（WAFルール変更時に自動復旧）
  2. ブロック時は output/manulife_cache.json から読み込み

キャッシュ更新方法:
  - ブラウザで https://www.manulife.co.jp/ja/individual/about/newsrelease.html を開き
  - 取得したデータを output/manulife_cache.json に保存
"""

import json
import os
import re
import logging
from pathlib import Path
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)

# キャッシュファイルパス
CACHE_FILE = Path(__file__).resolve().parent / "manulife_cache.json"


class ManulifeScraper(BaseScraper):
    company_key = "manulife"
    company_name = COMPANIES["manulife"]["name"]
    base_url = COMPANIES["manulife"]["base_url"]

    # 統合ニュースリリースページ
    RELEASE_URL = "https://www.manulife.co.jp/ja/individual/about/newsrelease.html"

    def fetch_releases(self, category: str = "B") -> list[dict]:
        pages = COMPANIES[self.company_key]["pages"]
        if category not in pages:
            return []

        # まず通常のHTTPリクエストを試行
        releases = self._try_http(category)
        if releases:
            return releases

        # WAFブロック時: キャッシュから読み込み
        logger.info(f"[{self.company_name}] HTTPブロック → キャッシュ読み込み")
        releases = self._load_from_cache(category)

        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(releases)}件")
        return releases

    def _try_http(self, category: str) -> list[dict]:
        """通常のHTTPリクエストでの取得を試行"""
        pages = COMPANIES[self.company_key]["pages"]
        releases = []

        for url in pages[category]:
            soup = self._get(url)
            page_text = soup.get_text()

            # WAFブロック検出
            if "Access Denied" in page_text or "edgesuite" in str(soup) or len(page_text.strip()) < 100:
                logger.warning(
                    f"[{self.company_name}] Akamai WAFブロック検出。キャッシュにフォールバック。"
                )
                return []

            entries = self._parse_page(soup, category)
            releases.extend(entries)

        return releases

    def _parse_page(self, soup, category: str) -> list[dict]:
        """HTMLページからエントリを抽出

        HTML構造:
          <p><strong>2026年4月3日</strong></p>
          <p>プレスリリース</p>
          <p><a href="...">タイトル</a></p>
        """
        entries = []
        date_re = re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日$")

        for strong in soup.select("strong"):
            date_text = strong.get_text(strip=True)
            if not date_re.match(date_text):
                continue

            p = strong.parent
            if not p or p.name != "p":
                continue

            sibling = p.next_sibling
            cat = ""
            title = ""
            href = ""
            count = 0

            while sibling and count < 10:
                if hasattr(sibling, "get_text"):
                    text = sibling.get_text(strip=True)

                    # 次の日付エントリに到達したら終了
                    s = sibling.select_one("strong") if hasattr(sibling, "select_one") else None
                    if s and date_re.match(s.get_text(strip=True)):
                        break

                    # カテゴリ検出
                    if not cat:
                        if "プレスリリース" in text:
                            cat = "B"
                        elif "お知らせ" in text:
                            cat = "A"

                    # リンク検出
                    if not href and hasattr(sibling, "select_one"):
                        a = sibling.select_one("a")
                        if a:
                            title = a.get_text(strip=True)
                            href = self._absolute_url(a.get("href", ""))

                    if cat and href:
                        break

                sibling = sibling.next_sibling
                count += 1

            if title and href:
                entry_cat = cat or "B"
                if entry_cat == category:
                    entries.append(self._make_entry(date_text, title, href, category))

        return entries

    def _load_from_cache(self, category: str) -> list[dict]:
        """キャッシュJSONからエントリを読み込み"""
        if not CACHE_FILE.exists():
            logger.warning(
                f"[{self.company_name}] キャッシュファイルなし: {CACHE_FILE}\n"
                f"  ブラウザで {self.RELEASE_URL} を開いてキャッシュを更新してください。"
            )
            return []

        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"[{self.company_name}] キャッシュ読み込み失敗: {e}")
            return []

        fetched_at = data.get("fetched_at", "")
        raw_entries = data.get("entries", [])
        logger.info(
            f"[{self.company_name}] キャッシュ読み込み: {len(raw_entries)}件 "
            f"(取得日時: {fetched_at})"
        )

        entries = []
        for item in raw_entries:
            item_cat = item.get("category", "B")
            if item_cat != category:
                continue

            date_str = item.get("date", "")
            title = item.get("title", "")
            url = item.get("url", "")

            if not title:
                continue

            entries.append(self._make_entry(date_str, title, url, category))

        return entries
