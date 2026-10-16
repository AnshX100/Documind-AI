import pytest
from datetime import datetime, date
from app.extensions import db
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.services.anomaly_detection_service import AnomalyDetectionService


def test_duplicate_invoice_detection(app, user_a):
    """Test detection of duplicate invoice numbers from the same vendor."""
    with app.app_context():
        doc1 = Document(
            user_id=user_a.id,
            original_filename="inv_jan.pdf",
            filename="inv_jan.pdf",
            file_path="/fake/inv_jan.pdf",
            file_type="application/pdf",
            file_size=500,
            status="processed"
        )
        doc2 = Document(
            user_id=user_a.id,
            original_filename="inv_jan_copy.pdf",
            filename="inv_jan_copy.pdf",
            file_path="/fake/inv_jan_copy.pdf",
            file_type="application/pdf",
            file_size=500,
            status="processed"
        )
        db.session.add_all([doc1, doc2])
        db.session.commit()

        a1 = DocumentAnalysis(
            document_id=doc1.id,
            vendor_name="ABC Technologies",
            invoice_number="INV-2045",
            invoice_date=date(2026, 1, 10),
            total_amount=48500.0,
            confidence_score=0.95
        )
        a2 = DocumentAnalysis(
            document_id=doc2.id,
            vendor_name="ABC Technologies",
            invoice_number="INV-2045",
            invoice_date=date(2026, 1, 10),
            total_amount=48500.0,
            confidence_score=0.95
        )
        db.session.add_all([a1, a2])
        db.session.commit()

        service = AnomalyDetectionService()
        anomalies = service.get_user_anomalies(user_a.id)

        assert len(anomalies) >= 1
        dup_anom = next((a for a in anomalies if a["anomaly_type"] == "duplicate_invoice"), None)
        assert dup_anom is not None
        assert dup_anom["severity"] in ["HIGH", "CRITICAL"]
        assert "INV-2045" in dup_anom["title"]
        assert "ABC Technologies" in dup_anom["description"]


def test_weak_duplicate_transaction_detection(app, user_a):
    """Test detection of duplicate transaction when invoice numbers are missing but vendor, date, and amount match."""
    with app.app_context():
        doc1 = Document(
            user_id=user_a.id,
            original_filename="receipt1.pdf",
            filename="receipt1.pdf",
            file_path="/fake/receipt1.pdf",
            file_type="application/pdf",
            file_size=500,
            status="processed"
        )
        doc2 = Document(
            user_id=user_a.id,
            original_filename="receipt2.pdf",
            filename="receipt2.pdf",
            file_path="/fake/receipt2.pdf",
            file_type="application/pdf",
            file_size=500,
            status="processed"
        )
        db.session.add_all([doc1, doc2])
        db.session.commit()

        a1 = DocumentAnalysis(
            document_id=doc1.id,
            vendor_name="Office Supplies Depot",
            invoice_number=None,
            invoice_date=date(2026, 3, 5),
            total_amount=1500.0,
            confidence_score=0.9
        )
        a2 = DocumentAnalysis(
            document_id=doc2.id,
            vendor_name="Office Supplies Depot",
            invoice_number=None,
            invoice_date=date(2026, 3, 5),
            total_amount=1500.0,
            confidence_score=0.9
        )
        db.session.add_all([a1, a2])
        db.session.commit()

        service = AnomalyDetectionService()
        anomalies = service.get_document_anomalies(doc1.id, user_a.id)

        dup = next((a for a in anomalies if a["anomaly_type"] == "duplicate_invoice"), None)
        assert dup is not None
        assert dup["severity"] == "MEDIUM"


def test_unusual_transaction_amount_detection(app, user_a):
    """Test statistical outlier detection for unusually high transaction amounts."""
    with app.app_context():
        # Create historical baseline: ₹5,000, ₹7,000, ₹8,500, ₹9,000 (avg = 7,375)
        docs = []
        amounts = [5000.0, 7000.0, 8500.0, 9000.0]
        for i, amt in enumerate(amounts):
            d = Document(
                user_id=user_a.id,
                original_filename=f"doc_{i}.pdf",
                filename=f"doc_{i}.pdf",
                file_path=f"/fake/doc_{i}.pdf",
                file_type="application/pdf",
                file_size=500,
                status="processed"
            )
            docs.append(d)
        
        # New outlier transaction: ₹95,000 (> 10x average)
        outlier_doc = Document(
            user_id=user_a.id,
            original_filename="large_purchase.pdf",
            filename="large_purchase.pdf",
            file_path="/fake/large_purchase.pdf",
            file_type="application/pdf",
            file_size=500,
            status="processed"
        )
        docs.append(outlier_doc)
        db.session.add_all(docs)
        db.session.commit()

        for i, amt in enumerate(amounts):
            a = DocumentAnalysis(
                document_id=docs[i].id,
                vendor_name=f"Vendor {i}",
                invoice_number=f"INV-{i}",
                invoice_date=date(2026, 1, 10 + i),
                total_amount=amt,
                confidence_score=0.9
            )
            db.session.add(a)

        outlier_analysis = DocumentAnalysis(
            document_id=outlier_doc.id,
            vendor_name="Major Machinery Co",
            invoice_number="INV-999",
            invoice_date=date(2026, 2, 1),
            total_amount=95000.0,
            confidence_score=0.95
        )
        db.session.add(outlier_analysis)
        db.session.commit()

        service = AnomalyDetectionService()
        doc_anomalies = service.get_document_anomalies(outlier_doc.id, user_a.id)

        unusual = next((a for a in doc_anomalies if a["anomaly_type"] == "unusual_amount"), None)
        assert unusual is not None
        assert unusual["severity"] in ["HIGH", "CRITICAL"]
        assert "95,000" in unusual["title"] or "95,000" in unusual["detected_value"]


def test_arithmetic_inconsistency_detection(app, user_a):
    """Test detection of arithmetic mismatch between subtotal + tax and total amount."""
    with app.app_context():
        doc = Document(
            user_id=user_a.id,
            original_filename="bad_math.pdf",
            filename="bad_math.pdf",
            file_path="/fake/bad_math.pdf",
            file_type="application/pdf",
            file_size=500,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()

        # Subtotal: 1000, Tax: 180 => Expected: 1180. Declared Total: 2500 (Discrepancy 1320)
        analysis = DocumentAnalysis(
            document_id=doc.id,
            vendor_name="Corner Retail",
            invoice_number="INV-777",
            invoice_date=date(2026, 1, 15),
            subtotal_amount=1000.0,
            tax_amount=180.0,
            total_amount=2500.0,
            confidence_score=0.9
        )
        db.session.add(analysis)
        db.session.commit()

        service = AnomalyDetectionService()
        anomalies = service.get_document_anomalies(doc.id, user_a.id)

        arith = next((a for a in anomalies if a["anomaly_type"] == "arithmetic_inconsistency"), None)
        assert arith is not None
        assert arith["severity"] in ["HIGH", "MEDIUM"]
        assert "1,320" in arith["reason"] or "1,180" in arith["expected_value"]


def test_vendor_spending_spike_detection(app, user_a):
    """Test detection of vendor spending spike compared to historical average with that vendor."""
    with app.app_context():
        # 2 prior transactions with Cloud Host: ₹2,000 each (avg: ₹2,000)
        doc1 = Document(user_id=user_a.id, original_filename="h1.pdf", filename="h1.pdf", file_path="/fake/h1.pdf", file_type="application/pdf", file_size=500, status="processed")
        doc2 = Document(user_id=user_a.id, original_filename="h2.pdf", filename="h2.pdf", file_path="/fake/h2.pdf", file_type="application/pdf", file_size=500, status="processed")
        doc_spike = Document(user_id=user_a.id, original_filename="spike.pdf", filename="spike.pdf", file_path="/fake/spike.pdf", file_type="application/pdf", file_size=500, status="processed")
        db.session.add_all([doc1, doc2, doc_spike])
        db.session.commit()

        a1 = DocumentAnalysis(document_id=doc1.id, vendor_name="Cloud Host", total_amount=2000.0, confidence_score=0.9)
        a2 = DocumentAnalysis(document_id=doc2.id, vendor_name="Cloud Host", total_amount=2000.0, confidence_score=0.9)
        # Spike: ₹25,000 (12.5x normal, diff = ₹23,000)
        a_spike = DocumentAnalysis(document_id=doc_spike.id, vendor_name="Cloud Host", total_amount=25000.0, confidence_score=0.9)
        db.session.add_all([a1, a2, a_spike])
        db.session.commit()

        service = AnomalyDetectionService()
        doc_anomalies = service.get_document_anomalies(doc_spike.id, user_a.id)

        spike = next((a for a in doc_anomalies if a["anomaly_type"] == "spending_spike"), None)
        assert spike is not None
        assert "Cloud Host" in spike["title"]
        assert spike["severity"] in ["HIGH", "MEDIUM"]


def test_missing_data_detection(app, user_a):
    """Test detection of missing core fields."""
    with app.app_context():
        doc = Document(
            user_id=user_a.id,
            original_filename="missing.pdf",
            filename="missing.pdf",
            file_path="/fake/missing.pdf",
            file_type="application/pdf",
            file_size=500,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()

        # Missing vendor and missing total
        analysis = DocumentAnalysis(
            document_id=doc.id,
            vendor_name=None,
            invoice_number=None,
            invoice_date=None,
            total_amount=0.0,
            confidence_score=0.4
        )
        db.session.add(analysis)
        db.session.commit()

        service = AnomalyDetectionService()
        anomalies = service.get_document_anomalies(doc.id, user_a.id)

        missing = next((a for a in anomalies if a["anomaly_type"] == "missing_data"), None)
        assert missing is not None
        assert missing["severity"] == "HIGH"

