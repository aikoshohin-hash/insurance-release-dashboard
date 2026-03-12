"""PGF生命スクレイパー（API経由でIncapsulaを回避）"""

import re
import logging
from .base import BaseScraper
from config import COMPANIES

logger = logging.getLogger(__name__)

# API エンドポイント
PGF_API_NEWS = "https://www.pgf-life.co.jp/is/news/NB100.do?TYPE=1"      # ニュースリリース
PGF_API_NOTICE = "https://www.pgf-life.co.jp/is/news/NB100.do?TYPE=2"    # お知らせ


class PGFScraper(BaseScraper):
    company_key = "pgf"
    company_name = COMPANIES["pgf"]["name"]
    base_url = COMPANIES["pgf"]["base_url"]

    def fetch_releases(self, category: str = "B") -> list[dict]:
        releases = []

        if category == "A":
            url = PGF_API_NOTICE
        elif category in ("B", "C"):
            url = PGF_API_NEWS
        else:
            return []

        soup = self._get(url)
        releases.extend(self._parse_page(soup, category))

        logger.info(f"[{self.company_name}] カテゴリ{category}: {len(releases)}件")
        return releases

    def _parse_page(self, soup, category: str) -> list[dict]:
        """API応答のテーブル構造を解析

        構造:
          <div class="box_newsPress">
            <table><tbody>
              <tr>
                <td width="125">2026年 3月 6日</td>
                <td><span class="icon_pdf">
                  <a href='/hpcms/news/NB300.do?NID=2042'>タイトル</a>
                </span></td>
              </tr>
            </tbody></table>
          </div>
        """
        entries = []

        for tr in soup.select("div.box_newsPress table tr, table tr"):
            tds = tr.select("td")
            if len(tds) < 2:
                continue

            date_str = tds[0].get_text(strip=True)
            # 日付形式チェック
            if not re.search(r"\d{4}年", date_str):
                continue

            a_tag = tds[1].select_one("a")
            if not a_tag:
                continue

            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            if href and not href.startswith("http"):
                href = f"https://www.pgf-life.co.jp{href}"

            entries.append(self._make_entry(date_str, title, href, category))

        return entries
