"""Dashboard repository for aggregating financial data."""

from sqlalchemy import func, desc, or_
from datetime import datetime
from app.extensions import db
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis


class DashboardRepository:
    """Repository for dashboard aggregations."""

    def get_financial_metrics(self, user_id: int, start_date: datetime = None, end_date: datetime = None):
        """Get high-level financial metrics."""
        query = db.session.query(
            func.sum(DocumentAnalysis.total_amount).label('total_expenses'),
            func.sum(DocumentAnalysis.tax_amount).label('total_tax'),
            func.avg(DocumentAnalysis.total_amount).label('average_expense'),
            func.count(DocumentAnalysis.id).label('analyzed_count')
        ).join(Document, DocumentAnalysis.document_id == Document.id)\
         .filter(Document.user_id == user_id)

        if start_date:
            query = query.filter(Document.created_at >= start_date)
        if end_date:
            query = query.filter(Document.created_at <= end_date)

        result = query.first()
        return {
            'total_expenses': float(result.total_expenses or 0.0),
            'total_tax': float(result.total_tax or 0.0),
            'average_expense': float(result.average_expense or 0.0),
            'analyzed_count': result.analyzed_count or 0
        }

    def get_document_counts(self, user_id: int, start_date: datetime = None, end_date: datetime = None):
        """Get document counts by status."""
        query = db.session.query(
            Document.status,
            func.count(Document.id).label('count')
        ).filter(Document.user_id == user_id)

        if start_date:
            query = query.filter(Document.created_at >= start_date)
        if end_date:
            query = query.filter(Document.created_at <= end_date)

        query = query.group_by(Document.status)
        results = query.all()
        
        counts = {'pending': 0, 'processed': 0, 'failed': 0, 'total': 0}
        for row in results:
            counts[row.status] = row.count
            counts['total'] += row.count
            
        return counts

    def get_category_breakdown(self, user_id: int, start_date: datetime = None, end_date: datetime = None):
        """Get spending by category."""
        query = db.session.query(
            func.coalesce(DocumentAnalysis.category, 'General').label('category'),
            func.sum(DocumentAnalysis.total_amount).label('total')
        ).join(Document, DocumentAnalysis.document_id == Document.id)\
         .filter(Document.user_id == user_id)

        if start_date:
            query = query.filter(Document.created_at >= start_date)
        if end_date:
            query = query.filter(Document.created_at <= end_date)

        query = query.group_by('category').order_by(desc('total'))
        
        return [{'category': row.category, 'total': float(row.total or 0.0)} for row in query.all()]

    def get_vendor_breakdown(self, user_id: int, start_date: datetime = None, end_date: datetime = None, limit: int = 5):
        """Get spending by top vendors."""
        query = db.session.query(
            DocumentAnalysis.vendor_name,
            func.sum(DocumentAnalysis.total_amount).label('total')
        ).join(Document, DocumentAnalysis.document_id == Document.id)\
         .filter(Document.user_id == user_id)\
         .filter(DocumentAnalysis.vendor_name != None)\
         .filter(DocumentAnalysis.vendor_name != '')

        if start_date:
            query = query.filter(Document.created_at >= start_date)
        if end_date:
            query = query.filter(Document.created_at <= end_date)

        query = query.group_by(DocumentAnalysis.vendor_name).order_by(desc('total')).limit(limit)
        
        return [{'vendor': row.vendor_name, 'total': float(row.total or 0.0)} for row in query.all()]

    def get_monthly_trend(self, user_id: int, start_date: datetime = None, end_date: datetime = None):
        """Get spending trend by month."""
        # Use COALESCE to fallback to created_at if invoice_date is NULL
        date_expr = func.coalesce(DocumentAnalysis.invoice_date, Document.created_at)
        
        # Check database dialect to use appropriate format function
        bind = db.session.get_bind()
        if bind.dialect.name == 'sqlite':
            month_expr = func.strftime('%Y-%m', date_expr)
        else:
            month_expr = func.date_format(date_expr, '%Y-%m')
        
        query = db.session.query(
            month_expr.label('month'),
            func.sum(DocumentAnalysis.total_amount).label('total')
        ).join(Document, DocumentAnalysis.document_id == Document.id)\
         .filter(Document.user_id == user_id)

        if start_date:
            # We filter by created_at for the general range to keep it simple and consistent
            query = query.filter(Document.created_at >= start_date)
        if end_date:
            query = query.filter(Document.created_at <= end_date)

        query = query.group_by('month').order_by('month')
        
        return [{'month': row.month, 'total': float(row.total or 0.0)} for row in query.all()]

    def get_recent_documents(self, user_id: int, limit: int = 5):
        """Get recent documents with their analysis."""
        query = db.session.query(
            Document, DocumentAnalysis
        ).outerjoin(DocumentAnalysis, Document.id == DocumentAnalysis.document_id)\
         .filter(Document.user_id == user_id)\
         .order_by(desc(Document.created_at))\
         .limit(limit)
         
        results = []
        for doc, analysis in query.all():
            results.append({
                'id': doc.id,
                'filename': doc.original_filename,
                'status': doc.status,
                'created_at': doc.created_at.strftime('%Y-%m-%d'),
                'vendor': analysis.vendor_name if analysis else None,
                'invoice_number': analysis.invoice_number if analysis else None,
                'invoice_date': analysis.invoice_date.strftime('%Y-%m-%d') if analysis and analysis.invoice_date else None,
                'total_amount': float(analysis.total_amount) if analysis else None,
                'category': analysis.category if analysis else None
            })
        return results
