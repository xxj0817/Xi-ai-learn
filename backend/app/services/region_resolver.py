"""地区与语言解析：决定是否提供本地搜索工具。"""

from __future__ import annotations

from dataclasses import dataclass

_COUNTRY_BY_REGION = {
    "CN": "china",
    "US": "united states",
    "GB": "united kingdom",
    "JP": "japan",
    "KR": "south korea",
    "SG": "singapore",
    "IN": "india",
    "DE": "germany",
    "FR": "france",
    "CA": "canada",
    "AU": "australia",
    "BR": "brazil",
    "RU": "russia",
    "IT": "italy",
    "ES": "spain",
    "NL": "netherlands",
    "SE": "sweden",
    "CH": "switzerland",
    "AE": "united arab emirates",
    "SA": "saudi arabia",
    "MX": "mexico",
    "ID": "indonesia",
    "TH": "thailand",
    "VN": "vietnam",
    "MY": "malaysia",
    "PH": "philippines",
    "TR": "turkey",
    "PL": "poland",
    "UA": "ukraine",
    "IL": "israel",
    "EG": "egypt",
    "ZA": "south africa",
    "AR": "argentina",
    "CL": "chile",
    "CO": "colombia",
    "PE": "peru",
    "NZ": "new zealand",
    "IE": "ireland",
    "PT": "portugal",
    "GR": "greece",
    "CZ": "czech republic",
    "AT": "austria",
    "BE": "belgium",
    "DK": "denmark",
    "NO": "norway",
    "FI": "finland",
}

_LANGUAGE_REGION = {
    "zh": "CN",
    "ja": "JP",
    "ko": "KR",
    "de": "DE",
    "fr": "FR",
    "es": "ES",
    "pt": "BR",
    "ru": "RU",
    "it": "IT",
    "nl": "NL",
    "tr": "TR",
    "ar": "SA",
    "hi": "IN",
    "th": "TH",
    "vi": "VN",
    "id": "ID",
    "ms": "MY",
}

_GLOBAL_VALUES = {"GLOBAL", "NONE", "WORLD", "ALL"}


@dataclass(frozen=True)
class RegionContext:
    locale: str
    country: str | None
    label: str


def _primary_language(value: str | None) -> str:
    if not value:
        return ""
    first = value.split(",", 1)[0].strip()
    return first.replace("_", "-").split("-", 1)[0].lower()


def _normalized_locale(value: str | None) -> str:
    if not value:
        return "unknown"
    return value.split(",", 1)[0].strip().replace("_", "-") or "unknown"


def _has_cjk(text: str) -> bool:
    cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    letters = sum(1 for char in text if char.isalpha())
    return cjk >= 2 and cjk / max(letters, 1) >= 0.1


def _context(region_code: str, locale: str) -> RegionContext:
    country = _COUNTRY_BY_REGION.get(region_code)
    if country is None:
        return RegionContext(locale=locale, country=None, label="全球")
    return RegionContext(
        locale=locale,
        country=country,
        label="中国" if region_code == "CN" else country,
    )


def resolve_region(
    *,
    region: str | None = None,
    locale: str | None = None,
    accept_language: str | None = None,
    user_input: str = "",
) -> RegionContext:
    normalized_locale = _normalized_locale(locale or accept_language)

    explicit_region = (region or "").strip().upper()
    if explicit_region:
        if explicit_region in _GLOBAL_VALUES:
            return RegionContext(locale=normalized_locale, country=None, label="全球")
        return _context(explicit_region, normalized_locale)

    language = _primary_language(locale) or _primary_language(accept_language)
    if language in _LANGUAGE_REGION:
        return _context(_LANGUAGE_REGION[language], normalized_locale)
    if language == "en":
        return RegionContext(locale=normalized_locale, country=None, label="全球")

    if _has_cjk(user_input):
        return RegionContext(locale="zh-CN", country="china", label="中国")

    return RegionContext(locale=normalized_locale, country=None, label="全球")
