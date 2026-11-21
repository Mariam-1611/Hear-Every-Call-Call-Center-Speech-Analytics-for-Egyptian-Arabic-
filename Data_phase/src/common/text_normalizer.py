"""
Text Normalization Module for Egyptian Arabic and English Code-Switching.

Key Capabilities:
1. Inaudible detection: Flags/excludes non-lexical audio annotations ('غير واضح').
2. Acoustic hesitation removal: Strips repeated dots/ellipses ('...', '…') representing pauses.
3. Arabic orthographic normalization: Unifies Alef variants, Taa Marbuta, and Yaa.
4. Diacritic removal: Strips all Arabic Tashkeel marks and Tatweel (kashida).
5. Code-switching preservation: Retains all ASCII Latin characters (a-z) in lowercase.
6. Numeral standardization: Maps Eastern Arabic-Indic digits (٠-٩) to Western Arabic digits (0-9).
"""

import re
import unicodedata

# Matches all Arabic diacritics (Tashkeel: Fathatan, Dammatan, Kasratan, Fatha,
# Damma, Kasra, Shadda, Sukun, Superscript Alef) and Tatweel (ـ)
ARABIC_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")

# Mapping table to convert Eastern Arabic-Indic digits (٠-٩) to standard digits (0-9)
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Pattern matching inaudible / unintelligible transcriber markers
INAUDIBLE_PATTERNS = re.compile(r"(_?غير\s+واضح|\[غير واضح\]|\(غير واضح\))")


def contains_inaudible_tag(text: str) -> bool:
    """
    Check if a transcript contains an inaudible marker ('غير واضح').
    Used to filter out corrupted audio-text alignment records before training.
    """
    if not text or not isinstance(text, str):
        return False
    return bool(INAUDIBLE_PATTERNS.search(text))


def normalize_text(text: str) -> str:
    """
    Apply model-agnostic text normalization for bilingual Egyptian Arabic / English speech:
    - Removes non-lexical acoustic pauses (...).
    - Unifies Arabic character variants.
    - Preserves English code-switching vocabulary in lowercase.
    - Strips noisy punctuation and special characters.
    """
    if not text or not isinstance(text, str):
        return ""

    text = text.strip()

    # Step 1: Standardize Eastern Arabic-Indic numerals to 0-9
    text = text.translate(ARABIC_INDIC_DIGITS)

    # Step 2: Replace multi-dot ellipses and pauses with whitespace
    text = re.sub(r"\.{2,}", " ", text)
    text = text.replace("…", " ")

    # Step 3: Remove brackets, quotes, hyphens, and decorative symbols
    text = re.sub(r"[_\(\)\[\]\{\}\<\>\"\'«»/\\~#@\$\%\^\&\*\+\=\|\-]", " ", text)

    # Step 4: Strip Arabic diacritics (Tashkeel) and Tatweel
    text = ARABIC_DIACRITICS.sub("", text)

    # Step 5: Unify Arabic letter variants (Orthographic normalization)
    text = re.sub(r"[إأآٱ]", "ا", text)  # Unify all Alef variants to bare Alef
    text = re.sub(r"ة\b", "ه", text)     # Unify word-final Taa Marbuta to Haa
    text = re.sub(r"ى\b", "ي", text)     # Unify Alef Maqsura to Yaa

    # Step 6: Character-level filtering:
    # Retain Arabic characters, ASCII Latin characters (lowercased), digits, and spaces
    cleaned_chars = []
    for char in text:
        if char.isalpha() and "ARABIC" in unicodedata.name(char, ""):
            cleaned_chars.append(char)
        elif char.isascii() and char.isalpha():
            cleaned_chars.append(char.lower()) # Enforce lowercase on English words
        elif char.isnumeric():
            cleaned_chars.append(char)
        elif char.isspace() or char in [".", "،", "؟", "?"]:
            # Convert single punctuation to space to keep clean lexical tokens
            cleaned_chars.append(" ")
        else:
            cleaned_chars.append(" ")

    text = "".join(cleaned_chars)

    # Step 7: Collapse redundant whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text