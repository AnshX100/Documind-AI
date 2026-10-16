"""Intent Detection Service for classification of financial questions and entity extraction."""

import re
from typing import Dict, Any, Optional, List


class IntentDetectionService:
    """Service to perform rule-based deterministic intent classification and entity extraction."""

    KNOWN_CATEGORIES = [
        "Travel",
        "Food & Dining",
        "Office Supplies",
        "Utilities",
        "Marketing",
        "Software & Subscriptions",
        "General",
        "Professional Services",
        "Equipment",
        "Healthcare",
        "Logistics"
    ]

    CATEGORY_ALIASES = {
        "travel": "Travel",
        "flight": "Travel",
        "flights": "Travel",
        "hotel": "Travel",
        "lodging": "Travel",
        "taxi": "Travel",
        "cab": "Travel",
        "food": "Food & Dining",
        "dining": "Food & Dining",
        "restaurant": "Food & Dining",
        "meals": "Food & Dining",
        "lunch": "Food & Dining",
        "dinner": "Food & Dining",
        "office": "Office Supplies",
        "supplies": "Office Supplies",
        "paper": "Office Supplies",
        "stationery": "Office Supplies",
        "utility": "Utilities",
        "utilities": "Utilities",
        "electricity": "Utilities",
        "water": "Utilities",
        "internet": "Utilities",
        "marketing": "Marketing",
        "ads": "Marketing",
        "advertising": "Marketing",
        "software": "Software & Subscriptions",
        "saas": "Software & Subscriptions",
        "subscription": "Software & Subscriptions",
        "subscriptions": "Software & Subscriptions",
        "general": "General",
        "miscellaneous": "General"
    }

    def detect_intent(self, question: str) -> Dict[str, Any]:
        """Classify question into intent and extract entities.

        Args:
            question (str): User natural language question.

        Returns:
            Dict[str, Any]: Dict containing intent, entities, and confidence score.
        """
        if not question or not question.strip():
            return {
                "intent": "UNKNOWN",
                "entities": {"category": None, "document_reference": None, "time_period": None},
                "confidence": 0.0
            }

        text = question.strip()
        text_lower = text.lower()

        # Extract entities first
        entities = {
            "category": self._extract_category(text_lower),
            "document_reference": self._extract_document_reference(text),
            "time_period": self._extract_time_period(text_lower)
        }

        # Rule matching for intents (ordered from specific to general)

        # 1. Document Risk
        if (re.search(r'\b(why|reason|explain|risk|flag|flagged|warn|warning)\b', text_lower) and 
            (entities["document_reference"] is not None or re.search(r'\b(invoice|receipt|document|doc)\b', text_lower))):
            return {
                "intent": "DOCUMENT_RISK",
                "entities": entities,
                "confidence": 0.95 if entities["document_reference"] else 0.80
            }

        # 2. Document Lookup
        if (re.search(r'\b(lookup|show|find|get|details?|view|fetch)\b', text_lower) and 
            entities["document_reference"] is not None):
            return {
                "intent": "DOCUMENT_LOOKUP",
                "entities": entities,
                "confidence": 0.95
            }

        # 3. Duplicate Documents
        if re.search(r'\b(duplicate|duplicates|duplicated|repeated|double billed)\b', text_lower):
            return {
                "intent": "DUPLICATE_DOCUMENTS",
                "entities": entities,
                "confidence": 0.95
            }

        # 4. Anomalies / Risk signals
        if re.search(r'\b(anomal|anomalies|unusual|suspicious|weird|spike|flagged|high expense|irregular)\b', text_lower):
            return {
                "intent": "ANOMALIES",
                "entities": entities,
                "confidence": 0.95
            }

        # 5. Due Diligence / Financial Health
        if re.search(r'\b(due diligence|health|healthy|audit|score|risk profile|diligence|stability)\b', text_lower):
            return {
                "intent": "DUE_DILIGENCE",
                "entities": entities,
                "confidence": 0.95
            }

        # 6. Tax Summary
        if re.search(r'\b(tax|taxes|vat|gst|taxation|effective tax)\b', text_lower):
            return {
                "intent": "TAX_SUMMARY",
                "entities": entities,
                "confidence": 0.95
            }

        # 7. Payment Method Summary
        if re.search(r'\b(payment method|payment methods|pay method|paid with|card vs cash|credit card|cash|bank transfer)\b', text_lower):
            return {
                "intent": "PAYMENT_METHOD_SUMMARY",
                "entities": entities,
                "confidence": 0.95
            }

        # 8. Category Spending
        if entities["category"] is not None or re.search(r'\b(category|categories|by category|spending on|spent on)\b', text_lower):
            return {
                "intent": "CATEGORY_SPENDING",
                "entities": entities,
                "confidence": 0.95 if entities["category"] else 0.85
            }

        # 9. Top Vendors vs Top Vendor
        if re.search(r'\b(top vendors|list vendors|all vendors|biggest vendors|largest vendors|highest suppliers)\b', text_lower):
            return {
                "intent": "TOP_VENDORS",
                "entities": entities,
                "confidence": 0.95
            }
        if re.search(r'\b(top vendor|most money|highest vendor|biggest vendor|highest spending vendor|main vendor|largest vendor|vendor received)\b', text_lower):
            return {
                "intent": "TOP_VENDOR",
                "entities": entities,
                "confidence": 0.95
            }

        # 10. Month Comparison
        if re.search(r'\b(compare|comparison|versus|vs|month over month|mom|change from last month|this month with last month)\b', text_lower):
            return {
                "intent": "MONTH_COMPARISON",
                "entities": entities,
                "confidence": 0.95
            }

        # 11. Spending Trend
        if re.search(r'\b(trend|trends|monthly pattern|spending pattern|over time|history|history pattern|pattern)\b', text_lower):
            return {
                "intent": "SPENDING_TREND",
                "entities": entities,
                "confidence": 0.95
            }

        # 12. General Financial Summary
        if re.search(r'\b(summary|overview|executive summary|workspace summary|state of finance|financial state)\b', text_lower):
            return {
                "intent": "GENERAL_FINANCIAL_SUMMARY",
                "entities": entities,
                "confidence": 0.90
            }

        # 13. Total Spending
        if re.search(r'\b(how much|total spend|total spending|total expenses|overall spending|how much did i spend|total cost|spent in total)\b', text_lower):
            return {
                "intent": "TOTAL_SPENDING",
                "entities": entities,
                "confidence": 0.95
            }

        # Fallback keyword match if general spend question
        if "spend" in text_lower or "expense" in text_lower or "cost" in text_lower:
            return {
                "intent": "TOTAL_SPENDING",
                "entities": entities,
                "confidence": 0.70
            }

        return {
            "intent": "UNKNOWN",
            "entities": entities,
            "confidence": 0.40
        }

    def _extract_category(self, text_lower: str) -> Optional[str]:
        """Extract matched financial category from text."""
        # Direct check against known categories (case-insensitive)
        for cat in self.KNOWN_CATEGORIES:
            if cat.lower() in text_lower:
                return cat

        # Check aliases
        for kw, cat in self.CATEGORY_ALIASES.items():
            if re.search(rf'\b{re.escape(kw)}\b', text_lower):
                return cat

        return None

    def _extract_document_reference(self, text: str) -> Optional[str]:
        """Extract invoice number or document ID reference."""
        # Pattern 1: Invoice numbers like INV-1044, REC-2026-01
        match = re.search(r'\b([A-Z]{2,5}-?[0-9A-Z]{2,10})\b', text)
        if match:
            ref = match.group(1)
            if ref.upper() not in ["PDF", "PNG", "JPG", "WEBP", "DOCX", "HIGH", "MEDIUM", "LOW", "TOTAL"]:
                return ref

        # Pattern 2: Explicit invoice/doc/receipt #123 or INV 123
        match = re.search(r'\b(?:invoice|doc|document|receipt|ref|#)\s*:?\s*#?([A-Za-z0-9_\-]+)\b', text, re.IGNORECASE)
        if match:
            return match.group(1)

        # Pattern 3: Number after document or invoice
        match = re.search(r'\b(?:invoice|doc|document|receipt)\s+([0-9]+)\b', text, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def _extract_time_period(self, text_lower: str) -> Optional[str]:
        """Extract time period specification."""
        if "this month" in text_lower:
            return "this_month"
        if "last month" in text_lower:
            return "last_month"
        if "this year" in text_lower:
            return "this_year"
        if "last year" in text_lower:
            return "last_year"
        if "today" in text_lower:
            return "today"
        if "30 days" in text_lower or "30d" in text_lower:
            return "30d"
        if "3 months" in text_lower or "3m" in text_lower:
            return "3m"
        if "6 months" in text_lower or "6m" in text_lower:
            return "6m"
        if "12 months" in text_lower or "12m" in text_lower:
            return "12m"
        return None
