"""
Simple keyword-based categorizer for emails.

This is plain substring/word matching (no AI call needed for it) — fast,
free, and predictable. Edit CATEGORY_KEYWORDS below any time to add,
remove, or rename categories/keywords; nothing else needs to change.
"""

import re
from enum import Enum


class EmailCategory(str, Enum):
    DOCUMENT_COMPARISON = "Document Comparison (SI/BL)"
    NEW_SI = "New SI Request"
    INVOICE_QUERY = "Invoice / Payment"
    GENERAL_MESSAGE = "General / Update"
    SPAM = "Spam"
    ADMIN_ESCALATION = "Admin Escalation"
    UNCATEGORIZED = "Uncategorized"


# NOTE: a couple of these lists were reconstructed from a photo of your code
# that got cut off on the right edge, so I filled in a few reasonable-looking
# extra keywords (marked below) — please skim through and adjust as needed.
CATEGORY_KEYWORDS = {
    EmailCategory.DOCUMENT_COMPARISON: [
        "bill of lading", "bl", "b/l", "shipping instruction",
        "si vs bl", "si/bl", "compare", "comparison",
        "verify", "match", "discrepancy", "mismatch",  # <- filled in, please check
    ],
    EmailCategory.NEW_SI: [
        "new si", "prepare si", "shipping instruction template",
        "submit si", "si draft", "si request",  # <- filled in, please check
    ],
    EmailCategory.INVOICE_QUERY: [
        "invoice", "bill", "payment", "charge", "cost",
        "fee", "amount due", "receipt",  # <- filled in, please check
    ],
    EmailCategory.GENERAL_MESSAGE: [
        "update", "notice", "info", "schedule", "operations",
        "announcement", "reminder",  # <- filled in, please check
    ],
    EmailCategory.SPAM: [
        "win", "lottery", "crypto", "free", "discount",
        "click here", "prize", "congratulations",  # <- filled in, please check
    ],
}


def _contains_keyword(text, keyword):
    """Word-boundary match so short keywords like 'bl' or 'si' don't match
    inside unrelated words (e.g. 'bl' inside 'trouble', 'si' inside 'using').
    Multi-word phrases like 'bill of lading' still match as a phrase."""
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return re.search(pattern, text) is not None


def categorize_email(email):
    """Return a list of category labels (strings) that match this email.

    If the email already carries a "source_category" (e.g. it came from
    your teammate's classifier via friend_client.py), that's used as-is —
    no need to re-derive it from keywords, and it avoids the two
    categorizers ever disagreeing on the same email.

    Otherwise, falls back to keyword matching. An email can match more
    than one category this way; if nothing matches, falls back to
    EmailCategory.UNCATEGORIZED.value."""
    if email.get("source_category"):
        return [email["source_category"]]

    text = f"{email.get('subject', '')} {email.get('content', '')}".lower()

    matched = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(_contains_keyword(text, kw) for kw in keywords):
            matched.append(category.value)

    return matched or [EmailCategory.UNCATEGORIZED.value]
