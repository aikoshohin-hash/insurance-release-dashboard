"""オリックス生命スクレイパー v3 - microCMS API対応

サイトリニューアルにより、コンテンツが microCMS で配信されるようになったため
API経由で直接取得する方式に変更。

API情報（micro.js から取得）:
  Service ID : k1os4xfvrp
  Endpoint   : https://k1os4xfvrp.microcms.io/api/v1/news
  API Key    : R7XEJFS5lYE61714OHVb26kIZdnXLnmpUnGu（公開済みキー）
"""

import logging
from datetime import datetime, timezone

import requests

from .base import BaseScraper
from config import COMPANIES, DATE_FROM, DATE_TO

logger = logging.getLogger(__name__)

_SERVICE_ID = "k1os4xfvrp"
_API_KEY    = "R7XEJFS5lYE61714OHVb26kIZdnXLnmpUnGu"
_BASE_API   = f"https://{_SERVICE_ID}.microcms.io/api/v1/news"
_BASE_URL   = "https://www.orixlife.co.jp"


class OrixScraper(BaseScraper):
    company_key  = "orix"
    company_name = COMPANIES["orix"]["name"]
    base_url     = COMPANIES["orix"]["base_url"]

    def fetch_releases(self, category: str = "B") -> list[dict]:
        """microCMS API から全ニュースを取得。

        カテゴリ区別なし（APIが統合エンドポイント）のため、
        A/B どちらで呼ばれても同じデータを返す。
        重複は filter.py 側の dedup で除去される。
        """
        entries = self._fetch_all_from_api()
        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(entries)}件")
        return entries

    def _fetch_all_from_api(self) -> list[dict]:
        """microCMS API をページングしながら全件取得する。"""
        # DATE_FROM を ISO8601 UTC で渡す（APIのフィルタ形式に合わせる）
        date_from_iso = datetime(
            DATE_FROM.year, DATE_FROM.month, DATE_FROM.day,
            tzinfo=timezone.utc
        ).isoformat()

        headers = {"X-MICROCMS-API-KEY": _API_KEY}
        limit   = 100
        offset  = 0
        entries = []

        while True:
            params = {
                "filters": f"published_at[greater_than]{date_from_iso}",
                "limit":   limit,
                "offset":  offset,
                "orders":  "-published_at",
            }
            try:
                resp = requests.get(
                    _BASE_API, headers=headers, params=params, timeout=30
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                logger.warning(f"[{self.company_name}] API取得失敗: {e}")
                break

            data     = resp.json()
            contents = data.get("contents", [])
            total    = data.get("totalCount", 0)

            for item in contents:
                entry = self._item_to_entry(item)
                if entry:
                    entries.append(entry)

            offset += len(contents)
            if offset >= total or not contents:
                break

        return entries

    def _item_to_entry(self, item: dict) -> dict | None:
        """microCMS のアイテム辞書をエントリ辞書に変換する。"""
        title = item.get("title", "").strip()
        if not title:
            return None

        # published_at: "2026-03-24T15:00:00.000Z"
        pub_raw  = item.get("published_at", "")
        date_str = pub_raw[:10] if pub_raw else ""     # → "2026-03-24"

        # URL: link フィールドは [{"fieldId":"url","url":"/about/news/..."}]
        link_list = item.get("link", [])
        href = ""
        if link_list and isinstance(link_list, list):
            href = link_list[0].get("url", "")
        if href and not href.startswith("http"):
            href = _BASE_URL + href

        return self._make_entry(date_str, title, href, "")
