"""Due Diligence Service for calculating internal audit and financial compliance indicators."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.models.document import Document
from app.services.financial_intelligence_service import FinancialIntelligenceService
from app.services.anomaly_detection_service import AnomalyDetectionService

logger = logging.getLogger(__name__)


class DueDiligenceService:
    """Service providing document-based analytical indicators for financial diligence review."""

    def __init__(
        self,
        financial_service: Optional[FinancialIntelligenceService] = None,
        anomaly_service: Optional[AnomalyDetectionService] = None
    ) -> None:
        self.financial_service = financial_service or FinancialIntelligenceService()
        self.anomaly_service = anomaly_service or AnomalyDetectionService()

    def get_due_diligence_report(
        self,
        user_id: int,
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Calculates internal analytical due-diligence indicators from real user records."""
        try:
            overview = self.financial_service.get_financial_overview(user_id, period_start=period_start, period_end=period_end)
            total_docs = overview["total_documents"]
            analyzed_docs = overview["analyzed_documents"]
            pending_docs = overview["pending_documents"]
            failed_docs = overview["failed_documents"]

            if total_docs == 0:
                return {
                    "total_docs": 0,
                    "analyzed_docs": 0,
                    "completeness_score": 100,
                    "consistency_score": 100,
                    "stability_rating": "Insufficient Data",
                    "concentration_rating": "Low",
                    "overall_score": 100,
                    "risk_profile": "Low risk profile",
                    "highest_vendor": None,
                    "highest_vendor_pct": 0,
                    "top_3_vendor_pct": 0,
                    "anomalies_count": 0,
                    "high_risk_anomalies_count": 0,
                    "action_items": []
                }

            # 1. Document Completeness Score (0-100)
            proc_ratio = (analyzed_docs / total_docs) if total_docs > 0 else 1.0
            completeness_score = int(max(20, min(100, round(proc_ratio * 100 - (failed_docs / total_docs * 30)))))

            # 2. Anomalies Assessment
            anomalies = self.anomaly_service.get_user_anomalies(user_id, period_start=period_start, period_end=period_end)
            anomaly_summary = self.anomaly_service.get_anomaly_summary(user_id, period_start=period_start, period_end=period_end)
            total_anomalies = anomaly_summary["total"]
            high_risk_count = anomaly_summary["high_risk_count"]

            # 3. Financial Consistency Score (0-100)
            consistency_penalty = (anomaly_summary["critical"] * 25) + (anomaly_summary["high"] * 15) + (anomaly_summary["medium"] * 8)
            consistency_score = int(max(25, min(100, 100 - consistency_penalty)))

            # 4. Vendor Concentration
            concentration = self.financial_service.get_spending_concentration(user_id, period_start=period_start, period_end=period_end)
            concentration_rating = concentration.get("concentration_level", "Low")
            top_1_pct = concentration.get("top_1_pct", 0)
            top_3_pct = concentration.get("top_3_pct", 0)

            vendors = self.financial_service.get_spending_by_vendor(user_id, limit=1, period_start=period_start, period_end=period_end)
            highest_vendor = vendors[0]["vendor"] if vendors else None
            highest_vendor_pct = int(top_1_pct)

            # 5. Spending Stability Rating
            monthly = self.financial_service.get_monthly_spending_patterns(user_id, months=6, period_start=period_start, period_end=period_end)
            if len(monthly) < 2:
                stability_rating = "Insufficient Data"
                stability_score = 75
            else:
                totals = [m["total"] for m in monthly if m["total"] > 0]
                if len(totals) >= 2:
                    avg_m = sum(totals) / len(totals)
                    var_m = sum((t - avg_m) ** 2 for t in totals) / len(totals)
                    std_m = var_m ** 0.5
                    cov = (std_m / avg_m) if avg_m > 0 else 0
                    if cov < 0.35:
                        stability_rating = "High"
                        stability_score = 95
                    elif cov < 0.75:
                        stability_rating = "Moderate"
                        stability_score = 80
                    else:
                        stability_rating = "Volatile"
                        stability_score = 55
                else:
                    stability_rating = "Moderate"
                    stability_score = 75

            # 6. Concentration penalty for overall score
            concentration_score = 90
            if concentration_rating == "Severe":
                concentration_score = 50
            elif concentration_rating == "High":
                concentration_score = 65
            elif concentration_rating == "Moderate":
                concentration_score = 80

            # 7. Overall Audit Health Index (Weighted)
            overall_score = int(round(
                completeness_score * 0.30 +
                consistency_score * 0.40 +
                stability_score * 0.15 +
                concentration_score * 0.15
            ))
            overall_score = max(30, min(100, overall_score))

            if overall_score >= 85:
                risk_profile = "Low risk profile"
            elif overall_score >= 60:
                risk_profile = "Medium risk profile"
            else:
                risk_profile = "High risk profile"

            # 8. Action Items
            action_items = []
            if failed_docs > 0:
                action_items.append(f"Reprocess {failed_docs} failed document extraction(s).")
            if high_risk_count > 0:
                action_items.append(f"Review {high_risk_count} high-risk financial anomalies (duplicate invoices or unusual amounts).")
            if concentration_rating in ["High", "Severe"]:
                action_items.append(f"Evaluate vendor risk diversification (top vendor represents {highest_vendor_pct}% of spending).")
            if pending_docs > 0:
                action_items.append(f"{pending_docs} document(s) are pending review and approval.")

            return {
                "total_docs": total_docs,
                "analyzed_docs": analyzed_docs,
                "completeness_score": completeness_score,
                "consistency_score": consistency_score,
                "stability_rating": stability_rating,
                "concentration_rating": concentration_rating,
                "overall_score": overall_score,
                "risk_profile": risk_profile,
                "highest_vendor": highest_vendor,
                "highest_vendor_pct": highest_vendor_pct,
                "top_3_vendor_pct": round(top_3_pct, 1),
                "anomalies_count": total_anomalies,
                "high_risk_anomalies_count": high_risk_count,
                "action_items": action_items
            }

        except Exception as e:
            logger.error(f"Error calculating due diligence report for user {user_id}: {e}")
            return {
                "total_docs": 0,
                "analyzed_docs": 0,
                "completeness_score": 100,
                "consistency_score": 100,
                "stability_rating": "Insufficient Data",
                "concentration_rating": "Low",
                "overall_score": 100,
                "risk_profile": "Low risk profile",
                "highest_vendor": None,
                "highest_vendor_pct": 0,
                "top_3_vendor_pct": 0,
                "anomalies_count": 0,
                "high_risk_anomalies_count": 0,
                "action_items": []
            }
