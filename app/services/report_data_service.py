"""Report Data Service for assembling verified report datasets across intelligence services."""

import logging
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.services.financial_intelligence_service import FinancialIntelligenceService
from app.services.anomaly_detection_service import AnomalyDetectionService
from app.services.due_diligence_service import DueDiligenceService
from app.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)


class ReportDataService:
    """Service to assemble period-scoped, verified datasets for financial report compilation."""

    def __init__(
        self,
        financial_service: Optional[FinancialIntelligenceService] = None,
        anomaly_service: Optional[AnomalyDetectionService] = None,
        due_diligence_service: Optional[DueDiligenceService] = None,
        document_repo: Optional[DocumentRepository] = None
    ) -> None:
        self.financial_service = financial_service or FinancialIntelligenceService()
        self.anomaly_service = anomaly_service or AnomalyDetectionService()
        self.due_diligence_service = due_diligence_service or DueDiligenceService()
        self.document_repo = document_repo or DocumentRepository()

    def resolve_period_bounds(
        self,
        period: str = 'all_time',
        custom_start: Optional[Any] = None,
        custom_end: Optional[Any] = None,
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> Tuple[str, Optional[date], Optional[date]]:
        """Resolves period string, custom range, or explicit period bounds into formatted label, start_date, and end_date."""
        # 1. Handle explicit period_start / period_end (e.g. from saved Report entity)
        if period_start is not None or period_end is not None:
            start = self._to_date(period_start)
            end = self._to_date(period_end)
            if start and end and start > end:
                raise ValueError("Invalid date range: start_date must be before or equal to end_date.")
            if start and end:
                label = f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}"
            elif start:
                label = f"From {start.strftime('%d %b %Y')}"
            elif end:
                label = f"Until {end.strftime('%d %b %Y')}"
            else:
                label = "All Time"
            return label, start, end

        today = date.today()

        if period == 'current_month':
            start = date(today.year, today.month, 1)
            end = today
            label = start.strftime("Current Month (%b %Y)")
            return label, start, end

        elif period == 'previous_month':
            first_of_curr = date(today.year, today.month, 1)
            end = first_of_curr - timedelta(days=1)
            start = date(end.year, end.month, 1)
            label = start.strftime("Previous Month (%b %Y)")
            return label, start, end

        elif period == 'current_quarter':
            q_month = ((today.month - 1) // 3) * 3 + 1
            start = date(today.year, q_month, 1)
            end = today
            q_num = (today.month - 1) // 3 + 1
            label = f"Current Quarter (Q{q_num} {today.year})"
            return label, start, end

        elif period == 'previous_quarter':
            curr_q_month = ((today.month - 1) // 3) * 3 + 1
            first_of_curr_q = date(today.year, curr_q_month, 1)
            end = first_of_curr_q - timedelta(days=1)
            prev_q_month = ((end.month - 1) // 3) * 3 + 1
            start = date(end.year, prev_q_month, 1)
            q_num = (end.month - 1) // 3 + 1
            label = f"Previous Quarter (Q{q_num} {end.year})"
            return label, start, end

        elif period == 'current_year':
            start = date(today.year, 1, 1)
            end = today
            label = f"Current Year ({today.year})"
            return label, start, end

        elif period == 'previous_year':
            prev_y = today.year - 1
            start = date(prev_y, 1, 1)
            end = date(prev_y, 12, 31)
            label = f"Previous Year ({prev_y})"
            return label, start, end

        elif period == 'custom':
            start_dt = self._to_date(custom_start)
            end_dt = self._to_date(custom_end)
            if not start_dt or not end_dt:
                raise ValueError("Custom period requires valid start_date and end_date.")
            if start_dt > end_dt:
                raise ValueError("Invalid custom date range: start_date must be before or equal to end_date.")
            label = f"Custom ({start_dt.strftime('%d %b %Y')} – {end_dt.strftime('%d %b %Y')})"
            return label, start_dt, end_dt

        return "All Time", None, None

    def _to_date(self, val: Any) -> Optional[date]:
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            try:
                return datetime.strptime(val.strip(), "%Y-%m-%d").date()
            except ValueError:
                return None
        return None

    def get_report_dataset(
        self,
        user_id: int,
        report_type: str,
        period: str = 'all_time',
        custom_start: Optional[Any] = None,
        custom_end: Optional[Any] = None,
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Assembles verified report facts and source document list for the report period."""
        period_label, start_date, end_date = self.resolve_period_bounds(
            period=period,
            custom_start=custom_start,
            custom_end=custom_end,
            period_start=period_start,
            period_end=period_end
        )

        # 1. Financial Overview
        overview = self.financial_service.get_financial_overview(
            user_id, period_start=start_date, period_end=end_date
        )

        # 2. Categories & Vendors
        categories = self.financial_service.get_spending_by_category(
            user_id, period_start=start_date, period_end=end_date
        )
        vendors = self.financial_service.get_spending_by_vendor(
            user_id, limit=15, period_start=start_date, period_end=end_date
        )

        # 3. Monthly Trends & Payment Methods
        monthly_trends = self.financial_service.get_monthly_spending_patterns(
            user_id, months=12, period_start=start_date, period_end=end_date
        )
        payment_methods = self.financial_service.get_payment_method_distribution(
            user_id, period_start=start_date, period_end=end_date
        )
        concentration = self.financial_service.get_spending_concentration(
            user_id, period_start=start_date, period_end=end_date
        )

        # 4. Anomalies & Risk Assessment
        anomalies = self.anomaly_service.get_user_anomalies(
            user_id, period_start=start_date, period_end=end_date
        )
        anomaly_summary = self.anomaly_service.get_anomaly_summary(
            user_id, period_start=start_date, period_end=end_date
        )

        # 5. Due Diligence Metrics
        due_diligence = self.due_diligence_service.get_due_diligence_report(
            user_id, period_start=start_date, period_end=end_date
        )

        # 6. Financial Observations
        observations = self.financial_service.get_financial_observations(
            user_id, period_start=start_date, period_end=end_date
        )

        # 7. Source Documents list for period
        source_docs = self._get_source_documents(user_id, start_date, end_date)

        return {
            "report_type": report_type,
            "period": period,
            "period_label": period_label,
            "period_start": start_date,
            "period_end": end_date,
            "generated_at": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
            "overview": overview,
            "categories": categories,
            "vendors": vendors,
            "monthly_trends": monthly_trends,
            "payment_methods": payment_methods,
            "concentration": concentration,
            "anomalies": anomalies,
            "anomaly_summary": anomaly_summary,
            "due_diligence": due_diligence,
            "observations": observations,
            "source_documents": source_docs
        }

    def _get_source_documents(
        self,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Fetch list of user source documents belonging to the reporting period."""
        query = Document.query.filter_by(user_id=user_id, status='processed')

        if start_date:
            start_dt = datetime.combine(start_date, datetime.min.time())
            query = query.filter(Document.created_at >= start_dt)
        if end_date:
            end_dt = datetime.combine(end_date, datetime.max.time())
            query = query.filter(Document.created_at <= end_dt)

        docs = query.order_by(Document.created_at.desc()).all()

        source_list = []
        for d in docs:
            analysis: Optional[DocumentAnalysis] = d.analysis
            source_list.append({
                "document_id": d.id,
                "original_filename": d.original_filename,
                "file_type": d.file_type,
                "vendor_name": analysis.vendor_name if analysis else "Unknown",
                "invoice_number": analysis.invoice_number if analysis else None,
                "invoice_date": analysis.invoice_date.strftime("%Y-%m-%d") if (analysis and analysis.invoice_date) else d.created_at.strftime("%Y-%m-%d"),
                "total_amount": float(analysis.total_amount or 0.0) if analysis else 0.0,
                "category": analysis.category if analysis else "General"
            })

        return source_list
