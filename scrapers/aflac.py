"""アフラック生命スクレイパー

データ取得方針:
  - URL パターン: https://www.aflac.co.jp/corp/profile/news/{year}/
  - 前年・当年の2ページを取得（_year_urls と同様のアプローチをスクレイパー内で実装）

HTML構造:
  <div class="news" data-news-pc="row">
    <article class="news__article">
      <a class="news__type--pdf" href="/static/corp/profile/news/2026/20260526.pdf" ...>
        <div class="news__body">
          <div class="news__property">
            <time class="news__date">2026年05月26日</time>
          </div>
          <div class="news__caption">
            <h3 class="news__title">タイトル<i class="news__filesize">[PDF:819KB]</i></h3>
          </div>
        </div>
      </a>
    </article>
    ...
  </div>
"""

import logging
from datetime import date

from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)

_BASE    = "https://www.aflac.co.jp"
_URL_TPL = _BASE + "/corp/profile/news/{year}/"


class AflacScraper(BaseScraper):
    company_key  = "aflac"
    company_name = COMPANIES["aflac"]["name"]
    base_url     = _BASE

    def fetch_releases(self, category: str = "B") -> list[dict]:
        """前年・当年の2ページ分を取得する。"""
        cur_year  = date.today().year
        entries: list[dict] = []

        for year in (cur_year - 1, cur_year):
            url  = _URL_TPL.format(year=year)
            soup = self._get(url)
            got  = self._parse(soup, category)
            entries.extend(got)
            logger.info(f"[{self.company_name}] {year}年: {len(got)}件")

        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(entries)}件")
        return entries

    def _parse(self, soup, category: str) -> list[dict]:
        """div.news > article.news__article を解析してエントリリストを返す。"""
        entries = []

        for article in soup.select("div.news article.news__article"):
            # リンク（親の <a> タグ）
            a_tag = article.select_one("a[href]")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            if href and not href.startswith("http"):
                href = _BASE + href

            # 日付
            time_el  = article.select_one("time.news__date")
            date_str = time_el.get_text(strip=True) if time_el else ""

            # タイトル（ファイルサイズ表示を除去）
            title_el = article.select_one("h3.news__title")
            if not title_el:
                continue
            filesize = title_el.select_one("i.news__filesize")
            if filesize:
                filesize.decompose()
            title = title_el.get_text(strip=True)

            if not title:
                continue

            entries.append(self._make_entry(date_str, title, href, category))

        return entries
