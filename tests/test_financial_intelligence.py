import pytest
from datetime import datetime, date
from app.extensions import db
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.services.financial_intelligence_service import FinancialIntelligenceService


def test_financial_overview_empty(app, user_a):
    """Test financial intelligence overview handles empty state gracefully."""
    with app.app_context():
        service = FinancialIntelligenceService()
        overview = service.get_financial_overview(user_a.id)

        assert overview["total_spending"] == 0.0
        assert overview["total_documents"] == 0
        assert overview["analyzed_documents"] == 0
        assert overview["average_transaction"] == 0.0
        assert overview["highest_transaction"]["amount"] == 0.0
        assert overview["review_needed_count"] == 0


def test_financial_overview_with_data(app, user_a):
    """Test financial intelligence overview calculations with real document analyses."""
    with app.app_context():
        doc1 = Document(
            user_id=user_a.id,
            original_filename="inv1.pdf",
            filename="inv1.pdf",
            file_path="/fake/inv1.pdf",
            file_type="application/pdf",
            file_size=1000,
            status="processed",
            created_at=datetime(2026, 1, 15)
        )
        doc2 = Document(
            user_id=user_a.id,
            original_filename="inv2.pdf",
            filename="inv2.pdf",
            file_path="/fake/inv2.pdf",
            file_type="application/pdf",
            file_size=1200,
            status="processed",
            created_at=datetime(2026, 2, 10)
        )
        doc_pending = Document(
            user_id=user_a.id,
            original_filename="inv_pending.pdf",
            filename="inv_pending.pdf",
            file_path="/fake/inv_pending.pdf",
            file_type="application/pdf",
            file_size=800,
            status="pending",
            created_at=datetime(2026, 2, 12)
        )
        db.session.add_all([doc1, doc2, doc_pending])
        db.session.commit()

        analysis1 = DocumentAnalysis(
            document_id=doc1.id,
            vendor_name="Acme Supplies",
            invoice_number="INV-001",
            invoice_date=date(2026, 1, 15),
            subtotal_amount=1000.0,
            tax_amount=180.0,
            total_amount=1180.0,
            category="Office Supplies",
            payment_method="Card",
            confidence_score=0.92
        )
        analysis2 = DocumentAnalysis(
            document_id=doc2.id,
            vendor_name="Tech Solutions",
            invoice_number="INV-002",
            invoice_date=date(2026, 2, 10),
            subtotal_amount=4000.0,
            tax_amount=720.0,
            total_amount=4720.0,
            category="Software",
            payment_method="Wire Transfer",
            confidence_score=0.88
        )
        db.session.add_all([analysis1, analysis2])
        db.session.commit()

        service = FinancialIntelligenceService()
        overview = service.get_financial_overview(user_a.id)

        assert overview["total_documents"] == 3
        assert overview["analyzed_documents"] == 2
        assert overview["pending_documents"] == 1
        assert overview["total_spending"] == 5900.0
        assert overview["total_tax"] == 900.0
        assert overview["total_subtotal"] == 5000.0
        assert overview["average_transaction"] == 2950.0
        assert overview["highest_transaction"]["amount"] == 4720.0
        assert overview["highest_transaction"]["vendor"] == "Tech Solutions"
        assert overview["lowest_transaction"] == 1180.0
        assert overview["invoices_count"] == 2
        assert overview["effective_tax_rate"] == 18.0


def test_category_and_vendor_breakdown(app, user_a):
    """Test spending aggregation by category and vendor."""
    with app.app_context():
        doc1 = Document(
            user_id=user_a.id,
            original_filename="cloud.pdf",
            filename="cloud.pdf",
            file_path="/fake/cloud.pdf",
            file_type="application/pdf",
            file_size=500,
            status="processed"
        )
        doc2 = Document(
            user_id=user_a.id,
            original_filename="flight.pdf",
            filename="flight.pdf",
            file_path="/fake/flight.pdf",
            file_type="application/pdf",
            file_size=600,
            status="processed"
        )
        db.session.add_all([doc1, doc2])
        db.session.commit()

        a1 = DocumentAnalysis(
            document_id=doc1.id,
            vendor_name="AWS Cloud",
            total_amount=3000.0,
            category="Infrastructure",
            confidence_score=0.9
        )
        a2 = DocumentAnalysis(
            document_id=doc2.id,
            vendor_name="Air India",
            total_amount=7000.0,
            category="Travel",
            confidence_score=0.95
        )
        db.session.add_all([a1, a2])
        db.session.commit()

        service = FinancialIntelligenceService()
        categories = service.get_spending_by_category(user_a.id)
        vendors = service.get_spending_by_vendor(user_a.id)

        assert len(categories) == 2
        # Travel should be top category (7000 > 3000)
        assert categories[0]["category"] == "Travel"
        assert categories[0]["total"] == 7000.0
        assert categories[0]["percentage"] == 70.0

        assert len(vendors) == 2
        assert vendors[0]["vendor"] == "Air India"
        assert vendors[0]["total"] == 7000.0
        assert vendors[0]["percentage"] == 70.0


def test_spending_concentration_and_observations(app, user_a):
    """Test concentration calculation and observation generation."""
    with app.app_context():
        doc = Document(
            user_id=user_a.id,
            original_filename="invoice.pdf",
            filename="invoice.pdf",
            file_path="/fake/invoice.pdf",
            file_type="application/pdf",
            file_size=500,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()

        a = DocumentAnalysis(
            document_id=doc.id,
            vendor_name="Dominant Corp",
            total_amount=50000.0,
            subtotal_amount=45000.0,
            tax_amount=5000.0,
            category="Consulting",
            confidence_score=0.9
        )
        db.session.add(a)
        db.session.commit()

        service = FinancialIntelligenceService()
        concentration = service.get_spending_concentration(user_a.id)
        observations = service.get_financial_observations(user_a.id)

        assert concentration["top_1_pct"] == 100.0
        assert concentration["concentration_level"] in ["High", "Severe"]

        assert len(observations) > 0
        obs_titles = [o["title"] for o in observations]
        assert any("Primary Expenditure Category" in t for t in obs_titles)


def test_financial_intelligence_route(client, app, user_a):
    """Test accessing /financial-intelligence route."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    resp = client.get('/financial-intelligence')
    assert resp.status_code == 200
    assert b"Financial Intelligence" in resp.data

