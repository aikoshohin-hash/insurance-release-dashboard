"""スクレイパー動的ロード

companies.py の enabled フラグに基づいて、
有効な会社のスクレイパーのみ SCRAPER_MAP に登録する。
"""

import importlib
import logging

from companies import get_enabled_companies

logger = logging.getLogger(__name__)

SCRAPER_MAP = {}

# 各スクレイパーモジュール内のクラス名マッピング
_CLASS_NAMES = {
    "sumitomo": "SumitomoScraper",
    "nissay": "NissayScraper",
    "nissay_wealth": "NissayWealthScraper",
    "taiju": "TaijuScraper",
    "meiji_yasuda": "MeijiYasudaScraper",
    "ms_primary": "MSPrimaryScraper",
    "metlife": "MetlifeScraper",
    "taiyo": "TaiyoScraper",
    "pgf": "PGFScraper",
    "sonylife": "SonylifeScraper",
    "orix": "OrixScraper",
    "td_financial": "TDFinancialScraper",
    "manulife": "ManulifeScraper",
}

for company in get_enabled_companies():
    scraper_module = company.get("scraper", "")
    key = company["key"]

    if not scraper_module:
        continue

    cls_name = _CLASS_NAMES.get(scraper_module)
    if not cls_name:
        logger.warning(f"クラス名不明: scraper={scraper_module}, key={key}")
        continue

    try:
        mod = importlib.import_module(f".{scraper_module}", package="scrapers")
        cls = getattr(mod, cls_name)
        SCRAPER_MAP[key] = cls
    except Exception as e:
        logger.warning(f"スクレイパー読み込み失敗: {key} ({scraper_module}): {e}")

__all__ = ["SCRAPER_MAP"]
