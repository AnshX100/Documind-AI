import pytest
from datetime import datetime, date
from app.extensions import db
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.services.due_diligence_service import DueDiligenceService


def test_due_diligence_empty(app, user_a):
    """Test due diligence report with zero documents."""
    with app.app_context():
        service = DueDiligenceService()
        report = service.get_due_diligence_report(user_a.id)

        assert report["total_docs"] == 0
        assert report["overall_score"] == 100
        assert report["risk_profile"] == "Low risk profile"
        assert report["anomalies_count"] == 0


def test_due_diligence_healthy_workspace(app, user_a):
    """Test due diligence on a healthy, diversified workspace."""
    with app.app_context():
        # 3 documents, 3 different vendors, proper math, no duplicates
        docs = []
        for i in range(3):
            d = Document(
                user_id=user_a.id,
                original_filename=f"healthy_{i}.pdf",
                filename=f"healthy_{i}.pdf",
                file_path=f"/fake/healthy_{i}.pdf",
                file_type="application/pdf",
                file_size=500,
                status="processed"
            )
            docs.append(d)
        db.session.add_all(docs)
        db.session.commit()

        for i in range(3):
            a = DocumentAnalysis(
                document_id=docs[i].id,
                vendor_name=f"Vendor {i}",
                invoice_number=f"INV-{100 + i}",
                invoice_date=date(2026, 1, 10 + i),
                subtotal_amount=1000.0,
                tax_amount=100.0,
                total_amount=1100.0,
                confidence_score=0.95
            )
            db.session.add(a)
        db.session.commit()

        service = DueDiligenceService()
        report = service.get_due_diligence_report(user_a.id)

        assert report["total_docs"] == 3
        assert report["analyzed_docs"] == 3
        assert report["completeness_score"] >= 90
        assert report["consistency_score"] >= 90
        assert report["overall_score"] >= 85
        assert report["risk_profile"] == "Low risk profile"
        assert report["anomalies_count"] == 0


def test_due_diligence_with_risk_factors(app, user_a):
    """Test due diligence detects concentration and consistency penalties."""
    with app.app_context():
        # 1 failed doc, 1 doc with arithmetic error, high concentration on Vendor X
        doc1 = Document(user_id=user_a.id, original_filename="good.pdf", filename="good.pdf", file_path="/fake/good.pdf", file_type="application/pdf", file_size=500, status="processed")
        doc2 = Document(user_id=user_a.id, original_filename="failed.pdf", filename="failed.pdf", file_path="/fake/failed.pdf", file_type="application/pdf", file_size=500, status="failed")
        db.session.add_all([doc1, doc2])
        db.session.commit()

        # Arithmetic error: 1000 + 100 != 5000
        a1 = DocumentAnalysis(
            document_id=doc1.id,
            vendor_name="Monopoly Supplier",
            invoice_number="INV-001",
            invoice_date=date(2026, 1, 10),
            subtotal_amount=1000.0,
            tax_amount=100.0,
            total_amount=5000.0,
            confidence_score=0.9
        )
        db.session.add(a1)
        db.session.commit()

        service = DueDiligenceService()
        report = service.get_due_diligence_report(user_a.id)

        assert report["total_docs"] == 2
        assert report["analyzed_docs"] == 1
        assert report["anomalies_count"] >= 1
        assert report["concentration_rating"] in ["High", "Severe"]
        assert len(report["action_items"]) > 0


def test_diligence_route(client, app, user_a):
    """Test accessing /diligence route."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    resp = client.get('/diligence')
    assert resp.status_code == 200
    assert b"Financial Due Diligence" in resp.data or b"Financial due diligence" in resp.data

