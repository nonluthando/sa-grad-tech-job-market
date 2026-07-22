"""Explainable, deterministic job and location classifications."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from src.transformation.cleaning import normalize_whitespace, unique_strings


@dataclass(frozen=True)
class LocationClassification:
    city: str | None
    province: str | None
    country: str | None
    is_south_africa: bool
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class LabelClassification:
    label: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class TechnologyClassification:
    is_technology_role: bool
    evidence: tuple[str, ...]


_CITY_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Cape Town", "Western Cape", (r"\bcape\s*town\b", r"\bcapetown\b", r"\bcpt\b")),
    ("Stellenbosch", "Western Cape", (r"\bstellenbosch\b",)),
    ("Johannesburg", "Gauteng", (r"\bjohannesburg\b", r"\bjhb\b", r"\bsandton\b", r"\brosebank\b", r"\brandburg\b", r"\bmidrand\b")),
    ("Pretoria", "Gauteng", (r"\bpretoria\b", r"\bpta\b")),
    ("Centurion", "Gauteng", (r"\bcenturion\b",)),
    ("Durban", "KwaZulu-Natal", (r"\bdurban\b", r"\bdbn\b", r"\bumhlanga\b")),
    ("Gqeberha", "Eastern Cape", (r"\bgqeberha\b", r"\bport\s+elizabeth\b")),
    ("Bloemfontein", "Free State", (r"\bbloemfontein\b",)),
)

_COUNTRY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("South Africa", (r"\bsouth\s+africa\b", r"\bza\b")),
    ("United Kingdom", (r"\bunited\s+kingdom\b", r"\buk\b", r"\bengland\b", r"\bscotland\b")),
    ("United States", (r"\bunited\s+states\b", r"\busa\b", r"\bu\.s\.a?\.?\b")),
    ("Portugal", (r"\bportugal\b",)),
    ("Netherlands", (r"\bnetherlands\b",)),
    ("Germany", (r"\bgermany\b",)),
    ("Ireland", (r"\bireland\b",)),
    ("Canada", (r"\bcanada\b",)),
    ("Australia", (r"\baustralia\b",)),
    ("Singapore", (r"\bsingapore\b",)),
    ("Malaysia", (r"\bmalaysia\b",)),
    ("India", (r"\bindia\b",)),
    ("Nigeria", (r"\bnigeria\b",)),
    ("Kenya", (r"\bkenya\b",)),
    ("Spain", (r"\bspain\b",)),
    ("France", (r"\bfrance\b",)),
)

_REMOTE_SOUTH_AFRICA_PATTERNS = (
    r"remote\s+(?:within|in|from)\s+south\s+africa",
    r"based\s+in\s+south\s+africa",
    r"south\s+africa[- ]based",
    r"candidates?\s+(?:must\s+be\s+)?(?:located|based)\s+in\s+south\s+africa",
)

_ROLE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("internship", (r"\bintern(?:ship)?\b", r"\bvacation\s+work\b", r"\blearnership\b", r"\bapprentice(?:ship)?\b")),
    ("graduate", (r"\bgraduate\b", r"\bnew\s+grad\b", r"\bgrad\s+programme\b", r"\bgrad\s+program\b")),
    (
        "junior",
        (
            r"\bjunior\b",
            r"\bentry[- ]level\b",
            r"\bassociate\s+(?:software|data|qa|test|cloud|devops|security|business\s+intelligence)\b",
            r"\b(?:software|data|qa|test|cloud|devops|security)\s+engineer\s+i\b",
            r"\b(?:software|web|backend|front[- ]?end|full[- ]?stack)\s+developer\s+i\b",
        ),
    ),
    (
        "senior",
        (
            r"\bsenior\b",
            r"\bstaff\b",
            r"\bprincipal\b",
            r"\blead\b",
            r"\bmanager\b",
            r"\bdirector\b",
            r"\bhead\s+of\b",
            r"\barchitect\b",
            r"\bvice\s+president\b",
            r"\bvp\b",
            r"\bchief\b",
        ),
    ),
)

_DESCRIPTION_LEVEL_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("internship", (r"\bthis\s+internship\b", r"\binternship\s+programme\b")),
    ("graduate", (r"\bgraduate\s+programme\b", r"\bgraduate\s+program\b", r"\bnew\s+graduate\b")),
    ("junior", (r"\bentry[- ]level\s+(?:role|position|opportunity)\b", r"\b0\s*(?:-|to)\s*2\s+years?\b")),
)

_TECH_TITLE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("software", (r"\bsoftware\b", r"\bapplication\s+development\b")),
    (
        "developer",
        (
            r"\bdeveloper\b",
            r"\bfront[- ]?end\b",
            r"\bback[- ]?end\b",
            r"\bfull[- ]?stack\b",
            r"\bweb\s+development\b",
            r"\bmobile\b",
            r"\bandroid\s+engineer\b",
            r"\bios\s+engineer\b",
        ),
    ),
    (
        "data",
        (
            r"\bdata\s+(?:analyst|analytics|engineer|engineering|scientist|science|platform|warehouse|lead)\b",
            r"\banalytics?\b",
            r"\bdatabase\s+administrator\b",
        ),
    ),
    (
        "ai_ml",
        (
            r"\bmachine\s+learning\b",
            r"\bartificial\s+intelligence\b",
            r"\bai\s+engineer\b",
            r"\bml\s+engineer\b",
            r"\bgenai\b",
            r"\bapplied\s+ai\b",
        ),
    ),
    ("automation", (r"\bautomation\b", r"\brpa\b")),
    ("security", (r"\bcyber(?:security)?\b", r"\binformation\s+security\b", r"\bsecurity\s+(?:analyst|engineer|operations)\b")),
    ("cloud_devops", (r"\bcloud\b", r"\bdevops\b", r"\bsite\s+reliability\b", r"\bsre\b", r"\bplatform\s+engineer\b")),
    ("quality_engineering", (r"\bquality\s+assurance\b", r"\bqa\b", r"\btest\s+(?:engineer|automation|analyst)\b")),
    ("business_intelligence", (r"\bbusiness\s+intelligence\b", r"\bbi\s+(?:analyst|developer|engineer)\b")),
    (
        "systems",
        (
            r"\bsystems?\s+(?:analyst|engineer)\b",
            r"\b(?:integration|implementation|solutions?|support)\s+engineer\b",
            r"\btechnical\s+services?\s+engineer\b",
            r"\bit\s+(?:analyst|support|engineer|technician|auditor)\b",
            r"\binformation\s+technology\b",
            r"\bblockchain\b",
        ),
    ),
    ("business_analysis", (r"\bbusiness\s+analyst\b",)),
    ("product", (r"\bproduct\s+manager\b", r"\btechnical\s+product\b")),
)

_GENERIC_EARLY_CAREER = re.compile(
    r"\b(?:graduate|intern(?:ship)?|junior|entry[- ]level|learnership|apprentice(?:ship)?)\b",
    re.IGNORECASE,
)

_DESCRIPTION_TECH_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("software_engineering", (r"\bsoftware\s+(?:engineering|development)\b",)),
    ("programming", (r"\bprogramming\b", r"\bcoding\b")),
    ("data", (r"\bdata\s+(?:analytics|engineering|science)\b",)),
    ("cloud_devops", (r"\bcloud\s+(?:engineering|platform|infrastructure)\b", r"\bdevops\b")),
    ("security", (r"\bcybersecurity\b", r"\binformation\s+security\b")),
)

_TECH_FALSE_POSITIVES = (
    r"\bdata\s+(?:capturer|capture|clerk|privacy|protection)\b",
    r"\bsoftware\s+sales\b",
    r"\btechnical\s+recruit(?:er|ment)\b",
)

_WORKPLACE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("hybrid", (r"\bhybrid\b", r"\bflexible\s+hybrid\b")),
    ("remote", (r"\bremote\b", r"\bwork\s+from\s+home\b", r"\bfully\s+distributed\b")),
    ("on_site", (r"\bon[- ]?site\b", r"\boffice[- ]based\b", r"\bin[- ]office\b")),
)


def _match_rules(text: str, patterns: Iterable[str]) -> tuple[str, ...]:
    return unique_strings(
        match.group(0)
        for pattern in patterns
        for match in re.finditer(pattern, text, flags=re.IGNORECASE)
    )


def classify_location(location_raw: str, description_text: str = "") -> LocationClassification:
    """Normalise location evidence without guessing unsupported cities."""

    location_text = normalize_whitespace(location_raw)
    city: str | None = None
    province: str | None = None
    country: str | None = None
    evidence: list[str] = []

    for canonical_city, canonical_province, patterns in _CITY_RULES:
        matches = _match_rules(location_text, patterns)
        if matches:
            city = canonical_city
            province = canonical_province
            country = "South Africa"
            evidence.extend(matches)
            break

    if country is None:
        for canonical_country, patterns in _COUNTRY_RULES:
            matches = _match_rules(location_text, patterns)
            if matches:
                country = canonical_country
                evidence.extend(matches)
                break

    if country is None and _match_rules(description_text, _REMOTE_SOUTH_AFRICA_PATTERNS):
        country = "South Africa"
        evidence.extend(_match_rules(description_text, _REMOTE_SOUTH_AFRICA_PATTERNS))

    if city is None and country and "," in location_text:
        first_segment = normalize_whitespace(location_text.split(",", maxsplit=1)[0])
        if first_segment and not re.search(r"\bremote\b", first_segment, re.IGNORECASE):
            city = first_segment

    return LocationClassification(
        city=city,
        province=province,
        country=country,
        is_south_africa=country == "South Africa",
        evidence=unique_strings(evidence),
    )


def classify_workplace(title: str, location_raw: str, description_text: str) -> LabelClassification:
    """Classify workplace type, preferring explicit hybrid evidence."""

    combined_text = " ".join((title, location_raw, description_text))
    for label, patterns in _WORKPLACE_RULES:
        matches = _match_rules(combined_text, patterns)
        if matches:
            return LabelClassification(label=label, evidence=matches)
    return LabelClassification(label="unspecified", evidence=())


def classify_role_level(title: str, description_text: str) -> LabelClassification:
    """Classify advertised seniority using title-first deterministic rules."""

    for label, patterns in _ROLE_RULES:
        matches = _match_rules(title, patterns)
        if matches:
            return LabelClassification(label=label, evidence=matches)

    for label, patterns in _DESCRIPTION_LEVEL_RULES:
        matches = _match_rules(description_text, patterns)
        if matches:
            return LabelClassification(label=label, evidence=matches)

    return LabelClassification(label="unspecified", evidence=())


def classify_technology_role(
    title: str,
    department: str | None,
    description_text: str,
) -> TechnologyClassification:
    """Classify technology roles and retain the evidence behind the result."""

    if _match_rules(title, _TECH_FALSE_POSITIVES):
        return TechnologyClassification(is_technology_role=False, evidence=())

    evidence: list[str] = []
    for label, patterns in _TECH_TITLE_RULES:
        matches = _match_rules(title, patterns)
        if matches:
            evidence.append(label)
            evidence.extend(matches)

    if evidence:
        return TechnologyClassification(
            is_technology_role=True,
            evidence=unique_strings(evidence),
        )

    if _GENERIC_EARLY_CAREER.search(title):
        supporting_text = " ".join(
            value for value in (department or "", description_text) if value
        )
        for label, patterns in _DESCRIPTION_TECH_RULES:
            matches = _match_rules(supporting_text, patterns)
            if matches:
                evidence.append(label)
                evidence.extend(matches)

    return TechnologyClassification(
        is_technology_role=bool(evidence),
        evidence=unique_strings(evidence),
    )
