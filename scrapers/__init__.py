from .sumitomo import SumitomoScraper
from .nissay import NissayScraper
from .nissay_wealth import NissayWealthScraper
from .taiju import TaijuScraper
from .meiji_yasuda import MeijiYasudaScraper
from .ms_primary import MSPrimaryScraper
from .metlife import MetlifeScraper
from .taiyo import TaiyoScraper
from .pgf import PGFScraper
from .sonylife import SonylifeScraper
from .orix import OrixScraper
from .td_financial import TDFinancialScraper
from .manulife import ManulifeScraper

SCRAPER_MAP = {
    "sumitomo": SumitomoScraper,
    "nissay": NissayScraper,
    "nissay-wealth": NissayWealthScraper,
    "taiju": TaijuScraper,
    "meiji-yasuda": MeijiYasudaScraper,
    "ms-primary": MSPrimaryScraper,
    "metlife": MetlifeScraper,
    "taiyo": TaiyoScraper,
    "pgf": PGFScraper,
    "sonylife": SonylifeScraper,
    "orix": OrixScraper,
    "td-financial": TDFinancialScraper,
    "manulife": ManulifeScraper,
}

__all__ = ["SCRAPER_MAP"]
