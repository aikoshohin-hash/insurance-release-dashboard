"""ソニー生命スクレイパー v3

SSL handshake failure 対策:
  Python の requests/urllib3 では TLS接続不可だが、
  curl / subprocess 経由なら取得可能。
  curl フォールバックを実装。
"""

import re
import subprocess
import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class SonylifeScraper(BaseScraper):
    company_key = "sonylife"
    company_name = COMPANIES["sonylife"]["name"]
    base_url = COMPANIES["sonylife"]["base_url"]

    def fetch_releases(self, category: str = "B") -> list[dict]:
        pages = COMPANIES[self.company_key]["pages"]
        if category not in pages:
            return []

        releases = []
        for url in pages[category]:
            # まず requests で試行
            soup = self._get(url)
            entries = self._parse_page(soup, category)

            if not entries:
                # SSL失敗時: curl フォールバック
                logger.info(f"[{self.company_name}] curl フォールバック: {url}")
                soup = self._get_via_curl(url)
                entries = self._parse_page(soup, category)

            releases.extend(entries)

        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(releases)}件")
        return releases

    def _get_via_curl(self, url: str):
        """curl で HTML を取得し BeautifulSoup を返す"""
        from bs4 import BeautifulSoup
        try:
            result = subprocess.run(
                ["curl", "-s", "--tlsv1.2", "-m", "30",
                 "-H", f"User-Agent: {self.session.headers.get('User-Agent', '')}",
                 url],
                capture_output=True, text=True, timeout=35, encoding="utf-8", errors="replace"
            )
            if result.returncode == 0 and result.stdout:
                logger.info(f"[{self.company_name}] curl 取得成功: {url} ({len(result.stdout)} bytes)")
                return BeautifulSoup(result.stdout, "html.parser")
            else:
                logger.warning(f"[{self.company_name}] curl 失敗 (code={result.returncode}): {url}")
        except Exception as e:
            logger.warning(f"[{self.company_name}] curl エラー: {e}")

        return BeautifulSoup("", "html.parser")

    def _parse_page(self, soup, category: str) -> list[dict]:
        """ニュースリリース / お知らせページを解析

        HTML構造:
          <ul>
            <li>
              2026年3月25日
              <a href="/company/news/...">タイトル</a>
            </li>
          </ul>
        """
        entries = []

        for li in soup.select("li"):
            a_tag = li.select_one("a")
            if not a_tag:
                continue

            text = li.get_text(strip=True)
            href = a_tag.get("href", "")

            # ソニー生命のニュースリンクパターン
            if not re.search(r"/(company/news|info)/", href):
                continue

            # 日付抽出: "YYYY年M月D日タイトル" パターン
            m = re.match(r"(\d{4}年\d{1,2}月\d{1,2}日)(.*)", text)
            if not m:
                continue

            date_str = m.group(1)
            title = a_tag.get_text(strip=True)

            # PDFサイズ除去
            title = re.sub(r"\s*[\(（]PDF[^)）]*[\)）]\s*$", "", title)

            href = self._absolute_url(href)
            entries.append(self._make_entry(date_str, title, href, category))

        return entries
