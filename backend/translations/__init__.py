from typing import Dict

from .en import TRANSLATIONS as EN_TRANSLATIONS
from .ja import TRANSLATIONS as JA_TRANSLATIONS
from .zh_cn import TRANSLATIONS as ZH_CN_TRANSLATIONS

SUPPORTED_LANGUAGES: Dict[str, Dict[str, str]] = {
    "zh-CN": ZH_CN_TRANSLATIONS,
    "en": EN_TRANSLATIONS,
    "ja": JA_TRANSLATIONS,
}

DEFAULT_LANGUAGE = "zh-CN"

__all__ = ["DEFAULT_LANGUAGE", "SUPPORTED_LANGUAGES"]
