"""Lightweight post-generation check: do the generated answer's numeric
claims actually appear in the context it was grounded on?

Heuristic and regex-based by design (not a second LLM call) -- cheap enough
to run on every turn. It can't tell whether a number was used *correctly*,
only whether it exists somewhere in the source, so a flag means "worth a
look," not "definitely wrong."
"""

import json
import re

_NUMBER_RE = re.compile(
    r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?"  # 12,345 or 12,345.6
    r"|(?<![\w.])\d+\.\d+"                     # 12.5
    r"|(?<![\w.])\d+[Kk]\+?"                   # 50K, 50k+
    r"|(?<![\w.])\d+(?![\w.])"                 # bare integer: 40, 12, 4
)


def _normalize(number_text: str) -> set[str]:
    """Equivalent plain-digit spellings of one matched number, so "50K" in
    the answer can match "50,000" in the source, or vice versa."""
    cleaned = number_text.replace(",", "")
    variants = {cleaned}
    k_form = re.fullmatch(r"(\d+)[Kk]\+?", cleaned)
    if k_form:
        variants.add(str(int(k_form.group(1)) * 1000))
    elif re.fullmatch(r"\d+", cleaned) and int(cleaned) >= 1000 and int(cleaned) % 1000 == 0:
        variants.add(f"{int(cleaned) // 1000}K")
        variants.add(f"{int(cleaned) // 1000}k")
    return variants


def find_ungrounded_numbers(answer: str, profile: dict, retrieved_context: list[dict]) -> list[str]:
    """Numbers in `answer` with no trace, in any normalized form, in the
    profile or retrieved excerpts actually used to generate it. Skips
    small counts (<4) and plausible years -- too common in ordinary prose
    to be a useful signal.
    """
    haystack = json.dumps(profile) + "\n" + "\n".join(
        chunk.get("content", "") for chunk in retrieved_context
    )
    haystack_variants: set[str] = set()
    for match in _NUMBER_RE.finditer(haystack):
        haystack_variants |= _normalize(match.group())

    flagged = []
    for match in _NUMBER_RE.finditer(answer):
        raw = match.group()
        cleaned = raw.replace(",", "")
        if re.fullmatch(r"\d+", cleaned):
            value = int(cleaned)
            if value < 4 or 1900 <= value <= 2100:
                continue
        if not (_normalize(raw) & haystack_variants):
            flagged.append(raw)
    return flagged
