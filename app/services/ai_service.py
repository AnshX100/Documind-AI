"""AI Service for financial entity extraction and summarization."""

import os
import re
import json
import logging
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

class AIService:
    """Service to extract structured financial data from raw OCR text."""

    def __init__(
        self, 
        provider: str = "none", 
        openai_api_key: Optional[str] = None, 
        model: str = "gpt-4o-mini"
    ):
        self.provider = provider.lower()
        self.openai_api_key = openai_api_key
        self.model = model

    def extract_financial_data(self, raw_text: str) -> Dict[str, Any]:
        """
        Extract financial entities from text using LLM or local fallback.
        """
        if not raw_text or not raw_text.strip():
            return self._empty_result()

        result = None
        
        # Try LLM if configured
        if self.provider == "openai" and self.openai_api_key:
            try:
                result = self._extract_with_openai(raw_text)
                if self._is_valid_result(result):
                    return result
            except Exception as e:
                logger.warning(f"LLM extraction failed, falling back to local: {e}")

        # Fallback to local heuristic parser
        return self._extract_with_heuristics(raw_text)

    def _extract_with_heuristics(self, text: str) -> Dict[str, Any]:
        """Local regex-based heuristic parser for financial documents."""
        result = self._empty_result()
        
        # 1. Invoice Number
        inv_match = re.search(r'(?:Invoice Number|Invoice No|Invoice #|Bill Number|Bill No|Invoice|Bill)\s*[:#\.-]?\s*([A-Z0-9-]+)', text, re.IGNORECASE)
        if inv_match:
            result["invoice_number"] = inv_match.group(1).strip()

        # 2. Date
        date_match = re.search(r'(?:Invoice Date|Bill Date|Date Issued|Issued|Date)\s*[:]?\s*([A-Za-z0-9\s/,.-]+?)(?:\n|$)', text, re.IGNORECASE)
        if date_match:
            parsed_date = self._parse_date(date_match.group(1).strip())
            if parsed_date:
                result["invoice_date"] = parsed_date

        # 3. Vendor
        vendor_match = re.search(r'(?:From|Vendor|Seller|Company)\s*:\s*(.+)(?:\n|$)', text, re.IGNORECASE)
        if vendor_match:
            result["vendor_name"] = vendor_match.group(1).strip()
        else:
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if lines and lines[0].lower() not in ['invoice', 'receipt', 'bill', 'tax invoice']:
                result["vendor_name"] = lines[0]
            elif len(lines) > 1:
                result["vendor_name"] = lines[1]

        # 4. Amounts (Robust extraction with consistency validation)
        amounts_result = self._extract_amounts_robust(text)
        
        if amounts_result["subtotal"] is not None:
            result["subtotal_amount"] = amounts_result["subtotal"]
        if amounts_result["tax"] is not None:
            result["tax_amount"] = amounts_result["tax"]
        if amounts_result["total"] is not None:
            result["total_amount"] = amounts_result["total"]

        # 5. Category classification
        result["category"] = self._classify_category(text)

        # 6. Payment Method
        result["payment_method"] = self._detect_payment_method(text)

        # 7. Confidence Score (Evidence Based)
        score = 0.0
        
        # Base explicit fields (15% each)
        if result["vendor_name"]: score += 0.15
        if result["invoice_number"]: score += 0.15
        if result["invoice_date"]: score += 0.15
        if result["payment_method"] != "Unknown": score += 0.05
        if result["category"] != "General": score += 0.05
        
        # Financial logic accounts for the remaining 45%+
        has_sub = amounts_result.get("subtotal") is not None
        has_tax = amounts_result.get("tax") is not None
        has_tot = amounts_result.get("total") is not None
        
        math_consistent = amounts_result.get("math_consistent", False)
        
        if has_tot:
            score += 0.15
        if has_sub:
            score += 0.15
            
        if math_consistent:
            score += 0.30 # Massive boost for verified math
        elif has_tot and not has_sub and not has_tax:
            score -= 0.20 # Deduction for isolated total
            
        # Bound confidence between 0.0 and 1.0
        result["confidence_score"] = round(max(0.0, min(1.0, score)), 2)
        
        # 8. AI Summary
        vendor = result["vendor_name"] or "an unknown vendor"
        total = result["total_amount"] or "an unknown amount"
        date_str = result["invoice_date"] or "an unknown date"
        
        result["ai_summary"] = f"This document appears to be an invoice from {vendor} for {total}, issued on {date_str}."
        if result["confidence_score"] < 0.4:
            result["ai_summary"] += " Extraction confidence is very low. Please verify values manually."

        return result

    def _extract_amounts_robust(self, text: str) -> Dict[str, Any]:
        result = {"subtotal": None, "tax": None, "shipping": None, "total": None, "math_consistent": False}
        
        amounts = []
        for m in re.finditer(r'([\d,]+\.\d{2})', text):
            val = self._parse_amount(m.group(1))
            if val is not None:
                amounts.append({"val": val, "start": m.start(), "end": m.end()})
                
        if not amounts:
            return result
            
        def get_candidates(label_pattern):
            candidates = []
            for lbl_match in re.finditer(label_pattern, text, re.IGNORECASE):
                lbl_end = lbl_match.end()
                for amt in amounts:
                    if amt["start"] >= lbl_end and amt["start"] - lbl_end < 80:
                        between_text = text[lbl_end:amt["start"]]
                        candidates.append(amt["val"])
                        if len(candidates) >= 4:
                            break
            return candidates

        subs = get_candidates(r'(?:Sub Total|Subtotal|Sub-total|Net Amount|Net Total)\s*[:]?')
        taxes = get_candidates(r'(?:Sales Tax|Tax|GST|CGST|SGST|IGST|VAT)\s*[:]?')
        ships = get_candidates(r'(?:Shipping & Handling|Shipping|Handling|Delivery|Freight)\s*[:]?')
        totals = get_candidates(r'(?:Total Due|Grand Total|Amount Due|Balance Due|Net Payable|Total)\s*[:]?')
        
        # Cross reference math: Subtotal + Tax + Shipping = Total
        # Try all combinations to find a strictly consistent triad/quad
        for s in subs:
            for t in (taxes if taxes else [Decimal('0.00')]):
                for sh in (ships if ships else [Decimal('0.00')]):
                    for tot in totals:
                        if abs((s + t + sh) - tot) <= Decimal('0.10'):
                            return {
                                "subtotal": s, 
                                "tax": t if taxes else None,
                                "shipping": sh if ships else None, 
                                "total": tot,
                                "math_consistent": True
                            }
                            
        # Check simple Subtotal == Total (Zero tax/shipping)
        for s in subs:
            for tot in totals:
                if s == tot:
                    return {
                        "subtotal": s, 
                        "tax": Decimal('0.00'), 
                        "shipping": Decimal('0.00'),
                        "total": tot,
                        "math_consistent": True
                    }
                    
        # Fallback: Just return the first candidates found if no math consistency
        if subs: result["subtotal"] = subs[0]
        if taxes: result["tax"] = taxes[0]
        if ships: result["shipping"] = ships[0]
        if totals: result["total"] = totals[0]
        
        # Ultimate fallback: Highest value as total if missing
        if not totals and amounts:
            result["total"] = max([a["val"] for a in amounts])
            
        return result

    def _extract_with_openai(self, text: str) -> Dict[str, Any]:
        """Extract data using OpenAI API."""
        prompt = (
            "Extract the following financial fields from the OCR text. Return ONLY a valid JSON object. "
            "Dates MUST be YYYY-MM-DD. Amounts MUST be numeric (no currency symbols). "
            "Use null for missing fields.\n\n"
            "Fields: vendor_name (string), invoice_number (string), invoice_date (YYYY-MM-DD), "
            "subtotal_amount (number), tax_amount (number), total_amount (number), "
            "category (choose one: Food, Travel, Office Supplies, Utilities, Software, Marketing, Rent, Professional Services, Hardware, Healthcare, General), "
            "payment_method (choose one: Cash, Card, Credit Card, Debit Card, UPI, Bank Transfer, Cheque, Unknown), "
            "confidence_score (number 0.0 to 1.0), ai_summary (string 2-3 sentences max).\n\n"
            f"OCR Text:\n{text[:8000]}"
        )

        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }
        
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=15)
        response.raise_for_status()
        
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        
        # Ensure Decimals for amounts
        for field in ["subtotal_amount", "tax_amount", "total_amount"]:
            if parsed.get(field) is not None:
                parsed[field] = Decimal(str(parsed[field]))
                
        return parsed

    def _is_valid_result(self, result: Dict[str, Any]) -> bool:
        """Validate LLM output schema."""
        required = ["vendor_name", "total_amount", "confidence_score"]
        for req in required:
            if req not in result:
                return False
        return True

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "vendor_name": None,
            "invoice_number": None,
            "invoice_date": None,
            "subtotal_amount": None,
            "tax_amount": None,
            "total_amount": None,
            "category": "General",
            "payment_method": "Unknown",
            "confidence_score": 0.0,
            "ai_summary": "Document could not be processed."
        }

    def _parse_amount(self, amount_str: str) -> Optional[Decimal]:
        try:
            clean = re.sub(r'[^\d.]', '', amount_str)
            return Decimal(clean)
        except (InvalidOperation, ValueError):
            return None

    def _parse_date(self, date_str: str) -> Optional[str]:
        # Handle formats: January 25, 2016 | 25 January 2016 | 2016-01-25 | 25/01/2016 | 25-01-2016 | 23.05.2021
        clean = date_str.replace(',', '').strip()
        formats = [
            '%B %d %Y', '%b %d %Y', '%d %B %Y', '%d %b %Y',
            '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y',
            '%d.%m.%Y', '%m.%d.%Y'
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(clean, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        return None

    def _classify_category(self, text: str) -> str:
        text_lower = text.lower()
        
        # Word boundaries to prevent "travel" matching inside "traveler" etc, though less of an issue.
        def has_words(words):
            return any(re.search(r'\b' + w + r'\b', text_lower) for w in words)
            
        if has_words(['restaurant', 'cafe', 'lunch', 'dinner', 'eatery']): return 'Food'
        if has_words(['hotel', 'flight', 'taxi', 'uber', 'lyft', 'airline']): return 'Travel'
        if has_words(['electricity', 'internet', 'phone', 'utility', 'water', 'broadband']): return 'Utilities'
        if has_words(['office', 'stationery', 'desk', 'paperwork']): return 'Office Supplies'
        if has_words(['software', 'hosting', 'cloud', 'aws', 'subscription', 'saas']): return 'Software'
        if has_words(['marketing', 'ads', 'google ads', 'seo', 'campaign']): return 'Marketing'
        if has_words(['consulting', 'professional', 'legal', 'lawyer', 'cpa']): return 'Professional Services'
        
        return 'General'

    def _detect_payment_method(self, text: str) -> str:
        # Instead of just searching the whole text for "check", search for "paid by check" or "payment method: check"
        text_lower = text.lower()
        
        # Look specifically near payment keywords
        payment_context = re.search(r'(?:paid|payment|tender|method|paid via|paid by)\s*[:]?\s*(.{0,30})', text_lower)
        
        if payment_context:
            context = payment_context.group(1)
            if any(w in context for w in ['credit', 'visa', 'mastercard', 'amex']): return 'Credit Card'
            if 'debit' in context: return 'Debit Card'
            if 'card' in context: return 'Card'
            if 'cash' in context: return 'Cash'
            if 'upi' in context: return 'UPI'
            if any(w in context for w in ['bank', 'wire', 'ach', 'transfer']): return 'Bank Transfer'
            if any(w in context for w in ['cheque', 'check']): return 'Cheque'
            
        return 'Unknown'
