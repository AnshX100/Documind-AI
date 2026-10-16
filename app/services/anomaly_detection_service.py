"""Anomaly Detection Service for explainable, deterministic financial anomaly detection."""

import math
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date

from app.extensions import db
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_analysis_repository import DocumentAnalysisRepository

logger = logging.getLogger(__name__)


class AnomalyDetectionService:
    """Service implementing deterministic and explainable financial anomaly detection rules."""

    def __init__(
        self,
        document_repo: Optional[DocumentRepository] = None,
        analysis_repo: Optional[DocumentAnalysisRepository] = None
    ) -> None:
        self.document_repo = document_repo or DocumentRepository()
        self.analysis_repo = analysis_repo or DocumentAnalysisRepository()

    def get_document_anomalies(self, document_id: int, user_id: int) -> List[Dict[str, Any]]:
        """Evaluates and returns all detected anomalies for a single user document."""
        document = self.document_repo.get_by_id_and_user(document_id, user_id)
        if not document or not document.analysis or document.status != 'processed':
            return []

        # Fetch all processed user documents for comparison context
        all_user_docs = Document.query.filter_by(
            user_id=user_id,
            status='processed'
        ).all()

        return self._detect_anomalies_for_target(document, all_user_docs)

    def get_user_anomalies(
        self,
        user_id: int,
        severity: Optional[str] = None,
        anomaly_type: Optional[str] = None,
        limit: Optional[int] = None,
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Evaluates and returns detected anomalies across processed documents for a user.

        Preserves full analytical baseline context while filtering surfaced report findings
        to the specified period_start / period_end window.
        """
        all_user_docs = Document.query.filter_by(
            user_id=user_id,
            status='processed'
        ).order_by(Document.created_at.desc()).all()

        if not all_user_docs:
            return []

        all_anomalies = []
        for doc in all_user_docs:
            if doc.analysis:
                doc_anomalies = self._detect_anomalies_for_target(doc, all_user_docs)
                all_anomalies.extend(doc_anomalies)

        # De-duplicate pair duplicates (e.g. Doc 1 flags Doc 2 and Doc 2 flags Doc 1)
        seen_keys = set()
        deduped = []
        for anom in all_anomalies:
            # Key based on type and sorted doc IDs
            if anom["anomaly_type"] == "duplicate_invoice":
                doc_ids = tuple(sorted([anom["document_id"]] + anom.get("related_document_ids", [])))
                key = (anom["anomaly_type"], doc_ids)
            else:
                key = (anom["anomaly_type"], anom["document_id"])

            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(anom)

        # Date range filtering on surfaced anomalies (using document transaction/creation date)
        if period_start or period_end:
            start_dt = self._parse_datetime(period_start, is_end=False)
            end_dt = self._parse_datetime(period_end, is_end=True)

            # Map doc.id -> date
            doc_dates = {}
            for doc in all_user_docs:
                if doc.analysis and doc.analysis.invoice_date:
                    doc_dates[doc.id] = datetime.combine(doc.analysis.invoice_date, datetime.min.time())
                else:
                    doc_dates[doc.id] = doc.created_at

            filtered_by_date = []
            for a in deduped:
                d_id = a.get("document_id")
                d_date = doc_dates.get(d_id)
                if d_date:
                    if start_dt and d_date < start_dt:
                        continue
                    if end_dt and d_date > end_dt:
                        continue
                filtered_by_date.append(a)
            deduped = filtered_by_date

        # Apply severity and type filters
        if severity and severity.upper() != 'ALL':
            deduped = [a for a in deduped if a["severity"].upper() == severity.upper()]

        if anomaly_type and anomaly_type.lower() != 'all':
            deduped = [a for a in deduped if a["anomaly_type"].lower() == anomaly_type.lower()]

        # Sort: CRITICAL (0), HIGH (1), MEDIUM (2), LOW (3)
        severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        deduped.sort(key=lambda a: severity_rank.get(a["severity"].upper(), 99))

        if limit:
            return deduped[:limit]
        return deduped

    def _parse_datetime(self, val: Optional[Any], is_end: bool = False) -> Optional[datetime]:
        """Helper to parse str/date/datetime to datetime."""
        if not val:
            return None
        if isinstance(val, str):
            try:
                dt = datetime.strptime(val, "%Y-%m-%d")
                return dt.replace(hour=23, minute=59, second=59) if is_end else dt
            except ValueError:
                return None
        if isinstance(val, datetime):
            return val
        if isinstance(val, date):
            return datetime.combine(val, datetime.max.time()) if is_end else datetime.combine(val, datetime.min.time())
        return None

    def get_anomaly_summary(
        self,
        user_id: int,
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Returns summary counts of anomalies categorized by severity."""
        anomalies = self.get_user_anomalies(user_id, period_start=period_start, period_end=period_end)
        critical_count = sum(1 for a in anomalies if a["severity"] == "CRITICAL")
        high_count = sum(1 for a in anomalies if a["severity"] == "HIGH")
        medium_count = sum(1 for a in anomalies if a["severity"] == "MEDIUM")
        low_count = sum(1 for a in anomalies if a["severity"] == "LOW")

        return {
            "total": len(anomalies),
            "critical": critical_count,
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
            "high_risk_count": critical_count + high_count
        }

    def _detect_anomalies_for_target(
        self,
        doc: Document,
        all_docs: List[Document]
    ) -> List[Dict[str, Any]]:
        """Internal detection logic running rules A through F on a single document against its peer set."""
        anomalies = []
        analysis: DocumentAnalysis = doc.analysis
        if not analysis:
            return anomalies

        other_docs = [d for d in all_docs if d.id != doc.id and d.analysis]

        # Rule A: Duplicate Invoice Detection
        duplicate_anom = self._check_duplicate_invoice(doc, analysis, other_docs)
        if duplicate_anom:
            anomalies.append(duplicate_anom)

        # Rule B: Unusual Transaction Amount (Z-score / Outlier vs Historical Normal)
        unusual_amount_anom = self._check_unusual_amount(doc, analysis, other_docs)
        if unusual_amount_anom:
            anomalies.append(unusual_amount_anom)

        # Rule C: Spending Spike Detection
        spending_spike_anom = self._check_spending_spike(doc, analysis, other_docs)
        if spending_spike_anom:
            anomalies.append(spending_spike_anom)

        # Rule D: Missing or Incomplete Financial Information
        missing_data_anom = self._check_missing_financial_info(doc, analysis)
        if missing_data_anom:
            anomalies.append(missing_data_anom)

        # Rule E: Arithmetic Inconsistency
        arithmetic_anom = self._check_arithmetic_inconsistency(doc, analysis)
        if arithmetic_anom:
            anomalies.append(arithmetic_anom)

        # Rule F: Low Confidence Extraction Warning
        confidence_anom = self._check_extraction_confidence(doc, analysis)
        if confidence_anom:
            anomalies.append(confidence_anom)

        return anomalies

    def _check_duplicate_invoice(
        self,
        doc: Document,
        analysis: DocumentAnalysis,
        other_docs: List[Document]
    ) -> Optional[Dict[str, Any]]:
        """Detects strong and weak duplicate invoice records."""
        vendor = (analysis.vendor_name or "").strip().lower()
        inv_num = (analysis.invoice_number or "").strip().lower()
        total_amt = float(analysis.total_amount or 0.0)
        inv_date = analysis.invoice_date

        for other in other_docs:
            o_analysis: DocumentAnalysis = other.analysis
            o_vendor = (o_analysis.vendor_name or "").strip().lower()
            o_inv_num = (o_analysis.invoice_number or "").strip().lower()
            o_total = float(o_analysis.total_amount or 0.0)
            o_date = o_analysis.invoice_date

            # Strong duplicate match: Same vendor + Same non-empty invoice number
            if vendor and inv_num and o_vendor and o_inv_num:
                if vendor == o_vendor and inv_num == o_inv_num:
                    is_exact_amount = abs(total_amt - o_total) < 0.01
                    severity = "CRITICAL" if is_exact_amount else "HIGH"
                    return {
                        "id": f"anom-{doc.id}-dup-strong",
                        "anomaly_type": "duplicate_invoice",
                        "severity": severity,
                        "title": f"Duplicate Invoice #{analysis.invoice_number}",
                        "description": f"Identical invoice number #{analysis.invoice_number} from vendor '{analysis.vendor_name}' detected on another file.",
                        "reason": f"Matches document '{other.original_filename}' (ID #{other.id}) with the same vendor ('{analysis.vendor_name}') and invoice number ('{analysis.invoice_number}').",
                        "document_id": doc.id,
                        "document_name": doc.original_filename,
                        "related_document_ids": [other.id],
                        "related_document_names": [other.original_filename],
                        "detected_value": f"Invoice #{analysis.invoice_number} (₹{total_amt:,.2f})",
                        "expected_value": "Unique invoice identifier across all vendor records",
                        "confidence": 0.98,
                        "recommended_review_action": "Verify whether this is an accidental double submission or re-billing before approval.",
                        "detected_at": doc.created_at.strftime('%d %b %Y')
                    }

            # Weak duplicate match: Same vendor + Matching total amount (> 0) + Matching invoice date
            if vendor and o_vendor and vendor == o_vendor and total_amt > 0 and abs(total_amt - o_total) < 0.01:
                if inv_date and o_date and inv_date == o_date:
                    return {
                        "id": f"anom-{doc.id}-dup-weak",
                        "anomaly_type": "duplicate_invoice",
                        "severity": "MEDIUM",
                        "title": f"Potential Duplicate Transaction (₹{total_amt:,.2f})",
                        "description": f"Identical amount of ₹{total_amt:,.2f} and vendor '{analysis.vendor_name}' on date {inv_date.strftime('%d %b %Y')}.",
                        "reason": f"Matches document '{other.original_filename}' (ID #{other.id}) with matching amount (₹{total_amt:,.2f}) and date ({inv_date.strftime('%d %b %Y')}).",
                        "document_id": doc.id,
                        "document_name": doc.original_filename,
                        "related_document_ids": [other.id],
                        "related_document_names": [other.original_filename],
                        "detected_value": f"₹{total_amt:,.2f} on {inv_date.strftime('%d %b %Y')}",
                        "expected_value": "Distinct transaction or documented multiple services on same date",
                        "confidence": 0.85,
                        "recommended_review_action": "Check if two separate orders were placed with the vendor on the same date or if this invoice was scanned twice.",
                        "detected_at": doc.created_at.strftime('%d %b %Y')
                    }

        return None

    def _check_unusual_amount(
        self,
        doc: Document,
        analysis: DocumentAnalysis,
        other_docs: List[Document]
    ) -> Optional[Dict[str, Any]]:
        """Identifies transactions significantly larger than historical baseline."""
        target_amount = float(analysis.total_amount or 0.0)
        if target_amount <= 0:
            return None

        historical_amounts = [
            float(d.analysis.total_amount or 0.0)
            for d in other_docs
            if float(d.analysis.total_amount or 0.0) > 0
        ]

        # Require at least 3 historical transactions for statistical validity
        if len(historical_amounts) < 3:
            return None

        n = len(historical_amounts)
        mean = sum(historical_amounts) / n
        variance = sum((x - mean) ** 2 for x in historical_amounts) / n
        std_dev = math.sqrt(variance)

        # Median calculation
        sorted_amounts = sorted(historical_amounts)
        mid = n // 2
        median = (sorted_amounts[mid] if n % 2 != 0 else (sorted_amounts[mid - 1] + sorted_amounts[mid]) / 2.0)

        # Outlier condition: Amount > mean + 2.5 * std_dev and at least 2.0x mean
        ratio = target_amount / mean if mean > 0 else 1.0
        is_outlier = False

        if std_dev > 0 and target_amount > (mean + 2.5 * std_dev) and ratio >= 2.0:
            is_outlier = True
        elif std_dev == 0 and ratio >= 3.0:
            is_outlier = True

        if is_outlier:
            severity = "CRITICAL" if ratio >= 5.0 else "HIGH"
            return {
                "id": f"anom-{doc.id}-unusual-amt",
                "anomaly_type": "unusual_amount",
                "severity": severity,
                "title": f"Unusually High Transaction (₹{target_amount:,.2f})",
                "description": f"This transaction is {round(ratio, 1)}x higher than your historical workspace average of ₹{mean:,.2f}.",
                "reason": f"Amount ₹{target_amount:,.2f} deviates significantly from typical spending (mean: ₹{mean:,.2f}, median: ₹{median:,.2f}, standard deviation: ₹{std_dev:,.2f}, sample: {n} documents).",
                "document_id": doc.id,
                "document_name": doc.original_filename,
                "related_document_ids": [],
                "related_document_names": [],
                "detected_value": f"₹{target_amount:,.2f}",
                "expected_value": f"₹{mean:,.2f} avg (typical range: ₹{max(0, mean - std_dev):,.2f} – ₹{mean + std_dev:,.2f})",
                "confidence": 0.92,
                "recommended_review_action": "Review contract terms, management approval, and line-item details for this large expense.",
                "detected_at": doc.created_at.strftime('%d %b %Y')
            }

        return None

    def _check_spending_spike(
        self,
        doc: Document,
        analysis: DocumentAnalysis,
        other_docs: List[Document]
    ) -> Optional[Dict[str, Any]]:
        """Detects spending spikes for a specific vendor compared to prior transactions."""
        vendor = (analysis.vendor_name or "").strip()
        if not vendor or vendor.lower() in ["unknown", "uncategorized", ""]:
            return None

        target_amount = float(analysis.total_amount or 0.0)
        if target_amount < 5000:
            return None

        # Filter other transactions for this vendor
        vendor_others = [
            float(d.analysis.total_amount or 0.0)
            for d in other_docs
            if (d.analysis.vendor_name or "").strip().lower() == vendor.lower()
            and float(d.analysis.total_amount or 0.0) > 0
        ]

        if len(vendor_others) >= 2:
            vendor_avg = sum(vendor_others) / len(vendor_others)
            if vendor_avg > 0 and target_amount >= (2.5 * vendor_avg) and (target_amount - vendor_avg) >= 5000:
                pct_increase = ((target_amount - vendor_avg) / vendor_avg) * 100
                severity = "HIGH" if pct_increase >= 200 else "MEDIUM"
                return {
                    "id": f"anom-{doc.id}-vendor-spike",
                    "anomaly_type": "spending_spike",
                    "severity": severity,
                    "title": f"Vendor Spending Spike: {vendor}",
                    "description": f"Transaction is {round(pct_increase)}% higher than historical average for '{vendor}'.",
                    "reason": f"Current amount (₹{target_amount:,.2f}) significantly exceeds the historical average of ₹{vendor_avg:,.2f} across {len(vendor_others)} prior transactions with '{vendor}'.",
                    "document_id": doc.id,
                    "document_name": doc.original_filename,
                    "related_document_ids": [],
                    "related_document_names": [],
                    "detected_value": f"₹{target_amount:,.2f}",
                    "expected_value": f"₹{vendor_avg:,.2f} (vendor average)",
                    "confidence": 0.88,
                    "recommended_review_action": f"Confirm scope of work or volume expansion changes with vendor '{vendor}'.",
                    "detected_at": doc.created_at.strftime('%d %b %Y')
                }

        return None

    def _check_missing_financial_info(
        self,
        doc: Document,
        analysis: DocumentAnalysis
    ) -> Optional[Dict[str, Any]]:
        """Identifies missing essential financial metadata."""
        missing = []
        if not analysis.vendor_name or not analysis.vendor_name.strip():
            missing.append("Vendor Name")
        if not analysis.invoice_date:
            missing.append("Invoice Date")
        if not analysis.invoice_number or not analysis.invoice_number.strip():
            missing.append("Invoice Number")

        total = float(analysis.total_amount or 0.0)
        if total <= 0:
            missing.append("Total Amount")

        if missing:
            if "Total Amount" in missing:
                severity = "HIGH"
            elif "Vendor Name" in missing:
                severity = "MEDIUM"
            else:
                severity = "LOW"

            return {
                "id": f"anom-{doc.id}-missing-info",
                "anomaly_type": "missing_data",
                "severity": severity,
                "title": f"Missing Financial Information: {', '.join(missing[:2])}",
                "description": f"The document is missing essential metadata: {', '.join(missing)}.",
                "reason": f"Required accounting fields ({', '.join(missing)}) were not extracted or present in the document.",
                "document_id": doc.id,
                "document_name": doc.original_filename,
                "related_document_ids": [],
                "related_document_names": [],
                "detected_value": f"Missing: {', '.join(missing)}",
                "expected_value": "All core financial entities (Vendor, Date, Invoice #, Total)",
                "confidence": 0.95,
                "recommended_review_action": "Check the document preview and manually re-verify missing fields.",
                "detected_at": doc.created_at.strftime('%d %b %Y')
            }

        return None

    def _check_arithmetic_inconsistency(
        self,
        doc: Document,
        analysis: DocumentAnalysis
    ) -> Optional[Dict[str, Any]]:
        """Validates arithmetic consistency: Subtotal + Tax == Total."""
        subtotal = float(analysis.subtotal_amount or 0.0)
        tax = float(analysis.tax_amount or 0.0)
        total = float(analysis.total_amount or 0.0)

        if subtotal > 0 and (tax > 0 or (subtotal != total and total > 0)):
            expected_total = round(subtotal + tax, 2)
            discrepancy = round(abs(expected_total - total), 2)

            if discrepancy > 0.05:
                severity = "HIGH" if (discrepancy > 100 or (total > 0 and discrepancy / total > 0.1)) else "MEDIUM"
                return {
                    "id": f"anom-{doc.id}-arithmetic",
                    "anomaly_type": "arithmetic_inconsistency",
                    "severity": severity,
                    "title": "Arithmetic Inconsistency in Invoice",
                    "description": f"Subtotal (₹{subtotal:,.2f}) + Tax (₹{tax:,.2f}) = ₹{expected_total:,.2f}, but total is ₹{total:,.2f}.",
                    "reason": f"Calculated discrepancy of ₹{discrepancy:,.2f} between subtotal + tax and declared total.",
                    "document_id": doc.id,
                    "document_name": doc.original_filename,
                    "related_document_ids": [],
                    "related_document_names": [],
                    "detected_value": f"Total ₹{total:,.2f}",
                    "expected_value": f"Subtotal (₹{subtotal:,.2f}) + Tax (₹{tax:,.2f}) = ₹{expected_total:,.2f}",
                    "confidence": 0.96,
                    "recommended_review_action": "Review itemized invoice lines for unlisted discounts, shipping, or calculation errors.",
                    "detected_at": doc.created_at.strftime('%d %b %Y')
                }

        return None

    def _check_extraction_confidence(
        self,
        doc: Document,
        analysis: DocumentAnalysis
    ) -> Optional[Dict[str, Any]]:
        """Flags documents with low OCR / AI extraction confidence scores."""
        score = float(analysis.confidence_score or 0.0)
        if 0 < score < 0.70:
            return {
                "id": f"anom-{doc.id}-low-conf",
                "anomaly_type": "low_confidence",
                "severity": "MEDIUM" if score < 0.55 else "LOW",
                "title": f"Low Extraction Confidence ({int(score * 100)}%)",
                "description": f"OCR extraction confidence is {int(score * 100)}%, below standard verification threshold.",
                "reason": "Text image quality or layout complexity reduced optical extraction reliability.",
                "document_id": doc.id,
                "document_name": doc.original_filename,
                "related_document_ids": [],
                "related_document_names": [],
                "detected_value": f"{int(score * 100)}% Confidence",
                "expected_value": ">= 75% Extraction Confidence",
                "confidence": 0.90,
                "recommended_review_action": "Cross-check extracted financial breakdown against the original visual preview.",
                "detected_at": doc.created_at.strftime('%d %b %Y')
            }

        return None
