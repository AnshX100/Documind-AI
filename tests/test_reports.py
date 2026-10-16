"""Unit and Integration Tests for Sprint 10 Professional Financial Reports."""

import os
import pytest
from datetime import datetime, date, timedelta, timezone
from pypdf import PdfReader

from app.extensions import db
from app.models.user import User
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.report import Report
from app.services import report_service, report_data_service, report_pdf_service


def test_create_executive_report(app, user_a):
    """Test creating an Executive Financial Summary report."""
    with app.app_context():
        # Setup analyzed document for User A
        doc = Document(
            user_id=user_a.id,
            original_filename="cloud_bill.pdf",
            filename="cloud_bill.pdf",
            file_path="/fake/cloud.pdf",
            file_type="application/pdf",
            file_size=1024,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()

        analysis = DocumentAnalysis(
            document_id=doc.id,
            vendor_name="AWS Infrastructure",
            invoice_number="AWS-9912",
            total_amount=18500.0,
            category="Software & Subscriptions",
            confidence_score=0.98
        )
        db.session.add(analysis)
        db.session.commit()

        res = report_service.generate_report(
            user_id=user_a.id,
            report_type="EXECUTIVE",
            period="all_time",
            report_title="Executive Q3 Financial Report"
        )

        assert res["status"] == "success"
        report_id = res["report_id"]

        report = Report.query.get(report_id)
        assert report is not None
        assert report.report_name == "Executive Q3 Financial Report"
        assert report.report_type == "EXECUTIVE"
        assert report.status == "completed"
        assert float(report.total_expenses) == 18500.0
        assert report.total_documents == 1
        assert report.file_path is not None
        assert report.file_path.endswith(".pdf")

        # Verify disk file exists
        reports_dir, safe_filename = report_service.get_report_download_path(report_id, user_a.id)
        assert reports_dir is not None
        assert safe_filename is not None
        assert os.path.exists(os.path.join(reports_dir, safe_filename))


def test_create_spending_and_anomaly_reports(app, user_a):
    """Test generating Spending Analysis, Anomaly, and Due Diligence report types."""
    with app.app_context():
        doc = Document(
            user_id=user_a.id,
            original_filename="flight_ticket.pdf",
            filename="flight_ticket.pdf",
            file_path="/fake/flight.pdf",
            file_type="application/pdf",
            file_size=1024,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()

        analysis = DocumentAnalysis(
            document_id=doc.id,
            vendor_name="Indigo Airlines",
            total_amount=12500.0,
            category="Travel",
            confidence_score=0.95
        )
        db.session.add(analysis)
        db.session.commit()

        # Spending Report
        res_spend = report_service.generate_report(user_a.id, "SPENDING", "all_time")
        assert res_spend["status"] == "success"

        # Anomaly Report
        res_anom = report_service.generate_report(user_a.id, "ANOMALY", "all_time")
        assert res_anom["status"] == "success"

        # Due Diligence Report
        res_dd = report_service.generate_report(user_a.id, "DUE_DILIGENCE", "all_time")
        assert res_dd["status"] == "success"

        # Comprehensive Report
        res_comp = report_service.generate_report(user_a.id, "COMPREHENSIVE", "all_time")
        assert res_comp["status"] == "success"


def test_report_period_filtering(app, user_a):
    """Test report respects period date range bounds."""
    with app.app_context():
        # Current month document
        doc_now = Document(
            user_id=user_a.id,
            original_filename="current_month_doc.pdf",
            filename="current_month_doc.pdf",
            file_path="/fake/now.pdf",
            file_type="application/pdf",
            file_size=1024,
            status="processed",
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(doc_now)
        db.session.commit()

        analysis_now = DocumentAnalysis(
            document_id=doc_now.id,
            vendor_name="Recent Vendor",
            total_amount=5000.0,
            invoice_date=date.today(),
            category="Office Supplies",
            confidence_score=0.95
        )
        db.session.add(analysis_now)
        db.session.commit()

        res = report_service.generate_report(
            user_id=user_a.id,
            report_type="EXECUTIVE",
            period="current_month"
        )

        assert res["status"] == "success"
        report = Report.query.get(res["report_id"])
        assert float(report.total_expenses) >= 5000.0


def test_pdf_content_text_verification(app, user_a):
    """Constraint 6 Test: Verify PDF text extraction contains expected titles, vendor names, and values."""
    with app.app_context():
        doc = Document(
            user_id=user_a.id,
            original_filename="cloud_compute.pdf",
            filename="cloud_compute.pdf",
            file_path="/fake/cc.pdf",
            file_type="application/pdf",
            file_size=1024,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()

        analysis = DocumentAnalysis(
            document_id=doc.id,
            vendor_name="Cloud Compute Systems",
            invoice_number="CC-7711",
            total_amount=35000.0,
            category="Software & Subscriptions",
            confidence_score=0.99
        )
        db.session.add(analysis)
        db.session.commit()

        res = report_service.generate_report(
            user_id=user_a.id,
            report_type="EXECUTIVE",
            period="all_time",
            report_title="Verified Content Test Report"
        )
        assert res["status"] == "success"
        report_id = res["report_id"]

        reports_dir, safe_filename = report_service.get_report_download_path(report_id, user_a.id)
        pdf_path = os.path.join(reports_dir, safe_filename)

        # Extract text using pypdf PdfReader
        reader = PdfReader(pdf_path)
        assert len(reader.pages) >= 1

        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() or ""

        # Verify critical text content exists inside PDF stream
        assert "Verified Content Test Report" in full_text
        assert "DocuMind AI" in full_text
        assert "Cloud Compute Systems" in full_text
        assert "35,000.00" in full_text or "35000" in full_text


def test_user_isolation_for_reports(client, app, user_a, user_b):
    """Constraint 8 Test: Verify User B cannot view, download, or delete User A's reports."""
    with app.app_context():
        res = report_service.generate_report(
            user_id=user_a.id,
            report_type="EXECUTIVE",
            period="all_time",
            report_title="User A Secret Report"
        )
        report_id = res["report_id"]

    # Login as User B
    client.post('/auth/login', data={'email': 'userb@example.com', 'password': 'password123'})

    # 1. Attempt GET /reports/<A_ID>
    resp_view = client.get(f'/reports/{report_id}')
    assert resp_view.status_code in [302, 404]

    # 2. Attempt GET /reports/<A_ID>/download
    resp_dl = client.get(f'/reports/{report_id}/download')
    assert resp_dl.status_code in [302, 404]

    # 3. Attempt POST /reports/<A_ID>/delete
    resp_del = client.post(f'/reports/{report_id}/delete')
    assert resp_del.status_code in [302, 404]

    # Direct service security check
    assert report_service.get_user_report(report_id, user_b.id) is None
    reports_dir, filename = report_service.get_report_download_path(report_id, user_b.id)
    assert reports_dir is None
    assert filename is None
    assert report_service.delete_report(report_id, user_b.id) is False


def test_path_traversal_prevention(app, user_a):
    """Constraint 3 Test: Verify path traversal tricks in file_path are neutralized."""
    with app.app_context():
        report = Report(
            user_id=user_a.id,
            report_name="Traversing Report",
            report_type="EXECUTIVE",
            status="completed",
            file_path="../../etc/passwd"
        )
        db.session.add(report)
        db.session.commit()

        # Download path helper should use os.path.basename and fail if file doesn't exist
        reports_dir, safe_filename = report_service.get_report_download_path(report.id, user_a.id)
        assert safe_filename == "passwd" or reports_dir is None


def test_report_empty_workspace(app, user_a):
    """Test generating report when workspace has zero documents."""
    with app.app_context():
        # Ensure no documents for User A
        res = report_service.generate_report(
            user_id=user_a.id,
            report_type="EXECUTIVE",
            period="all_time",
            report_title="Empty Workspace Report"
        )

        assert res["status"] == "success"
        report = Report.query.get(res["report_id"])
        assert report.status == "completed"
        assert float(report.total_expenses) == 0.0
        assert report.total_documents == 0

        # Verify PDF compiles cleanly
        reports_dir, safe_filename = report_service.get_report_download_path(report.id, user_a.id)
        assert os.path.exists(os.path.join(reports_dir, safe_filename))


def test_report_deletion_cleans_file(app, user_a):
    """Test report deletion removes DB record and disk PDF file."""
    with app.app_context():
        res = report_service.generate_report(
            user_id=user_a.id,
            report_type="SPENDING",
            period="all_time",
            report_title="Report to Delete"
        )
        report_id = res["report_id"]

        reports_dir, safe_filename = report_service.get_report_download_path(report_id, user_a.id)
        file_disk_path = os.path.join(reports_dir, safe_filename)
        assert os.path.exists(file_disk_path)

        success = report_service.delete_report(report_id, user_a.id)
        assert success is True

        assert Report.query.get(report_id) is None
        assert not os.path.exists(file_disk_path)
