"""Evidence Retrieval Service for gathering user-scoped financial facts without hallucination."""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import or_

from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_analysis_repository import DocumentAnalysisRepository
from app.services.financial_intelligence_service import FinancialIntelligenceService
from app.services.anomaly_detection_service import AnomalyDetectionService
from app.services.due_diligence_service import DueDiligenceService

logger = logging.getLogger(__name__)


class EvidenceRetrievalService:
    """Service to retrieve verified, user-isolated financial facts and source documents."""

    def __init__(
        self,
        financial_service: FinancialIntelligenceService,
        anomaly_service: AnomalyDetectionService,
        due_diligence_service: DueDiligenceService,
        document_repo: Optional[DocumentRepository] = None,
        analysis_repo: Optional[DocumentAnalysisRepository] = None
    ) -> None:
        self.financial_service = financial_service
        self.anomaly_service = anomaly_service
        self.due_diligence_service = due_diligence_service
        self.document_repo = document_repo or DocumentRepository()
        self.analysis_repo = analysis_repo or DocumentAnalysisRepository()

    def get_evidence(self, user_id: int, intent: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve verified facts and sources for the given intent and user.

        Args:
            user_id (int): Authenticated user ID.
            intent (str): Identified intent name.
            entities (Dict[str, Any]): Extracted entities (category, document_reference, time_period).

        Returns:
            Dict[str, Any]: Structured evidence with status, intent, facts, sources, and warnings.
        """
        try:
            if intent == "TOTAL_SPENDING":
                return self._get_total_spending_evidence(user_id, entities)
            elif intent == "CATEGORY_SPENDING":
                return self._get_category_spending_evidence(user_id, entities)
            elif intent == "TOP_VENDOR":
                return self._get_top_vendor_evidence(user_id)
            elif intent == "TOP_VENDORS":
                return self._get_top_vendors_evidence(user_id)
            elif intent == "SPENDING_TREND":
                return self._get_spending_trend_evidence(user_id)
            elif intent == "MONTH_COMPARISON":
                return self._get_month_comparison_evidence(user_id)
            elif intent == "ANOMALIES":
                return self._get_anomalies_evidence(user_id)
            elif intent == "DUPLICATE_DOCUMENTS":
                return self._get_duplicate_documents_evidence(user_id)
            elif intent in ["DOCUMENT_RISK", "DOCUMENT_LOOKUP"]:
                return self._get_document_specific_evidence(user_id, intent, entities)
            elif intent == "DUE_DILIGENCE":
                return self._get_due_diligence_evidence(user_id)
            elif intent == "TAX_SUMMARY":
                return self._get_tax_summary_evidence(user_id)
            elif intent == "PAYMENT_METHOD_SUMMARY":
                return self._get_payment_method_evidence(user_id)
            elif intent == "GENERAL_FINANCIAL_SUMMARY":
                return self._get_general_summary_evidence(user_id)
            else:
                return {
                    "status": "success",
                    "intent": "UNKNOWN",
                    "facts": {},
                    "sources": [],
                    "warnings": ["Question could not be mapped to a specific financial metric."]
                }
        except Exception as e:
            logger.error(f"Error retrieving evidence for user {user_id}, intent {intent}: {e}")
            return {
                "status": "error",
                "intent": intent,
                "facts": {},
                "sources": [],
                "warnings": ["Failed to calculate evidence due to an internal error."]
            }

    def _get_total_spending_evidence(self, user_id: int, entities: Dict[str, Any]) -> Dict[str, Any]:
        time_period = entities.get("time_period") or "all"
        overview = self.financial_service.get_financial_overview(user_id, date_range=time_period)

        if overview["analyzed_documents"] == 0:
            return {
                "status": "insufficient_data",
                "intent": "TOTAL_SPENDING",
                "facts": overview,
                "sources": [],
                "warnings": ["No analyzed documents found for the requested timeframe."]
            }

        # Fetch top source documents for this user
        docs = self._get_top_user_documents(user_id, limit=5)
        sources = [self._format_doc_source(d) for d in docs]

        return {
            "status": "success",
            "intent": "TOTAL_SPENDING",
            "facts": overview,
            "sources": sources,
            "warnings": []
        }

    def _get_category_spending_evidence(self, user_id: int, entities: Dict[str, Any]) -> Dict[str, Any]:
        categories = self.financial_service.get_spending_by_category(user_id)
        req_cat = entities.get("category")

        if not categories:
            return {
                "status": "insufficient_data",
                "intent": "CATEGORY_SPENDING",
                "facts": {"requested_category": req_cat, "categories": []},
                "sources": [],
                "warnings": ["No categorized spending records found."]
            }

        # Normalize dict keys from financial_service
        normalized_cats = []
        for c in categories:
            cat_name = c.get("category") or c.get("category_name") or "General"
            total = float(c.get("total") or c.get("total_amount") or 0.0)
            count = int(c.get("count") or c.get("document_count") or 0)
            pct = float(c.get("percentage") or 0.0)
            normalized_cats.append({
                "category_name": cat_name,
                "total_amount": total,
                "document_count": count,
                "percentage": pct
            })

        if req_cat:
            matched = next((c for c in normalized_cats if c["category_name"].lower() == req_cat.lower()), None)
            if not matched:
                return {
                    "status": "insufficient_data",
                    "intent": "CATEGORY_SPENDING",
                    "facts": {"requested_category": req_cat, "available_categories": [c["category_name"] for c in normalized_cats]},
                    "sources": [],
                    "warnings": [f"No transactions recorded for category '{req_cat}'."]
                }

            # Fetch sources for this category
            docs = self._get_documents_by_category(user_id, matched["category_name"])
            sources = [self._format_doc_source(d) for d in docs]

            return {
                "status": "success",
                "intent": "CATEGORY_SPENDING",
                "facts": {
                    "requested_category": matched["category_name"],
                    "total_amount": matched["total_amount"],
                    "percentage": matched["percentage"],
                    "document_count": matched["document_count"]
                },
                "sources": sources,
                "warnings": []
            }

        return {
            "status": "success",
            "intent": "CATEGORY_SPENDING",
            "facts": {"categories": normalized_cats},
            "sources": [],
            "warnings": []
        }

    def _get_top_vendor_evidence(self, user_id: int) -> Dict[str, Any]:
        vendors = self.financial_service.get_spending_by_vendor(user_id, limit=1)

        if not vendors:
            return {
                "status": "insufficient_data",
                "intent": "TOP_VENDOR",
                "facts": {},
                "sources": [],
                "warnings": ["No vendor transactions found."]
            }

        top = vendors[0]
        v_name = top.get("vendor") or top.get("vendor_name") or "Unknown"
        total = float(top.get("total") or top.get("total_spending") or 0.0)
        count = int(top.get("transaction_count") or top.get("count") or 0)
        pct = float(top.get("percentage") or 0.0)

        top_fact = {
            "vendor_name": v_name,
            "total_spending": total,
            "document_count": count,
            "spending_percentage": pct
        }

        docs = self._get_documents_by_vendor(user_id, v_name)
        sources = [self._format_doc_source(d) for d in docs]

        return {
            "status": "success",
            "intent": "TOP_VENDOR",
            "facts": top_fact,
            "sources": sources,
            "warnings": []
        }

    def _get_top_vendors_evidence(self, user_id: int) -> Dict[str, Any]:
        vendors = self.financial_service.get_spending_by_vendor(user_id, limit=5)

        if not vendors:
            return {
                "status": "insufficient_data",
                "intent": "TOP_VENDORS",
                "facts": {"vendors": []},
                "sources": [],
                "warnings": ["No vendor transactions found."]
            }

        norm_vendors = []
        for v in vendors:
            norm_vendors.append({
                "vendor_name": v.get("vendor") or v.get("vendor_name") or "Unknown",
                "total_spending": float(v.get("total") or v.get("total_spending") or 0.0),
                "document_count": int(v.get("transaction_count") or v.get("count") or 0),
                "spending_percentage": float(v.get("percentage") or 0.0)
            })

        return {
            "status": "success",
            "intent": "TOP_VENDORS",
            "facts": {"vendors": norm_vendors},
            "sources": [],
            "warnings": []
        }

    def _get_spending_trend_evidence(self, user_id: int) -> Dict[str, Any]:
        trends = self.financial_service.get_monthly_spending_patterns(user_id, months=12)

        if not trends:
            return {
                "status": "insufficient_data",
                "intent": "SPENDING_TREND",
                "facts": {"trends": []},
                "sources": [],
                "warnings": ["No monthly trend data available."]
            }

        return {
            "status": "success",
            "intent": "SPENDING_TREND",
            "facts": {"trends": trends},
            "sources": [],
            "warnings": []
        }

    def _get_month_comparison_evidence(self, user_id: int) -> Dict[str, Any]:
        trends = self.financial_service.get_monthly_spending_patterns(user_id, months=2)

        if not trends or len(trends) < 2:
            return {
                "status": "insufficient_data",
                "intent": "MONTH_COMPARISON",
                "facts": {"available_months": len(trends)},
                "sources": [],
                "warnings": ["Requires at least 2 consecutive months of document data for comparison."]
            }

        current_month = trends[-1]
        previous_month = trends[-2]
        diff = current_month["total_amount"] - previous_month["total_amount"]
        pct_change = ((diff / previous_month["total_amount"]) * 100) if previous_month["total_amount"] > 0 else 0.0

        return {
            "status": "success",
            "intent": "MONTH_COMPARISON",
            "facts": {
                "current_period": {"label": current_month["month_label"], "amount": current_month["total_amount"]},
                "previous_period": {"label": previous_month["month_label"], "amount": previous_month["total_amount"]},
                "difference": diff,
                "percentage_change": round(pct_change, 2)
            },
            "sources": [],
            "warnings": []
        }

    def _get_anomalies_evidence(self, user_id: int) -> Dict[str, Any]:
        anomalies = self.anomaly_service.get_user_anomalies(user_id)
        summary = self.anomaly_service.get_anomaly_summary(user_id)

        sources = []
        for a in anomalies:
            if a.get("document_id"):
                doc = Document.query.filter_by(id=a["document_id"], user_id=user_id).first()
                if doc:
                    sources.append(self._format_doc_source(doc))

        return {
            "status": "success",
            "intent": "ANOMALIES",
            "facts": {
                "anomalies_count": len(anomalies),
                "summary": summary,
                "anomalies": anomalies
            },
            "sources": sources,
            "warnings": []
        }

    def _get_duplicate_documents_evidence(self, user_id: int) -> Dict[str, Any]:
        anomalies = self.anomaly_service.get_user_anomalies(user_id)
        duplicates = [a for a in anomalies if a.get("anomaly_type") in ["DUPLICATE_INVOICE", "WEAK_DUPLICATE"]]

        sources = []
        for d in duplicates:
            if d.get("document_id"):
                doc = Document.query.filter_by(id=d["document_id"], user_id=user_id).first()
                if doc:
                    sources.append(self._format_doc_source(doc))

        return {
            "status": "success",
            "intent": "DUPLICATE_DOCUMENTS",
            "facts": {
                "duplicate_count": len(duplicates),
                "duplicates": duplicates
            },
            "sources": sources,
            "warnings": []
        }

    def _get_document_specific_evidence(self, user_id: int, intent: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        doc_ref = entities.get("document_reference")

        if not doc_ref:
            return {
                "status": "not_found",
                "intent": intent,
                "facts": {},
                "sources": [],
                "warnings": ["No document reference provided in request."]
            }

        # User-isolated query for the document
        doc = None
        if isinstance(doc_ref, int) or (isinstance(doc_ref, str) and doc_ref.isdigit()):
            doc = Document.query.filter_by(id=int(doc_ref), user_id=user_id).first()

        if not doc and isinstance(doc_ref, str):
            # Try invoice number search
            analysis = DocumentAnalysis.query.join(Document).filter(
                Document.user_id == user_id,
                DocumentAnalysis.invoice_number.ilike(f"%{doc_ref}%")
            ).first()
            if analysis:
                doc = analysis.document

        if not doc and isinstance(doc_ref, str):
            # Try filename search
            doc = Document.query.filter(
                Document.user_id == user_id,
                Document.original_filename.ilike(f"%{doc_ref}%")
            ).first()

        if not doc:
            # Document does not exist or does not belong to user
            return {
                "status": "not_found",
                "intent": intent,
                "facts": {},
                "sources": [],
                "warnings": ["Requested document was not found or access is unauthorized."]
            }

        anomalies = self.anomaly_service.get_document_anomalies(doc.id, user_id)
        source = self._format_doc_source(doc)

        facts = {
            "document_id": doc.id,
            "original_filename": doc.original_filename,
            "status": doc.status,
            "created_at": doc.created_at.strftime("%Y-%m-%d"),
            "vendor_name": doc.analysis.vendor_name if doc.analysis else None,
            "invoice_number": doc.analysis.invoice_number if doc.analysis else None,
            "total_amount": float(doc.analysis.total_amount) if doc.analysis and doc.analysis.total_amount else 0.0,
            "tax_amount": float(doc.analysis.tax_amount) if doc.analysis and doc.analysis.tax_amount else 0.0,
            "subtotal_amount": float(doc.analysis.subtotal_amount) if doc.analysis and doc.analysis.subtotal_amount else 0.0,
            "confidence_score": float(doc.analysis.confidence_score) if doc.analysis and doc.analysis.confidence_score else 0.0,
            "anomalies": anomalies,
            "anomalies_count": len(anomalies)
        }

        return {
            "status": "success",
            "intent": intent,
            "facts": facts,
            "sources": [source],
            "warnings": []
        }

    def _get_due_diligence_evidence(self, user_id: int) -> Dict[str, Any]:
        dd_report = self.due_diligence_service.get_due_diligence_report(user_id)

        return {
            "status": "success",
            "intent": "DUE_DILIGENCE",
            "facts": dd_report,
            "sources": [],
            "warnings": []
        }

    def _get_tax_summary_evidence(self, user_id: int) -> Dict[str, Any]:
        overview = self.financial_service.get_financial_overview(user_id)

        if overview["analyzed_documents"] == 0:
            return {
                "status": "insufficient_data",
                "intent": "TAX_SUMMARY",
                "facts": {},
                "sources": [],
                "warnings": ["No analyzed documents found for tax breakdown."]
            }

        return {
            "status": "success",
            "intent": "TAX_SUMMARY",
            "facts": {
                "total_spending": overview["total_spending"],
                "total_subtotal": overview["total_subtotal"],
                "total_tax": overview["total_tax"],
                "effective_tax_rate": overview["effective_tax_rate"],
                "analyzed_documents": overview["analyzed_documents"]
            },
            "sources": [],
            "warnings": []
        }

    def _get_payment_method_evidence(self, user_id: int) -> Dict[str, Any]:
        methods = self.financial_service.get_payment_method_distribution(user_id)

        if not methods:
            return {
                "status": "insufficient_data",
                "intent": "PAYMENT_METHOD_SUMMARY",
                "facts": {"methods": []},
                "sources": [],
                "warnings": ["No payment method distribution data available."]
            }

        return {
            "status": "success",
            "intent": "PAYMENT_METHOD_SUMMARY",
            "facts": {"payment_methods": methods},
            "sources": [],
            "warnings": []
        }

    def _get_general_summary_evidence(self, user_id: int) -> Dict[str, Any]:
        overview = self.financial_service.get_financial_overview(user_id)
        vendors = self.financial_service.get_spending_by_vendor(user_id, limit=1)
        categories = self.financial_service.get_spending_by_category(user_id)
        anomaly_summary = self.anomaly_service.get_anomaly_summary(user_id)
        dd_report = self.due_diligence_service.get_due_diligence_report(user_id)

        if overview["analyzed_documents"] == 0:
            return {
                "status": "insufficient_data",
                "intent": "GENERAL_FINANCIAL_SUMMARY",
                "facts": overview,
                "sources": [],
                "warnings": ["Workspace contains no analyzed documents."]
            }

        top_vendor = vendors[0] if vendors else None
        top_category = categories[0] if categories else None

        return {
            "status": "success",
            "intent": "GENERAL_FINANCIAL_SUMMARY",
            "facts": {
                "overview": overview,
                "top_vendor": top_vendor,
                "top_category": top_category,
                "anomaly_summary": anomaly_summary,
                "audit_score": dd_report.get("overall_score"),
                "risk_profile": dd_report.get("risk_profile")
            },
            "sources": [],
            "warnings": []
        }

    # Helper methods
    def _get_top_user_documents(self, user_id: int, limit: int = 5) -> List[Document]:
        return Document.query.filter_by(user_id=user_id, status='processed').order_by(Document.created_at.desc()).limit(limit).all()

    def _get_documents_by_category(self, user_id: int, category_name: str, limit: int = 5) -> List[Document]:
        return Document.query.join(DocumentAnalysis).filter(
            Document.user_id == user_id,
            Document.status == 'processed',
            DocumentAnalysis.category == category_name
        ).limit(limit).all()

    def _get_documents_by_vendor(self, user_id: int, vendor_name: str, limit: int = 5) -> List[Document]:
        return Document.query.join(DocumentAnalysis).filter(
            Document.user_id == user_id,
            Document.status == 'processed',
            DocumentAnalysis.vendor_name == vendor_name
        ).limit(limit).all()

    def _format_doc_source(self, doc: Document) -> Dict[str, Any]:
        return {
            "document_id": doc.id,
            "original_filename": doc.original_filename,
            "file_type": doc.file_type,
            "vendor_name": doc.analysis.vendor_name if doc.analysis else "Unknown",
            "invoice_number": doc.analysis.invoice_number if doc.analysis else None,
            "total_amount": float(doc.analysis.total_amount) if doc.analysis and doc.analysis.total_amount else 0.0
        }
