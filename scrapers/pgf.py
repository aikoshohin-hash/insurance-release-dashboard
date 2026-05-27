"""PGF生命スクレイパー v2 - Incapsula WAF対策済み

Incapsula WAF は Referer と Accept-Language ヘッダーがない場合にブロックする。
これらを付与することで通過できることを確認済み。

エンドポイント（/is/news/ は軽量な専用API）:
  TYPE=1: ニュースリリース
  TYPE=2: お知らせ
"""

import re
import time
import logging

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper
from config import COMPANIES, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

PGF_BASE    = "https://www.pgf-life.co.jp"
PGF_NEWS    = f"{PGF_BASE}/is/news/NB100.do?TYPE=1"   # ニュースリリース
PGF_NOTICE  = f"{PGF_BASE}/is/news/NB100.do?TYPE=2"   # お知らせ

# Incapsula を通過するために必要なヘッダー
_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer":         PGF_BASE + "/",
}

# Incapsula のブロックページには "Pardon Our Interruption" が含まれる
# 実測サイズ: 正常コンテンツ ~2668B / ブロックページ ~4665B
_BLOCK_MARKER = "Pardon Our Interruption"


class PGFScraper(BaseScraper):
    company_key  = "pgf"
    company_name = COMPANIES["pgf"]["name"]
    base_url     = COMPANIES["pgf"]["base_url"]

    def fetch_releases(self, category: str = "B") -> list[dict]:
        url = PGF_NOTICE if category == "A" else PGF_NEWS

        soup = self._get_pgf(url)
        if soup is None:
            logger.warning(f"[{self.company_name}] カテゴリ{category}: 取得失敗（WAFブロック）")
            return []

        entries = self._parse_page(soup, category)
        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(entries)}件")
        return entries

    # ── 専用取得メソッド（Incapsula対策ヘッダー付き） ──────────────

    def _get_pgf(self, url: str) -> BeautifulSoup | None:
        """Incapsula WAF を通過するヘッダーでGETし、BSSoupを返す。

        ブロックされた場合は None を返す。
        """
        # レート制限（base.py と同じ間隔）
        elapsed = time.time() - self._last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        logger.info(f"[{self.company_name}] GET {url}")
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[{self.company_name}] リクエスト失敗: {url} -> {e}")
            return None

        self._last_request_time = time.time()

        # ブロックされた場合の検出（キーワードチェック）
        # 正常コンテンツ: ~2668B / ブロックページ: ~4665B + "Pardon Our Interruption"
        if _BLOCK_MARKER in resp.text:
            logger.warning(f"[{self.company_name}] Incapsula WAFブロック検出 "
                           f"(size={len(resp.content)}B): {url}")
            return None

        return BeautifulSoup(resp.content, "html.parser")

    # ── パース ───────────────────────────────────────────────────────

    def _parse_page(self, soup: BeautifulSoup, category: str) -> list[dict]:
        """テーブル形式のニュース一覧を解析する。

        HTML構造:
          <div class="box_newsPress">
            <table><tbody>
              <tr>
                <td width="125">2026年 5月27日</td>
                <td><span class="icon_pdf">
                  <a href='/hpcms/news/NB300.do?NID=2048'>タイトル</a>
                </span></td>
              </tr>
            </tbody></table>
          </div>
        """
        entries = []

        for tr in soup.select("div.box_newsPress table tr"):
            tds = tr.select("td")
            if len(tds) < 2:
                continue

            date_str = tds[0].get_text(strip=True)
            if not re.search(r"\d{4}年", date_str):
                continue

            a_tag = tds[1].select_one("a")
            if not a_tag:
                continue

            title = a_tag.get_text(strip=True)
            href  = a_tag.get("href", "")
            if href and not href.startswith("http"):
                href = f"{PGF_BASE}{href}"

            entries.append(self._make_entry(date_str, title, href, category))

        return entries
