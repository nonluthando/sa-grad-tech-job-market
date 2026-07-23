"""Regex patterns and weights for role-level evidence."""

from __future__ import annotations

TITLE_RULES: tuple[tuple[str, int, str, tuple[str, ...]], ...] = (
    ("internship", 15, "internship", (
        r"\bintern(?:ship)?\b",
        r"\bvacation\s+work\b",
        r"\blearnership\b",
        r"\bapprentice(?:ship)?\b",
    )),
    ("graduate", 15, "graduate", (
        r"\bgraduate\b",
        r"\bnew\s+grad\b",
        r"\bgrad(?:uate)?\s+programme\b",
        r"\bgrad(?:uate)?\s+program\b",
    )),
    ("junior", 10, "junior", (
        r"\bjunior\b",
        r"\bentry[- ]level\b",
        r"\btrainee\b",
    )),
    ("associate", 6, "junior", (r"\bassociate\b",)),
    ("engineer_i", 6, "junior", (
        r"\b(?:engineer|developer|analyst)\s+i\b",
        r"\b(?:engineer|developer|analyst)\s+1\b",
    )),
    ("level_ii", -2, "mid_level", (
        r"\b(?:engineer|developer|analyst)\s+ii\b",
        r"\b(?:engineer|developer|analyst)\s+2\b",
    )),
    ("senior", -20, "senior", (r"\bsenior\b",)),
    ("staff", -24, "senior", (r"\bstaff\b",)),
    ("principal", -28, "senior", (r"\bprincipal\b",)),
    ("lead", -24, "senior", (r"\blead\b",)),
    ("manager", -22, "senior", (r"\bmanager\b",)),
    ("director", -28, "senior", (r"\bdirector\b",)),
    ("head", -28, "senior", (r"\bhead\s+of\b",)),
    ("architect", -22, "senior", (r"\barchitect\b",)),
    ("executive", -30, "senior", (
        r"\bvice\s+president\b",
        r"\bvp\b",
        r"\bchief\b",
    )),
)

EXPLICIT_LEVEL_RULES: tuple[tuple[str, int, str, tuple[str, ...]], ...] = (
    ("internship", 15, "internship", (r"\bintern(?:ship)?\b",)),
    ("graduate", 15, "graduate", (r"\bgraduate\b", r"\bnew\s+grad\b")),
    ("junior", 10, "junior", (r"\bjunior\b", r"\bentry[- ]level\b")),
    ("mid_level", -3, "mid_level", (r"\bmid(?:dle)?[- ]level\b", r"\bintermediate\b")),
    ("senior", -20, "senior", (
        r"\bsenior\b",
        r"\blead\b",
        r"\bprincipal\b",
        r"\bmanager\b",
    )),
)

DESCRIPTION_TEXT_RULES: tuple[tuple[str, int, str, tuple[str, ...]], ...] = (
    ("no_experience", 7, "junior", (
        r"\bno\s+(?:(?:prior|professional)\s+)*experience\s+(?:is\s+)?(?:required|necessary)\b",
        r"\bno\s+prior\s+(?:work\s+)?experience\b",
    )),
    ("recent_graduate", 12, "graduate", (
        r"\brecent\s+graduate\b",
        r"\bfresh\s+graduate\b",
        r"\bnew\s+graduate\b",
    )),
    ("early_career", 8, "junior", (
        r"\bearly[- ]career\b",
        r"\bentry[- ]level\b",
    )),
)

TALENT_POOL_PATTERNS: tuple[str, ...] = (
    r"\btalent\s+pool\b",
    r"\btalent\s+community\b",
    r"\bexpression\s+of\s+interest\b",
    r"\bfuture\s+opportunit(?:y|ies)\b",
)
