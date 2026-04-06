"""住友生命スクレイパー v3

サイトリニューアル対応: ニュースリリースとお知らせが
統合ページ /infolist/ に集約。
ul.mod-newsList > li 内の <time> + <a> を抽出。
"""

import re
import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)


class SumitomoScraper(BaseScraper):
    company_key = "sumitomo"
    company_name = COMPANIES["sumitomo"]["name"]
    base_url = COMPANIES["sumitomo"]["base_url"]

    # 統合ニュースページ（カテゴリA/B共通）
    NEWS_URL = "https://www.sumitomolife.co.jp/infolist/"

    # サイト側のカテゴリラベル → 当ツールのカテゴリ対応
    CATEGORY_MAP_B = ["商品・サービス", "企業情報"]
    CATEGORY_MAP_A = ["トピックス", "イベント・セミナー", "キャンペーン", "サステナビリティ"]

    def fetch_releases(self, category: str = "B") -> list[dict]:
        pages = COMPANIES[self.company_key]["pages"]
        if category not in pages:
            return []

        soup = self._get(self.NEWS_URL)
        releases = self._parse_news_list(soup, category)

        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(releases)}件")
        return releases

    def _parse_news_list(self, soup, category: str) -> list[dict]:
        """統合ニュースページからエントリ抽出

        HTML構造:
          <ul class="mod-newsList">
            <li class="rt_bn_news_list">
              <time class="__time">2026年04月06日</time>
              <span>カテゴリ</span>
              <a href="...">タイトル</a>
            </li>
          </ul>
        """
        entries = []

        for li in soup.select("ul.mod-newsList > li"):
            # 日付
            time_tag = li.select_one("time")
            if not time_tag:
                continue
            date_str = time_tag.get_text(strip=True)

            # サイト側カテゴリ
            spans = li.select("span")
            site_cat = ""
            for span in spans:
                text = span.get_text(strip=True)
                if text and text != date_str and len(text) < 20:
                    site_cat = text
                    break

            # カテゴリフィルタ
            if category == "B" and site_cat not in self.CATEGORY_MAP_B:
                continue
            if category == "A" and site_cat not in self.CATEGORY_MAP_A:
                continue

            # タイトルとURL
            a_tag = li.select_one("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            # 日付部分がタイトルに含まれていたら除去
            title = re.sub(r"^\d{4}年\d{1,2}月\d{1,2}日\s*", "", title)
            # PDFサイズ表記除去
            title = re.sub(r"\s*[\(（]\d+\)$", "", title)

            href = self._absolute_url(a_tag.get("href", ""))

            entries.append(self._make_entry(date_str, title, href, category))

        return entries
