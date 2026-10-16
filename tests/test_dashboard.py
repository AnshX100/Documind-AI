import pytest
from app.extensions import db
from app.models.user import User
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from datetime import datetime

def test_dashboard_api_data(client, app, user_a):
    """Test dashboard API returns correct metrics and structure."""
    # Login as User A
    login_resp = client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    assert login_resp.status_code in [200, 302]
    
    # Create some documents with analysis for User A
    with app.app_context():
        doc1 = Document(
            user_id=user_a.id,
            original_filename="inv1.pdf",
            filename="inv1.pdf",
            file_path="/fake/inv1.pdf",
            file_type="application/pdf",
            file_size=500,
            status="processed",
            created_at=datetime(2026, 1, 15)
        )
        doc2 = Document(
            user_id=user_a.id,
            original_filename="inv2.pdf",
            filename="inv2.pdf",
            file_path="/fake/inv2.pdf",
            file_type="application/pdf",
            file_size=600,
            status="processed",
            created_at=datetime(2026, 2, 20)
        )
        db.session.add_all([doc1, doc2])
        db.session.commit()
        
        analysis1 = DocumentAnalysis(
            document_id=doc1.id,
            vendor_name="Vendor A",
            invoice_number="INV-001",
            invoice_date=datetime(2026, 1, 15),
            subtotal_amount=100.0,
            tax_amount=10.0,
            total_amount=110.0,
            category="Software",
            payment_method="Card",
            confidence_score=0.95
        )
        analysis2 = DocumentAnalysis(
            document_id=doc2.id,
            vendor_name="Vendor B",
            invoice_number="INV-002",
            invoice_date=datetime(2026, 2, 20),
            subtotal_amount=200.0,
            tax_amount=20.0,
            total_amount=220.0,
            category="Travel",
            payment_method="Cheque",
            confidence_score=0.85
        )
        db.session.add_all([analysis1, analysis2])
        db.session.commit()

    # Call Dashboard API
    response = client.get('/dashboard/api/data?range=12m')
    assert response.status_code == 200
    
    data = response.get_json()
    assert "metrics" in data
    assert "category_breakdown" in data
    assert "vendor_breakdown" in data
    assert "monthly_trend" in data
    assert "recent_documents" in data
    
    metrics = data["metrics"]
    assert metrics["total_documents"] == 2
    assert metrics["total_expenses"] == 330.0
    assert metrics["total_tax"] == 30.0
    assert metrics["average_expense"] == 165.0
    
    # Check category breakdown
    categories = {item["category"]: item["total"] for item in data["category_breakdown"]}
    assert categories.get("Software") == 110.0
    assert categories.get("Travel") == 220.0
    
    # Check vendor breakdown
    vendors = {item["vendor"]: item["total"] for item in data["vendor_breakdown"]}
    assert vendors.get("Vendor A") == 110.0
    assert vendors.get("Vendor B") == 220.0
    
    # Check monthly trend
    trends = {item["month"]: item["total"] for item in data["monthly_trend"]}
    assert trends.get("2026-01") == 110.0
    assert trends.get("2026-02") == 220.0
