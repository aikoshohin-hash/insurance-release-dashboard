"""スクレイパー基底クラス v2"""

import re
import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import REQUEST_DELAY, REQUEST_TIMEOUT, BROWSER_HEADERS
from enricher import LegacyTLSAdapter

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """各社スクレイパーの基底クラス"""

    company_key: str = ""
    company_name: str = ""
    base_url: str = ""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)
        self.session.mount("https://", LegacyTLSAdapter())
        self.session.verify = True
        self._last_request_time = 0.0

    # ── HTTP ──

    def _get(self, url: str) -> BeautifulSoup:
        """URL取得して BeautifulSoup を返す（レート制限付き）"""
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)

        logger.info(f"[{self.company_name}] GET {url}")
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.exceptions.SSLError as e:
            # ここで verify=False にしてはいけない。
            # ソニー生命等の handshake failure は証明書検証の問題ではなく
            # **暗号スイート要件**であり、verify=False では解決しないまま
            # 中間者攻撃への耐性だけを失う（product-scout での実測）。
            # セッションには既に LegacyTLSAdapter を噛ませてあるので、
            # ここまで来た SSL エラーは素直に失敗として扱う。
            logger.warning(f"[{self.company_name}] SSL失敗: {url} -> {e}")
            return BeautifulSoup("", "html.parser")
        except requests.RequestException as e:
            logger.warning(f"[{self.company_name}] リクエスト失敗: {url} -> {e}")
            return BeautifulSoup("", "html.parser")
        self._last_request_time = time.time()
        return BeautifulSoup(resp.content, "html.parser")

    def _absolute_url(self, href: str) -> str:
        """相対URLを絶対URLに変換"""
        if not href or href.startswith("javascript"):
            return ""
        if href.startswith("http"):
            return href
        return urljoin(self.base_url, href)

    # ── エントリ生成 ──

    def _make_entry(
        self,
        date_str: str,
        title: str,
        url: str,
        category: str = "",
    ) -> dict:
        """リリースエントリの辞書を生成"""
        return {
            "company": self.company_name,
            "date": self._normalize_date(date_str),
            "title": title.strip(),
            "url": url,
            "category": category.strip() if category else "",
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # ── 日付パース ──

    @staticmethod
    def _normalize_date(text: str) -> str:
        """様々な日付形式を YYYY/MM/DD に正規化"""
        if not text:
            return ""
        text = text.strip()

        # "2025年10月1日"
        m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?", text)
        if m:
            return f"{m.group(1)}/{int(m.group(2)):02d}/{int(m.group(3)):02d}"

        # "2025/10/01" or "2025-10-01" or "2025.10.01"
        m = re.search(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", text)
        if m:
            return f"{m.group(1)}/{int(m.group(2)):02d}/{int(m.group(3)):02d}"

        return text

    # ── 抽象メソッド ──

    @abstractmethod
    def fetch_releases(self, category: str = "B") -> list[dict]:
        """指定カテゴリのリリース一覧を取得

        Args:
            category: "A"(お知らせ), "B"(ニュースリリース), "C"(プレスリリース)

        Returns:
            リリースエントリのリスト
        """
        ...
