"""Dashboard service for orchestrating analytics."""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple
import logging

from app.repositories.dashboard_repository import DashboardRepository

logger = logging.getLogger(__name__)

class DashboardService:
    """Service to handle dashboard data orchestration."""

    def __init__(self, dashboard_repository: DashboardRepository):
        self.dashboard_repo = dashboard_repository

    def _get_date_range(self, range_filter: str) -> Tuple[datetime, datetime]:
        """Convert a range string into start and end datetimes."""
        end_date = datetime.now(timezone.utc)
        start_date = None

        if range_filter == '30d':
            start_date = end_date - timedelta(days=30)
        elif range_filter == '3m':
            start_date = end_date - timedelta(days=90)
        elif range_filter == '6m':
            start_date = end_date - timedelta(days=180)
        elif range_filter == '12m':
            start_date = end_date - timedelta(days=365)
            
        return start_date, end_date

    def get_dashboard_data(self, user_id: int, date_range: str = '12m') -> Dict[str, Any]:
        """
        Get all data required for the dashboard.
        """
        try:
            start_date, end_date = self._get_date_range(date_range)

            # Parallelizing or sequential is fine since these are fast aggregated queries.
            metrics = self.dashboard_repo.get_financial_metrics(user_id, start_date, end_date)
            counts = self.dashboard_repo.get_document_counts(user_id, start_date, end_date)
            
            # Combine metrics and counts
            combined_metrics = {
                "total_documents": counts.get('total', 0),
                "total_expenses": metrics.get('total_expenses', 0.0),
                "total_tax": metrics.get('total_tax', 0.0),
                "average_expense": metrics.get('average_expense', 0.0),
                "processed_documents": counts.get('processed', 0),
                "pending_documents": counts.get('pending', 0),
                "failed_documents": counts.get('failed', 0)
            }

            category_breakdown = self.dashboard_repo.get_category_breakdown(user_id, start_date, end_date)
            vendor_breakdown = self.dashboard_repo.get_vendor_breakdown(user_id, start_date, end_date, limit=10)
            monthly_trend = self.dashboard_repo.get_monthly_trend(user_id, start_date, end_date)
            recent_documents = self.dashboard_repo.get_recent_documents(user_id, limit=5)

            return {
                "metrics": combined_metrics,
                "category_breakdown": category_breakdown,
                "vendor_breakdown": vendor_breakdown,
                "monthly_trend": monthly_trend,
                "recent_documents": recent_documents
            }
        except Exception as e:
            logger.error(f"Error fetching dashboard data for user {user_id}: {str(e)}")
            raise e
