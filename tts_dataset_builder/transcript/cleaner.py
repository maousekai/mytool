"""
Text cleaner strictly respecting Vietnamese transcript content:
- Trim whitespace
- Remove double/consecutive spaces
- Unicode NFC normalization
- Fix whitespace before punctuation (e.g. " từ , " -> " từ, ")
- Remove HTML tags if present
- Preserves all Vietnamese diacritics, capitalization, proper nouns, and punctuation!
"""

import re
import unicodedata


def clean_vietnamese_text(raw_text: str) -> str:
    if not raw_text:
        return ""

    text = str(raw_text)

    # 1. Strip HTML tags (e.g. <font color="..."> or <i>)
    text = re.sub(r"<[^>]+>", "", text)

    # 2. Normalize Unicode NFC (critical for Vietnamese diacritics consistency)
    text = unicodedata.normalize("NFC", text)

    # 3. Replace various whitespace chars (non-breaking space, tabs, newlines) with standard space
    text = re.sub(r"[\r\n\t\u00a0\u200b\ufeff]+", " ", text)

    # 4. Remove space BEFORE common punctuation: . , ; : ! ? ) ] } " ”
    text = re.sub(r"\s+([.,;:!?\)\]\}\"”'’])", r"\1", text)

    # 5. Remove space AFTER opening punctuation: ( [ { “ ‘
    text = re.sub(r"([(\[{\“‘])\s+", r"\1", text)

    # 6. Collapse multiple consecutive spaces to a single space
    text = re.sub(r"\s{2,}", " ", text)

    # 7. Final trim
    return text.strip()
