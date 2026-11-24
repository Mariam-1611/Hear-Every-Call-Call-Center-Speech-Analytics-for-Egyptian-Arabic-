"""Check conservative and optional MGB-3 text-normalization rules."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.common.text_normalizer import normalize_text


def run_tests():
    # Conservative defaults preserve the disputed forms.
    assert normalize_text("... مدرسة فتى") == "... مدرسة فتى"
    assert normalize_text("خليني اسميها غير واضح") == "خليني اسميها غير واضح"

    # Optional aggressive rules make those choices explicit and comparable.
    aggressive = normalize_text(
        "... مدرسة فتى",
        remove_ellipses=True,
        normalize_taa_marbuta=True,
        normalize_alef_maqsura=True,
    )
    assert aggressive == "مدرسه فتي"

    # Stable normalization rules still apply to both profiles.
    assert normalize_text("إحنا عندنا ٦") == "احنا عندنا 6"
    assert normalize_text("Hey, pink") == "hey pink"
    print("Normalization examples passed.")


if __name__ == "__main__":
    run_tests()
