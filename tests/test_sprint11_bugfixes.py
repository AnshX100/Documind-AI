"""Regression tests for Sprint 11 Bug Fixes:
1. Document Delete Modal & Deletion Flow
2. Report Generation Argument Error & Flow
3. AI Assistant Conversation Management
"""

import os
from datetime import date, datetime, timezone
import pytest
from app.extensions import db
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.report import Report
from app.models.chat_history import ChatHistory
from app.services import report_service, financial_assistant_service


# =====================================================================
# BUG 1 REGRESSION TESTS: Document Delete Modal and Deletion Flow
# =====================================================================

def test_document_delete_modal_markup_and_action(client, app, user_a):
    """Verify delete modal markup is rendered cleanly with deleteForm, modal-dialog, and CSRF token."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    
    with app.app_context():
        doc = Document(
            user_id=user_a.id,
            filename="uuid_test.pdf",
            original_filename="test_invoice.pdf",
            file_path="tests/temp_uploads/test_invoice.pdf",
            file_type="application/pdf",
            file_size=1024,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id

    # View document detail page
    resp = client.get(f'/documents/{doc_id}')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    # Modal markup and triggers must be present
    assert 'id="deleteModal"' in html
    assert 'id="deleteForm"' in html
    assert 'deleteModalDocName' in html
    assert 'data-bs-target="#deleteModal"' in html
    assert f'data-doc-id="{doc_id}"' in html
    assert 'test_invoice.pdf' in html


def test_document_deletion_owner_success(client, app, user_a):
    """Verify authenticated owner can delete a document via POST; DB record and physical file are removed."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    with app.app_context():
        os.makedirs("tests/temp_uploads", exist_ok=True)
        file_path = os.path.abspath("tests/temp_uploads/real_file_to_delete.pdf")
        with open(file_path, "wb") as f:
            f.write(b"%PDF-1.4 mock content")

        doc = Document(
            user_id=user_a.id,
            filename="real_file_to_delete.pdf",
            original_filename="real_file_to_delete.pdf",
            file_path=file_path,
            file_type="application/pdf",
            file_size=1024,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id

        assert os.path.exists(file_path)

    # Execute deletion via POST
    resp = client.post(f'/documents/{doc_id}/delete', follow_redirects=True)
    assert resp.status_code == 200
    assert b"Document deleted successfully." in resp.data

    with app.app_context():
        # Database record must be removed
        assert db.session.get(Document, doc_id) is None
        # Physical file must be removed
        assert not os.path.exists(file_path)


def test_document_deletion_unauthenticated_rejected(client, app, user_a):
    """Unauthenticated users cannot delete documents and are redirected to login."""
    with app.app_context():
        doc = Document(
            user_id=user_a.id,
            filename="doc_unauth.pdf",
            original_filename="doc_unauth.pdf",
            file_path="tests/temp_uploads/doc_unauth.pdf",
            file_type="application/pdf",
            file_size=512,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id

    resp = client.post(f'/documents/{doc_id}/delete')
    assert resp.status_code == 302
    assert '/auth/login' in resp.headers['Location']


def test_document_deletion_user_b_cannot_delete_user_a(client, app, user_a, user_b):
    """User B cannot delete User A's document; returns 404 without modifying User A's document."""
    with app.app_context():
        doc = Document(
            user_id=user_a.id,
            filename="usera_protected.pdf",
            original_filename="usera_protected.pdf",
            file_path="tests/temp_uploads/usera_protected.pdf",
            file_type="application/pdf",
            file_size=512,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id

    # Login as User B
    client.post('/auth/login', data={'email': 'userb@example.com', 'password': 'password123'})

    resp = client.post(f'/documents/{doc_id}/delete')
    assert resp.status_code == 404

    with app.app_context():
        # User A's document must still exist
        assert db.session.get(Document, doc_id) is not None


def test_document_deletion_get_method_rejected(client, app, user_a):
    """GET request to /documents/<id>/delete must be rejected with 405 Method Not Allowed."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    with app.app_context():
        doc = Document(
            user_id=user_a.id,
            filename="doc_get_reject.pdf",
            original_filename="doc_get_reject.pdf",
            file_path="tests/temp_uploads/doc_get_reject.pdf",
            file_type="application/pdf",
            file_size=512,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id

    resp = client.get(f'/documents/{doc_id}/delete')
    assert resp.status_code == 405


def test_document_detail_post_rejected(client, app, user_a):
    """POST to /documents/<id> directly is rejected with 405 Method Not Allowed."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    with app.app_context():
        doc = Document(
            user_id=user_a.id,
            filename="doc_detail_test.pdf",
            original_filename="doc_detail_test.pdf",
            file_path="tests/temp_uploads/doc_detail_test.pdf",
            file_type="application/pdf",
            file_size=512,
            status="processed"
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id

    resp = client.post(f'/documents/{doc_id}')
    assert resp.status_code == 405


# =====================================================================
# BUG 2 REGRESSION TESTS: Report Generation Argument Error & Flow
# =====================================================================

def test_report_data_service_supports_period_start_and_end(app, user_a):
    """Verify ReportDataService.get_report_dataset accepts period_start and period_end keyword args."""
    with app.app_context():
        d_service = report_service.data_service
        dataset = d_service.get_report_dataset(
            user_id=user_a.id,
            report_type='EXECUTIVE',
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31)
        )
        assert isinstance(dataset, dict)
        assert dataset["report_type"] == "EXECUTIVE"
        assert dataset["period_start"] == date(2026, 1, 1)
        assert dataset["period_end"] == date(2026, 1, 31)
        assert "overview" in dataset
        assert "categories" in dataset
        assert "anomalies" in dataset


def test_report_detail_view_with_dataset(client, app, user_a):
    """Verify GET /reports/<id> renders cleanly without TypeError."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    with app.app_context():
        res = report_service.generate_report(
            user_id=user_a.id,
            report_type="EXECUTIVE",
            period="current_month",
            report_title="Monthly Exec Report"
        )
        assert res["status"] == "success"
        report_id = res["report_id"]

    resp = client.get(f'/reports/{report_id}')
    assert resp.status_code == 200
    assert b"Monthly Exec Report" in resp.data
    assert b"TOTAL EXPENSES" in resp.data


def test_reports_get_does_not_create_report(client, app, user_a):
    """GET /reports must only list reports and NEVER create a report or PDF."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    with app.app_context():
        initial_count = Report.query.filter_by(user_id=user_a.id).count()

    # Hit GET /reports multiple times
    client.get('/reports')
    client.get('/reports')
    client.get('/reports')

    with app.app_context():
        final_count = Report.query.filter_by(user_id=user_a.id).count()
        assert final_count == initial_count


def test_custom_date_range_validation_reversal_rejected(client, app, user_a):
    """Submitting custom period with start_date > end_date is safely rejected."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    resp = client.post('/reports/create', data={
        'report_type': 'SPENDING',
        'period': 'custom',
        'start_date': '2026-12-31',
        'end_date': '2026-01-01',
        'report_title': 'Invalid Date Range Report'
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b"Invalid custom date range" in resp.data

    with app.app_context():
        report = Report.query.filter_by(report_name='Invalid Date Range Report').first()
        assert report is None


def test_user_isolation_reports_security(client, app, user_a, user_b):
    """User B cannot view or download User A's reports."""
    with app.app_context():
        res = report_service.generate_report(
            user_id=user_a.id,
            report_type="ANOMALY",
            period="all_time",
            report_title="User A Private Risk Audit"
        )
        report_id = res["report_id"]

    # Login as User B
    client.post('/auth/login', data={'email': 'userb@example.com', 'password': 'password123'})

    resp_detail = client.get(f'/reports/{report_id}', follow_redirects=True)
    assert b"Report not found or access is unauthorized" in resp_detail.data

    resp_download = client.get(f'/reports/{report_id}/download', follow_redirects=True)
    assert b"Report file not found or unauthorized" in resp_download.data


# =====================================================================
# BUG 3 REGRESSION TESTS: AI Assistant Conversation Management
# =====================================================================

def test_assistant_multi_message_same_conversation(client, app, user_a):
    """Two subsequent messages in the same conversation use the same conversation_id."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    # 1. Ask initial question
    res1 = client.post('/api/assistant/ask', json={'question': 'How much did I spend in total?'})
    assert res1.status_code == 200
    data1 = res1.get_json()
    assert 'conversation_id' in data1
    conv_id = data1['conversation_id']
    assert conv_id is not None

    # 2. Ask follow-up question passing same conversation_id
    res2 = client.post('/api/assistant/ask', json={
        'question': 'Which vendor received the most money?',
        'conversation_id': conv_id
    })
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert data2['conversation_id'] == conv_id

    # 3. Verify in database: both turns have conversation_id set
    with app.app_context():
        msgs = ChatHistory.query.filter_by(user_id=user_a.id, conversation_id=conv_id).all()
        assert len(msgs) == 4  # 2 user messages + 2 assistant messages
        user_texts = [m.message for m in msgs if m.role == 'user']
        assert 'How much did I spend in total?' in user_texts
        assert 'Which vendor received the most money?' in user_texts


def test_assistant_new_conversation_creates_separate_id(client, app, user_a):
    """Explicitly starting a new conversation (omitting conversation_id) generates a distinct ID."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    res1 = client.post('/api/assistant/ask', json={'question': 'Question for thread 1'})
    conv_id_1 = res1.get_json()['conversation_id']

    res2 = client.post('/api/assistant/ask', json={'question': 'Question for thread 2'})
    conv_id_2 = res2.get_json()['conversation_id']

    assert conv_id_1 != conv_id_2


def test_assistant_get_conversation_messages_chronological(client, app, user_a):
    """GET /api/assistant/conversation/<id> returns all messages in chronological order."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    res1 = client.post('/api/assistant/ask', json={'question': 'First turn question'})
    conv_id = res1.get_json()['conversation_id']

    client.post('/api/assistant/ask', json={
        'question': 'Second turn question',
        'conversation_id': conv_id
    })

    resp = client.get(f'/api/assistant/conversation/{conv_id}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'success'
    assert data['conversation_id'] == conv_id
    messages = data['messages']
    assert len(messages) == 4
    assert messages[0]['role'] == 'user'
    assert messages[0]['message'] == 'First turn question'
    assert messages[1]['role'] == 'assistant'
    assert messages[2]['role'] == 'user'
    assert messages[2]['message'] == 'Second turn question'
    assert messages[3]['role'] == 'assistant'


def test_assistant_conversation_isolation_user_b_cannot_access_user_a(client, app, user_a, user_b):
    """User B cannot view or modify User A's conversation."""
    # Create conversation for User A
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    res_a = client.post('/api/assistant/ask', json={'question': 'User A secret invoice query'})
    conv_id_a = res_a.get_json()['conversation_id']

    # Logout User A and Login as User B
    client.post('/auth/logout')
    client.post('/auth/login', data={'email': 'userb@example.com', 'password': 'password123'})

    # 1. User B tries to fetch User A's conversation messages
    resp_get = client.get(f'/api/assistant/conversation/{conv_id_a}')
    assert resp_get.status_code in [403, 404]

    # 2. User B tries to post into User A's conversation
    resp_post = client.post('/api/assistant/ask', json={
        'question': 'Attempting unauthorized injection',
        'conversation_id': conv_id_a
    })
    assert resp_post.status_code in [403, 404]


def test_assistant_suggested_questions_not_saved_until_sent(client, app, user_a):
    """Loading the assistant page does NOT create any ChatHistory or conversation records."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    with app.app_context():
        initial_history_count = ChatHistory.query.filter_by(user_id=user_a.id).count()

    resp = client.get('/assistant')
    assert resp.status_code == 200

    with app.app_context():
        final_history_count = ChatHistory.query.filter_by(user_id=user_a.id).count()
        assert final_history_count == initial_history_count


def test_assistant_get_history_and_conversations_endpoint(client, app, user_a):
    """GET /api/assistant/history returns both 'history' (flat list) and 'conversations' (threads)."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    res = client.post('/api/assistant/ask', json={'question': 'Categorize my vendor spend'})
    conv_id = res.get_json()['conversation_id']

    resp = client.get('/api/assistant/history')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'success'
    assert 'history' in data
    assert 'conversations' in data
    assert len(data['conversations']) >= 1
    conv = [c for c in data['conversations'] if c['conversation_id'] == conv_id][0]
    assert conv['first_question'] == 'Categorize my vendor spend'
