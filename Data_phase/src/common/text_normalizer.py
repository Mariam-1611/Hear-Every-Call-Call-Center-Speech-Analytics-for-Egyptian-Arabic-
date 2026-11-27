"""Text normalization utilities for Egyptian Arabic and English code-switching.

This module changes transcript text only. It never decides that a record is
unintelligible or excludes it; those record-level decisions are explicit and
manual in configs/mgb3_manual_decisions.csv.
"""

import re
import unicodedata

# Arabic diacritics (Tashkeel), superscript alef, and Tatweel (kashida).
ARABIC_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")

# Eastern Arabic-Indic digits ٠-٩ to Western digits 0-9.
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_text(
    text: str,
    *,
    remove_ellipses: bool = False,
    normalize_taa_marbuta: bool = False,
    normalize_alef_maqsura: bool = False,
) -> str:
    """Create a derived text view using explicitly selected normalization rules.

    Defaults are conservative: ellipses, taa marbuta, and alef maqsura are
    retained. The source transcript is never modified. Optional rules allow
    later comparisons.
    """
    if not text or not isinstance(text, str):
        return ""

    text = text.strip()
    text = text.translate(ARABIC_INDIC_DIGITS)

    # Ellipses may mark pauses or incomplete speech. Keep them until reviewed.
    if remove_ellipses:
        text = re.sub(r"\.{2,}", " ", text)
        text = text.replace("…", " ")

    # Remove brackets, quotes, hyphens, and decorative symbols.
    text = re.sub(r"[_\(\)\[\]\{\}\<\>\"\'«»/\\~#@\$\%\^\&\*\+\=\|\-]", " ", text)
    text = ARABIC_DIACRITICS.sub("", text)

    # Normalize Alef variants in both profiles. Other spelling changes are
    # opt-in because they can affect training and WER.
    text = re.sub(r"[إأآٱ]", "ا", text)
    if normalize_taa_marbuta:
        text = re.sub(r"ة\b", "ه", text)
    if normalize_alef_maqsura:
        text = re.sub(r"ى\b", "ي", text)

    cleaned_chars = []
    for char in text:
        if char.isalpha() and "ARABIC" in unicodedata.name(char, ""):
            cleaned_chars.append(char)
        elif char.isascii() and char.isalpha():
            cleaned_chars.append(char.lower())
        elif char.isnumeric():
            cleaned_chars.append(char)
        elif char == ".":
            # Preserve periods/ellipses in the conservative profile. The
            # aggressive profile removes multi-dot ellipses before this loop.
            cleaned_chars.append(char)
        elif char.isspace() or char in ["،", "؟", "?"]:
            cleaned_chars.append(" ")
        else:
            cleaned_chars.append(" ")

    return re.sub(r"\s+", " ", "".join(cleaned_chars)).strip()
