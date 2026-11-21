"""
Unit test script to verify normalization rules against actual MGB-3 dataset samples.
"""

import sys
from pathlib import Path

# Add project root to Python search path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.common.text_normalizer import contains_inaudible_tag, normalize_text


def run_tests():
    print("==================================================")
    print(" Running Unit Tests on MGB-3 Real Dataset Samples")
    print("==================================================")

    test_cases = [
        # Case 1: Ellipses, hesitation dots, and English code-switching
        (
            "... ... iam so sorry أنا جاكي اللي هعمل معاك الانترفيو ...",
            "iam so sorry انا جاكي اللي هعمل معاك الانترفيو",
            "Remove ellipses + lowercase English + unify Alef variants"
        ),
        # Case 2: Mixed casing and punctuation
        (
            "Hey إزاي حضرتك ... تمام مستر فرحات اوكيه ... pink ...",
            "hey ازاي حضرتك تمام مستر فرحات اوكيه pink",
            "Preserve English loanwords 'hey' and 'pink' in lowercase"
        ),
        # Case 3: Parentheses, diacritics, and technical English terminology
        (
            "(Nuclear Physicsأو الهندس ال ال الفيزياء النَّوَوِيَّة)",
            "nuclear physicsاو الهندس ال ال الفيزياء النوويه",
            "Strip brackets and Tashkeel + lowercase technical English terms"
        ),
        # Case 4: Eastern Arabic digits and Fathatan tanween
        (
            "عنده بنت عندها ٦ سنين ... شكراً جزيلاً",
            "عنده بنت عندها 6 سنين شكرا جزيلا",
            "Standardize digits to 0-9 and remove Tashkeel"
        )
    ]

    for idx, (raw, expected, description) in enumerate(test_cases, 1):
        result = normalize_text(raw)
        assert result == expected, (
            f"\n[FAILED] Test {idx} ({description}):\n"
            f"Got     : '{result}'\n"
            f"Expected: '{expected}'"
        )
        print(f"[PASS] Test {idx}: {description}")
        print(f"       In : {raw}")
        print(f"       Out: {result}\n")

    # Inaudible tag detection tests
    print("--- Testing Inaudible Marker Detection ---")
    inaudible_cases = [
        ("لا _غير واضح ... حضرتك عايز تقول حاجة", True),
        ("خليني اسميها غير واضح وأصبح ده عبارة عن", True),
        ("حضرتك عايز تقول حاجة مستر فيكتور", False)
    ]

    for text, should_detect in inaudible_cases:
        detected = contains_inaudible_tag(text)
        assert detected == should_detect, f"Failed inaudible detection for: '{text}'"
        status = "Correctly detected" if detected else "Correctly passed"
        print(f"[PASS] {status}: '{text}'")

    print("\n==================================================")
    print(" All unit tests passed! Normalization verified.")
    print("==================================================")


if __name__ == "__main__":
    run_tests()