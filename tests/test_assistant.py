"""Unit and Integration Tests for Sprint 9 Phase 1 Evidence-Based AI Financial Assistant."""

import pytest
from app.extensions import db
from app.models.user import User
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.chat_history import ChatHistory
from app.services.intent_detection_service import IntentDetectionService
from app.services import (
    intent_detection_service,
    evidence_retrieval_service,
    answer_generation_service,
    financial_assistant_service
)


def test_intent_detection_classification():
    """Test IntentDetectionService correctly classifies questions and extracts entities."""
    service = IntentDetectionService()

    # 1. Total Spending
    res = service.detect_intent("How much did I spend in total?")
    assert res["intent"] == "TOTAL_SPENDING"
    assert res["confidence"] >= 0.80

    # 2. Category Spending
    res = service.detect_intent("How much did I spend on travel?")
    assert res["intent"] == "CATEGORY_SPENDING"
    assert res["entities"]["category"] == "Travel"

    res = service.detect_intent("Show my food and dining expenses")
    assert res["intent"] == "CATEGORY_SPENDING"
    assert res["entities"]["category"] == "Food & Dining"

    # 3. Top Vendor
    res = service.detect_intent("Which vendor received the most money?")
    assert res["intent"] == "TOP_VENDOR"

    # 4. Top Vendors
    res = service.detect_intent("List my top vendors by spending")
    assert res["intent"] == "TOP_VENDORS"

    # 5. Anomalies
    res = service.detect_intent("Show my unusual transactions")
    assert res["intent"] == "ANOMALIES"

    # 6. Duplicates
    res = service.detect_intent("Do I have any duplicate invoices?")
    assert res["intent"] == "DUPLICATE_DOCUMENTS"

    # 7. Document Risk
    res = service.detect_intent("Why was invoice INV-1044 flagged?")
    assert res["intent"] == "DOCUMENT_RISK"
    assert res["entities"]["document_reference"] == "INV-1044"

    # 8. Document Lookup
    res = service.detect_intent("Lookup invoice INV-990")
    assert res["intent"] == "DOCUMENT_LOOKUP"
    assert res["entities"]["document_reference"] == "INV-990"

    # 9. Month Comparison
    res = service.detect_intent("Compare this month with last month")
    assert res["intent"] == "MONTH_COMPARISON"

    # 10. Due Diligence
    res = service.detect_intent("How healthy are my finances?")
    assert res["intent"] == "DUE_DILIGENCE"

    # 11. Tax Summary
    res = service.detect_intent("What is my tax total?")
    assert res["intent"] == "TAX_SUMMARY"

    # 12. Payment Method
    res = service.detect_intent("Show payment method distribution")
    assert res["intent"] == "PAYMENT_METHOD_SUMMARY"

    # 13. General Summary
    res = service.detect_intent("Give me an executive financial summary")
    assert res["intent"] == "GENERAL_FINANCIAL_SUMMARY"

    # 14. Unknown Question
    res = service.detect_intent("What is the capital of France?")
    assert res["intent"] == "UNKNOWN"


def test_evidence_retrieval_and_hallucination_prevention(app, user_a):
    """Test EvidenceRetrievalService returns accurate facts and handles missing data gracefully."""
    with app.app_context():
        # Empty workspace check (no documents)
        ev = evidence_retrieval_service.get_evidence(user_a.id, "TOTAL_SPENDING", {})
        assert ev["status"] == "insufficient_data"
        assert ev["facts"]["analyzed_documents"] == 0

        ans = answer_generation_service.generate_answer(ev)
        assert "enough analyzed financial data" in ans
        assert "68,400" not in ans  # Ensure no fabricated hallucinated amounts!

        # Populate workspace with real analyzed document for User A
        doc = Document(
            user_id=user_a.id,
            original_filename="cloud_services_invoice.pdf",
            filename="cloud_services_invoice.pdf",
            file_path="/fake/cloud.pdf",
            file_type="application/pdf",
            file_size=2048,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()

        analysis = DocumentAnalysis(
            document_id=doc.id,
            vendor_name="AWS Cloud",
            invoice_number="AWS-8871",
            total_amount=15000.0,
            subtotal_amount=13500.0,
            tax_amount=1500.0,
            category="Software & Subscriptions",
            confidence_score=0.98
        )
        db.session.add(analysis)
        db.session.commit()

        # Check total spending evidence
        ev_total = evidence_retrieval_service.get_evidence(user_a.id, "TOTAL_SPENDING", {})
        assert ev_total["status"] == "success"
        assert ev_total["facts"]["total_spending"] == 15000.0
        assert len(ev_total["sources"]) == 1
        assert ev_total["sources"][0]["vendor_name"] == "AWS Cloud"

        # Check category spending evidence
        ev_cat = evidence_retrieval_service.get_evidence(user_a.id, "CATEGORY_SPENDING", {"category": "Software & Subscriptions"})
        assert ev_cat["status"] == "success"
        assert ev_cat["facts"]["total_amount"] == 15000.0

        # Check top vendor evidence
        ev_vendor = evidence_retrieval_service.get_evidence(user_a.id, "TOP_VENDOR", {})
        assert ev_vendor["status"] == "success"
        assert ev_vendor["facts"]["vendor_name"] == "AWS Cloud"

        # Check tax summary evidence
        ev_tax = evidence_retrieval_service.get_evidence(user_a.id, "TAX_SUMMARY", {})
        assert ev_tax["status"] == "success"
        assert ev_tax["facts"]["total_tax"] == 1500.0


def test_user_a_vs_user_b_assistant_isolation(client, app, user_a, user_b):
    """Test strict user isolation in AI assistant backend and chat history."""
    with app.app_context():
        # User A document
        doc_a = Document(
            user_id=user_a.id,
            original_filename="secret_deal_usera.pdf",
            filename="secret_deal_usera.pdf",
            file_path="/fake/path_a.pdf",
            file_type="application/pdf",
            file_size=1024,
            status="processed"
        )
        db.session.add(doc_a)
        db.session.commit()

        analysis_a = DocumentAnalysis(
            document_id=doc_a.id,
            vendor_name="UserA Only Supplier",
            invoice_number="SECRET-A-99",
            total_amount=50000.0,
            confidence_score=0.90
        )
        db.session.add(analysis_a)
        db.session.commit()

        # Direct service query isolation: User B asking for User A's document risk
        ev_b = evidence_retrieval_service.get_evidence(user_b.id, "DOCUMENT_RISK", {"document_reference": "SECRET-A-99"})
        assert ev_b["status"] == "not_found"
        assert len(ev_b["sources"]) == 0

        ans_b = answer_generation_service.generate_answer(ev_b)
        assert "No matching document was found" in ans_b
        assert "UserA Only Supplier" not in ans_b
        assert "50,000" not in ans_b

    # Web API test for User B asking about User A's document
    client.post('/auth/login', data={'email': 'userb@example.com', 'password': 'password123'})
    
    resp = client.post('/api/assistant/ask', json={"question": "Why was invoice SECRET-A-99 flagged?"})
    assert resp.status_code == 404
    json_data = resp.get_json()
    assert json_data["status"] == "not_found"
    assert "UserA Only Supplier" not in json_data["answer"]

    # Web API test for User B checking chat history
    resp_hist = client.get('/api/assistant/history')
    assert resp_hist.status_code == 200
    hist_b = resp_hist.get_json()["history"]
    # Ensure User B does NOT see User A's historical messages
    assert all("UserA" not in h["message"] for h in hist_b)


def test_assistant_api_validation_and_history(client, app, user_a):
    """Test API route input validation, error handling, and history recording."""
    # Login as User A
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    # 1. Empty question
    res_empty = client.post('/api/assistant/ask', json={"question": ""})
    assert res_empty.status_code == 400
    assert res_empty.get_json()["status"] == "error"

    # 2. Oversized question (> 500 chars)
    res_long = client.post('/api/assistant/ask', json={"question": "a" * 501})
    assert res_long.status_code == 400
    assert "too long" in res_long.get_json()["answer"]

    # 3. Valid question
    res_valid = client.post('/api/assistant/ask', json={"question": "How much did I spend in total?"})
    assert res_valid.status_code == 200
    res_json = res_valid.get_json()
    assert res_json["intent"] == "TOTAL_SPENDING"
    assert "answer" in res_json

    # 4. Check that history was saved in DB for User A
    res_hist = client.get('/api/assistant/history')
    assert res_hist.status_code == 200
    history = res_hist.get_json()["history"]
    assert len(history) >= 2  # 1 user message + 1 assistant message
    assert history[0]["role"] == "user"
    assert history[0]["message"] == "How much did I spend in total?"
    assert history[1]["role"] == "assistant"


def test_assistant_page_access_and_rendering(client, app, user_a):
    """Test authenticated and unauthenticated access to /assistant route."""
    # 1. Unauthenticated request should redirect to login
    resp_unauth = client.get('/assistant')
    assert resp_unauth.status_code == 302
    assert '/auth/login' in resp_unauth.headers['Location']

    # 2. Authenticated request should render page cleanly
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    resp_auth = client.get('/assistant')
    assert resp_auth.status_code == 200
    assert b'Financial Copilot' in resp_auth.data
    assert b'assistant.js' in resp_auth.data
    assert b'assistant-container' in resp_auth.data

