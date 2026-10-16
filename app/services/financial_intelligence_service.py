"""Financial Intelligence Service for aggregating user document analytics and spending patterns."""

import logging
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import func, desc

from app.extensions import db
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_analysis_repository import DocumentAnalysisRepository

logger = logging.getLogger(__name__)


class FinancialIntelligenceService:
    """Service to compute user-scoped financial intelligence, spending patterns, and observations."""

    def __init__(
        self,
        document_repo: Optional[DocumentRepository] = None,
        analysis_repo: Optional[DocumentAnalysisRepository] = None
    ) -> None:
        self.document_repo = document_repo or DocumentRepository()
        self.analysis_repo = analysis_repo or DocumentAnalysisRepository()

    def _get_date_bounds(
        self,
        date_range: str = 'all',
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Convert date range string or explicit dates into start and end datetimes."""
        if period_start or period_end:
            start_dt = None
            end_dt = None

            if isinstance(period_start, str):
                try:
                    start_dt = datetime.strptime(period_start, "%Y-%m-%d")
                except ValueError:
                    start_dt = None
            elif isinstance(period_start, datetime):
                start_dt = period_start
            elif isinstance(period_start, date):
                start_dt = datetime.combine(period_start, datetime.min.time())

            if isinstance(period_end, str):
                try:
                    end_dt = datetime.strptime(period_end, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                except ValueError:
                    end_dt = None
            elif isinstance(period_end, datetime):
                end_dt = period_end
            elif isinstance(period_end, date):
                end_dt = datetime.combine(period_end, datetime.max.time())

            return start_dt, end_dt

        now = datetime.now(timezone.utc)
        if date_range == '30d':
            return now - timedelta(days=30), None
        elif date_range == '3m':
            return now - timedelta(days=90), None
        elif date_range == '6m':
            return now - timedelta(days=180), None
        elif date_range == '12m':
            return now - timedelta(days=365), None
        return None, None

    def get_financial_overview(
        self,
        user_id: int,
        date_range: str = 'all',
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Calculates executive KPI metrics from real analyzed user documents."""
        try:
            start_date, end_date = self._get_date_bounds(date_range, period_start, period_end)

            # Base document query
            doc_query = Document.query.filter_by(user_id=user_id)
            if start_date:
                doc_query = doc_query.filter(Document.created_at >= start_date)
            if end_date:
                doc_query = doc_query.filter(Document.created_at <= end_date)

            all_docs = doc_query.all()
            total_documents = len(all_docs)
            pending_documents = sum(1 for d in all_docs if d.status == 'pending')
            failed_documents = sum(1 for d in all_docs if d.status == 'failed')
            processed_documents = sum(1 for d in all_docs if d.status == 'processed')

            # Analyzed document records
            analysis_query = db.session.query(DocumentAnalysis).join(
                Document, DocumentAnalysis.document_id == Document.id
            ).filter(Document.user_id == user_id, Document.status == 'processed')

            date_col = func.coalesce(DocumentAnalysis.invoice_date, Document.created_at)
            if start_date:
                analysis_query = analysis_query.filter(date_col >= start_date)
            if end_date:
                analysis_query = analysis_query.filter(date_col <= end_date)

            analyses: List[DocumentAnalysis] = analysis_query.all()
            analyzed_documents = len(analyses)

            if analyzed_documents == 0:
                return {
                    "total_spending": 0.0,
                    "total_documents": total_documents,
                    "analyzed_documents": 0,
                    "pending_documents": pending_documents,
                    "failed_documents": failed_documents,
                    "processed_documents": processed_documents,
                    "average_transaction": 0.0,
                    "highest_transaction": {"amount": 0.0, "vendor": "-", "doc_id": None},
                    "lowest_transaction": 0.0,
                    "total_tax": 0.0,
                    "total_subtotal": 0.0,
                    "effective_tax_rate": 0.0,
                    "invoices_count": 0,
                    "receipts_count": 0,
                    "review_needed_count": pending_documents + failed_documents
                }

            amounts = [float(a.total_amount or 0.0) for a in analyses]
            taxes = [float(a.tax_amount or 0.0) for a in analyses]
            subtotals = [float(a.subtotal_amount or 0.0) for a in analyses]

            total_spending = sum(amounts)
            total_tax = sum(taxes)
            total_subtotal = sum(subtotals)
            average_transaction = total_spending / analyzed_documents if analyzed_documents > 0 else 0.0

            # Find max transaction
            max_analysis = max(analyses, key=lambda a: float(a.total_amount or 0.0))
            highest_transaction = {
                "amount": float(max_analysis.total_amount or 0.0),
                "vendor": max_analysis.vendor_name or "Unknown",
                "doc_id": max_analysis.document_id
            }

            positive_amounts = [amt for amt in amounts if amt > 0]
            lowest_transaction = min(positive_amounts) if positive_amounts else 0.0

            effective_tax_rate = (total_tax / total_subtotal * 100) if total_subtotal > 0 else 0.0

            invoices_count = sum(1 for a in analyses if a.invoice_number and a.invoice_number.strip())
            receipts_count = analyzed_documents - invoices_count

            low_confidence_count = sum(1 for a in analyses if (a.confidence_score or 0.0) < 0.75)
            review_needed_count = pending_documents + failed_documents + low_confidence_count

            return {
                "total_spending": round(total_spending, 2),
                "total_documents": total_documents,
                "analyzed_documents": analyzed_documents,
                "pending_documents": pending_documents,
                "failed_documents": failed_documents,
                "processed_documents": processed_documents,
                "average_transaction": round(average_transaction, 2),
                "highest_transaction": highest_transaction,
                "lowest_transaction": round(lowest_transaction, 2),
                "total_tax": round(total_tax, 2),
                "total_subtotal": round(total_subtotal, 2),
                "effective_tax_rate": round(effective_tax_rate, 1),
                "invoices_count": invoices_count,
                "receipts_count": receipts_count,
                "review_needed_count": review_needed_count
            }
        except Exception as e:
            logger.error(f"Error calculating financial overview for user {user_id}: {e}")
            return {
                "total_spending": 0.0,
                "total_documents": 0,
                "analyzed_documents": 0,
                "pending_documents": 0,
                "failed_documents": 0,
                "processed_documents": 0,
                "average_transaction": 0.0,
                "highest_transaction": {"amount": 0.0, "vendor": "-", "doc_id": None},
                "lowest_transaction": 0.0,
                "total_tax": 0.0,
                "total_subtotal": 0.0,
                "effective_tax_rate": 0.0,
                "invoices_count": 0,
                "receipts_count": 0,
                "review_needed_count": 0
            }

    def get_spending_by_category(
        self,
        user_id: int,
        date_range: str = 'all',
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Calculates spending breakdown and percentage share per expense category."""
        try:
            start_date, end_date = self._get_date_bounds(date_range, period_start, period_end)

            query = db.session.query(
                func.coalesce(DocumentAnalysis.category, 'General').label('category'),
                func.sum(DocumentAnalysis.total_amount).label('total'),
                func.count(DocumentAnalysis.id).label('count')
            ).join(Document, DocumentAnalysis.document_id == Document.id)\
             .filter(Document.user_id == user_id, Document.status == 'processed')

            date_col = func.coalesce(DocumentAnalysis.invoice_date, Document.created_at)
            if start_date:
                query = query.filter(date_col >= start_date)
            if end_date:
                query = query.filter(date_col <= end_date)

            query = query.group_by('category').order_by(desc('total'))
            rows = query.all()

            grand_total = sum(float(r.total or 0.0) for r in rows)

            categories = []
            for row in rows:
                total = float(row.total or 0.0)
                pct = (total / grand_total * 100) if grand_total > 0 else 0.0
                categories.append({
                    "category": row.category or "General",
                    "total": round(total, 2),
                    "count": int(row.count or 0),
                    "percentage": round(pct, 1)
                })

            return categories
        except Exception as e:
            logger.error(f"Error calculating category spending for user {user_id}: {e}")
            return []

    def get_spending_by_vendor(
        self,
        user_id: int,
        limit: int = 10,
        date_range: str = 'all',
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Calculates spending per vendor with transaction counts and averages."""
        try:
            start_date, end_date = self._get_date_bounds(date_range, period_start, period_end)

            query = db.session.query(
                func.coalesce(DocumentAnalysis.vendor_name, 'Uncategorized Vendor').label('vendor'),
                func.sum(DocumentAnalysis.total_amount).label('total'),
                func.count(DocumentAnalysis.id).label('count'),
                func.avg(DocumentAnalysis.total_amount).label('avg_amount')
            ).join(Document, DocumentAnalysis.document_id == Document.id)\
             .filter(Document.user_id == user_id, Document.status == 'processed')

            date_col = func.coalesce(DocumentAnalysis.invoice_date, Document.created_at)
            if start_date:
                query = query.filter(date_col >= start_date)
            if end_date:
                query = query.filter(date_col <= end_date)

            query = query.group_by('vendor').order_by(desc('total')).limit(limit)
            rows = query.all()

            # Calculate total for percentage calculation
            grand_total_query = db.session.query(
                func.sum(DocumentAnalysis.total_amount)
            ).join(Document, DocumentAnalysis.document_id == Document.id)\
             .filter(Document.user_id == user_id, Document.status == 'processed')

            if start_date:
                grand_total_query = grand_total_query.filter(date_col >= start_date)
            if end_date:
                grand_total_query = grand_total_query.filter(date_col <= end_date)

            grand_total = float(grand_total_query.scalar() or 0.0)

            vendors = []
            for row in rows:
                total = float(row.total or 0.0)
                pct = (total / grand_total * 100) if grand_total > 0 else 0.0
                vendors.append({
                    "vendor": row.vendor or "Uncategorized Vendor",
                    "total": round(total, 2),
                    "transaction_count": int(row.count or 0),
                    "average_transaction": round(float(row.avg_amount or 0.0), 2),
                    "percentage": round(pct, 1)
                })

            return vendors
        except Exception as e:
            logger.error(f"Error calculating vendor spending for user {user_id}: {e}")
            return []

    def get_monthly_spending_patterns(
        self,
        user_id: int,
        months: int = 12,
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Calculates chronological monthly spending pattern data for trends and charts."""
        try:
            date_expr = func.coalesce(DocumentAnalysis.invoice_date, Document.created_at)

            bind = db.session.get_bind()
            if bind.dialect.name == 'sqlite':
                month_expr = func.strftime('%Y-%m', date_expr)
            else:
                month_expr = func.date_format(date_expr, '%Y-%m')

            query = db.session.query(
                month_expr.label('month'),
                func.sum(DocumentAnalysis.total_amount).label('total'),
                func.count(DocumentAnalysis.id).label('count'),
                func.avg(DocumentAnalysis.total_amount).label('avg_amount')
            ).join(Document, DocumentAnalysis.document_id == Document.id)\
             .filter(Document.user_id == user_id, Document.status == 'processed')

            start_date, end_date = self._get_date_bounds('all', period_start, period_end)
            if start_date:
                query = query.filter(date_expr >= start_date)
            if end_date:
                query = query.filter(date_expr <= end_date)

            query = query.group_by('month').order_by('month')
            rows = query.all()
            if not rows:
                return []

            results = []
            selected_rows = rows if (period_start or period_end) else rows[-months:]
            for row in selected_rows:
                if not row.month:
                    continue
                try:
                    dt = datetime.strptime(row.month, '%Y-%m')
                    month_name = dt.strftime('%b %Y')
                except ValueError:
                    month_name = str(row.month)

                results.append({
                    "month": row.month,
                    "month_name": month_name,
                    "total": round(float(row.total or 0.0), 2),
                    "count": int(row.count or 0),
                    "average": round(float(row.avg_amount or 0.0), 2)
                })

            return results
        except Exception as e:
            logger.error(f"Error calculating monthly spending patterns for user {user_id}: {e}")
            return []

    def get_quarterly_spending(
        self,
        user_id: int,
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Aggregates user spending into quarterly cohorts."""
        try:
            monthly = self.get_monthly_spending_patterns(user_id, months=24, period_start=period_start, period_end=period_end)
            if not monthly:
                return []

            quarters: Dict[str, Dict[str, Any]] = {}
            for item in monthly:
                month_str = item["month"] # YYYY-MM
                year, m = month_str.split('-')
                q_num = (int(m) - 1) // 3 + 1
                q_key = f"{year}-Q{q_num}"

                if q_key not in quarters:
                    quarters[q_key] = {"quarter": q_key, "total": 0.0, "count": 0}
                quarters[q_key]["total"] += item["total"]
                quarters[q_key]["count"] += item["count"]

            return [
                {
                    "quarter": q["quarter"],
                    "total": round(q["total"], 2),
                    "count": q["count"]
                }
                for q in quarters.values()
            ]
        except Exception as e:
            logger.error(f"Error calculating quarterly spending for user {user_id}: {e}")
            return []

    def get_payment_method_distribution(
        self,
        user_id: int,
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Calculates breakdown of payment methods across analyzed records."""
        try:
            query = db.session.query(
                func.coalesce(DocumentAnalysis.payment_method, 'Unknown').label('method'),
                func.sum(DocumentAnalysis.total_amount).label('total'),
                func.count(DocumentAnalysis.id).label('count')
            ).join(Document, DocumentAnalysis.document_id == Document.id)\
             .filter(Document.user_id == user_id, Document.status == 'processed')

            start_date, end_date = self._get_date_bounds('all', period_start, period_end)
            date_col = func.coalesce(DocumentAnalysis.invoice_date, Document.created_at)
            if start_date:
                query = query.filter(date_col >= start_date)
            if end_date:
                query = query.filter(date_col <= end_date)

            query = query.group_by('method').order_by(desc('total'))

            rows = query.all()
            grand_total = sum(float(r.total or 0.0) for r in rows)

            results = []
            for r in rows:
                tot = float(r.total or 0.0)
                pct = (tot / grand_total * 100) if grand_total > 0 else 0.0
                results.append({
                    "method": r.method or "Unknown",
                    "total": round(tot, 2),
                    "count": int(r.count or 0),
                    "percentage": round(pct, 1)
                })
            return results
        except Exception as e:
            logger.error(f"Error calculating payment methods for user {user_id}: {e}")
            return []

    def get_recurring_spending(
        self,
        user_id: int,
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Identifies recurring vendor relationships with multiple recorded transactions."""
        try:
            vendors = self.get_spending_by_vendor(user_id, limit=20, period_start=period_start, period_end=period_end)
            recurring = [v for v in vendors if v["transaction_count"] >= 2]
            return recurring
        except Exception as e:
            logger.error(f"Error calculating recurring spending for user {user_id}: {e}")
            return []

    def get_spending_concentration(
        self,
        user_id: int,
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Analyzes spending concentration among top vendors."""
        try:
            vendors = self.get_spending_by_vendor(user_id, limit=10, period_start=period_start, period_end=period_end)
            if not vendors:
                return {
                    "top_1_pct": 0.0,
                    "top_3_pct": 0.0,
                    "top_5_pct": 0.0,
                    "concentration_level": "Low",
                    "observation": "No vendor concentration data available."
                }

            top_1 = vendors[0]["percentage"] if len(vendors) >= 1 else 0.0
            top_3 = sum(v["percentage"] for v in vendors[:3])
            top_5 = sum(v["percentage"] for v in vendors[:5])

            if top_3 >= 75.0 or top_1 >= 50.0:
                concentration_level = "Severe"
            elif top_3 >= 50.0:
                concentration_level = "High"
            elif top_3 >= 30.0:
                concentration_level = "Moderate"
            else:
                concentration_level = "Low"

            top_vendors_str = ", ".join([v["vendor"] for v in vendors[:min(3, len(vendors))]])
            if len(vendors) >= 3:
                observation = f"Top 3 vendors ({top_vendors_str}) represent {round(top_3, 1)}% of total recorded spending."
            elif len(vendors) >= 1:
                observation = f"Top vendor '{vendors[0]['vendor']}' accounts for {round(top_1, 1)}% of total recorded spending."
            else:
                observation = "Spending is diversified across multiple vendors."

            return {
                "top_1_pct": round(top_1, 1),
                "top_3_pct": round(top_3, 1),
                "top_5_pct": round(top_5, 1),
                "concentration_level": concentration_level,
                "observation": observation
            }
        except Exception as e:
            logger.error(f"Error calculating concentration for user {user_id}: {e}")
            return {
                "top_1_pct": 0.0,
                "top_3_pct": 0.0,
                "top_5_pct": 0.0,
                "concentration_level": "Low",
                "observation": "Unable to calculate vendor concentration."
            }

    def get_financial_observations(
        self,
        user_id: int,
        period_start: Optional[Any] = None,
        period_end: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Generates deterministic, explainable analytical observations based on verified documents."""
        observations = []
        try:
            overview = self.get_financial_overview(user_id, period_start=period_start, period_end=period_end)
            if overview["analyzed_documents"] == 0:
                return []

            # 1. Volume & Average observation
            total_spend = overview["total_spending"]
            doc_count = overview["analyzed_documents"]
            avg_spend = overview["average_transaction"]
            observations.append({
                "type": "volume",
                "title": "Expense Volume & Average",
                "text": f"Across {doc_count} analyzed business documents, recorded spending totals ₹{total_spend:,.2f} with an average transaction value of ₹{avg_spend:,.2f}.",
                "level": "info"
            })

            # 2. Category Leader observation
            categories = self.get_spending_by_category(user_id, period_start=period_start, period_end=period_end)
            if categories:
                top_cat = categories[0]
                observations.append({
                    "type": "category",
                    "title": "Primary Expenditure Category",
                    "text": f"'{top_cat['category']}' represents your highest spending category at ₹{top_cat['total']:,.2f} ({top_cat['percentage']}% of total recorded expenses).",
                    "level": "info"
                })

            # 3. Vendor Concentration observation
            concentration = self.get_spending_concentration(user_id, period_start=period_start, period_end=period_end)
            if concentration["top_3_pct"] > 0:
                level = "warning" if concentration["concentration_level"] in ["High", "Severe"] else "info"
                observations.append({
                    "type": "concentration",
                    "title": f"{concentration['concentration_level']} Vendor Concentration",
                    "text": concentration["observation"],
                    "level": level
                })

            # 4. Monthly Trend observation
            monthly = self.get_monthly_spending_patterns(user_id, months=3, period_start=period_start, period_end=period_end)
            if len(monthly) >= 2:
                curr_month = monthly[-1]
                prev_month = monthly[-2]
                if prev_month["total"] > 0:
                    pct_change = ((curr_month["total"] - prev_month["total"]) / prev_month["total"]) * 100
                    direction = "increased" if pct_change >= 0 else "decreased"
                    observations.append({
                        "type": "trend",
                        "title": f"Month-over-Month Trend ({curr_month['month_name']})",
                        "text": f"Recorded spending {direction} by {abs(round(pct_change, 1))}% in {curr_month['month_name']} (₹{curr_month['total']:,.2f}) compared to {prev_month['month_name']} (₹{prev_month['total']:,.2f}).",
                        "level": "info" if abs(pct_change) < 50 else "warning"
                    })

            # 5. Tax efficiency observation
            if overview["total_tax"] > 0 and overview["total_subtotal"] > 0:
                observations.append({
                    "type": "tax",
                    "title": "Tax Contribution",
                    "text": f"Recorded tax accounts for ₹{overview['total_tax']:,.2f}, representing an effective tax rate of {overview['effective_tax_rate']}% on analyzed subtotals.",
                    "level": "info"
                })

        except Exception as e:
            logger.error(f"Error generating financial observations for user {user_id}: {e}")

        return observations
