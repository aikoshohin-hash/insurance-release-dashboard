"""日本生命スクレイパー v3 - JSON API 直接アクセス

日本生命はJS描画サイトのため、HTML解析では取得不可。
サイト内部の JSON API エンドポイントを直接取得:
  - /kaisha/news/json/index.json   → ニュースリリース (862件)
  - /kaisha/topics/json/index.json → お知らせ (134件)
"""

import re
import time
import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class NissayScraper(BaseScraper):
    company_key = "nissay"
    company_name = COMPANIES["nissay"]["name"]
    base_url = COMPANIES["nissay"]["base_url"]

    # JSON APIエンドポイント（サイト内部JS releaseOutput.js より特定）
    JSON_APIS = {
        "A": "https://www.nissay.co.jp/kaisha/topics/json/index.json",
        "B": "https://www.nissay.co.jp/kaisha/news/json/index.json",
    }

    def fetch_releases(self, category: str = "B") -> list[dict]:
        if category not in self.JSON_APIS:
            return []

        api_url = self.JSON_APIS[category]
        entries = self._fetch_json_api(api_url, category)

        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(entries)}件")
        return entries

    def _fetch_json_api(self, api_url: str, category: str) -> list[dict]:
        """JSON API からリリース一覧を取得

        JSON構造:
          [
            {
              "date": "2026-04-01",
              "title": "タイトル",
              "category": "商品・サービス",
              "link": "/kaisha/news/20260401.html",
              "category_weight": 1
            },
            ...
          ]
        """
        entries = []

        elapsed = time.time() - self._last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        logger.info(f"[{self.company_name}] GET {api_url}")
        try:
            resp = self.session.get(api_url, timeout=15)
            resp.raise_for_status()
            self._last_request_time = time.time()

            # サロゲートペア対策（日本生命JSONにはサロゲート文字が含まれる場合あり）
            text = resp.content.decode("utf-8", errors="replace")
            import json
            data = json.loads(text)

        except Exception as e:
            logger.warning(f"[{self.company_name}] JSON取得失敗: {e}")
            return entries

        if not isinstance(data, list):
            logger.warning(f"[{self.company_name}] JSON形式不正: {type(data)}")
            return entries

        for item in data:
            date_str = item.get("date", "")
            title = item.get("title", "")
            link = item.get("link", "")

            if not title:
                continue

            # 相対パスを絶対URLに変換
            if link and not link.startswith("http"):
                link = self._absolute_url(link)

            # サイズ表記除去: [198KB] 等
            title = re.sub(r"\s*[\[【]\d+KB[\]】]\s*$", "", title)

            entries.append(self._make_entry(date_str, title, link, category))

        return entries
