"""Dashboard routes."""
"""Dashboard and Financial Intelligence routes."""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, send_from_directory
import logging
from flask_login import login_required, current_user


from app.repositories.dashboard_repository import DashboardRepository
from app.services.dashboard_service import DashboardService
from app.services import (
    financial_intelligence_service, anomaly_detection_service, due_diligence_service, report_service
)
from app.forms.profile_forms import ProfileForm, ChangePasswordForm
from app.extensions import db, limiter
from app.models.user import User


logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

# Initialize dependencies
dashboard_repo = DashboardRepository()
dashboard_service = DashboardService(dashboard_repo)

def generate_priority_alerts(user_id):
    """Delegates priority alert retrieval directly to AnomalyDetectionService (Single Source of Truth)."""
    try:
        return anomaly_detection_service.get_user_anomalies(user_id, limit=3)
    except Exception as e:
        logger.error(f"Error fetching priority alerts for user {user_id}: {e}")
        return []

@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard overview page with pre-calculated initial metrics, trend data, and real anomalies."""
    try:
        initial_data = dashboard_service.get_dashboard_data(current_user.id, '12m')
        priority_alerts = anomaly_detection_service.get_user_anomalies(current_user.id, limit=5)
        dd_report = due_diligence_service.get_due_diligence_report(current_user.id)
    except Exception as e:
        logger.error(f"Error loading dashboard index for user {current_user.id}: {e}")
        initial_data = None
        priority_alerts = []
        dd_report = {"overall_score": 100, "risk_profile": "Low risk profile"}

    return render_template(
        'dashboard/index.html',
        title='Financial Dashboard',
        initial_data=initial_data,
        priority_alerts=priority_alerts,
        dd_report=dd_report
    )


@dashboard_bp.route('/api/data')
@login_required
def api_data():
    """API endpoint for dynamic date-range dashboard data."""
    date_range = request.args.get('range', '12m')
    try:
        data = dashboard_service.get_dashboard_data(current_user.id, date_range)
        anomaly_summary = anomaly_detection_service.get_anomaly_summary(current_user.id)
        data["anomaly_summary"] = anomaly_summary
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error fetching dashboard API data for user {current_user.id}: {e}")
        return jsonify({"error": "Failed to load dashboard data"}), 500


# Application feature & placeholder routes registered at '/' prefix
placeholders_bp = Blueprint('placeholders', __name__)


@placeholders_bp.route('/financial-intelligence')
@login_required
def financial_intelligence():
    """Comprehensive Financial Intelligence command center."""
    try:
        overview = financial_intelligence_service.get_financial_overview(current_user.id)
        categories = financial_intelligence_service.get_spending_by_category(current_user.id)
        vendors = financial_intelligence_service.get_spending_by_vendor(current_user.id, limit=10)
        monthly_trend = financial_intelligence_service.get_monthly_spending_patterns(current_user.id, months=12)
        quarterly_trend = financial_intelligence_service.get_quarterly_spending(current_user.id)
        concentration = financial_intelligence_service.get_spending_concentration(current_user.id)
        recurring = financial_intelligence_service.get_recurring_spending(current_user.id)
        observations = financial_intelligence_service.get_financial_observations(current_user.id)
        anomalies = anomaly_detection_service.get_user_anomalies(current_user.id)
        anomaly_summary = anomaly_detection_service.get_anomaly_summary(current_user.id)
        payment_methods = financial_intelligence_service.get_payment_method_distribution(current_user.id)
    except Exception as e:
        logger.error(f"Error loading financial intelligence page for user {current_user.id}: {e}")
        overview = financial_intelligence_service.get_financial_overview(current_user.id)
        categories = []
        vendors = []
        monthly_trend = []
        quarterly_trend = []
        concentration = {"top_1_pct": 0, "top_3_pct": 0, "concentration_level": "Low", "observation": "No data available."}
        recurring = []
        observations = []
        anomalies = []
        anomaly_summary = {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0, "high_risk_count": 0}
        payment_methods = []

    return render_template(
        'dashboard/financial_intelligence.html',
        title='Financial Intelligence',
        overview=overview,
        categories=categories,
        vendors=vendors,
        monthly_trend=monthly_trend,
        quarterly_trend=quarterly_trend,
        concentration=concentration,
        recurring=recurring,
        observations=observations,
        anomalies=anomalies,
        anomaly_summary=anomaly_summary,
        payment_methods=payment_methods
    )


@placeholders_bp.route('/diligence')
@login_required
def diligence():
    """View for Financial Due Diligence using authoritative DueDiligenceService."""
    try:
        dd_report = due_diligence_service.get_due_diligence_report(current_user.id)
        dd_score = dd_report.get("overall_score", 100)
        total_docs = dd_report.get("total_docs", 0)
        highest_vendor = dd_report.get("highest_vendor")
        highest_vendor_pct = dd_report.get("highest_vendor_pct", 0)
        anomaly_count = dd_report.get("anomalies_count", 0)
    except Exception as e:
        logger.error(f"Error preparing diligence page for user {current_user.id}: {e}")
        dd_score = 100
        total_docs = 0
        highest_vendor = None
        highest_vendor_pct = 0
        anomaly_count = 0
        dd_report = {
            "total_docs": 0,
            "analyzed_docs": 0,
            "completeness_score": 100,
            "consistency_score": 100,
            "stability_rating": "Insufficient Data",
            "concentration_rating": "Low",
            "overall_score": 100,
            "risk_profile": "Low risk profile",
            "highest_vendor": None,
            "highest_vendor_pct": 0,
            "top_3_vendor_pct": 0,
            "anomalies_count": 0,
            "high_risk_anomalies_count": 0,
            "action_items": []
        }

    return render_template(
        'dashboard/diligence.html',
        title='Financial Due Diligence',
        dd_score=dd_score,
        total_docs=total_docs,
        highest_vendor=highest_vendor,
        highest_vendor_pct=highest_vendor_pct,
        anomaly_count=anomaly_count,
        dd_report=dd_report
    )


@placeholders_bp.route('/assistant')
@login_required
def assistant():
    """View for AI Financial Assistant."""
    return render_template('dashboard/assistant.html', title='AI Assistant')


@placeholders_bp.route('/assistant/api/ask', methods=['POST'])
@placeholders_bp.route('/api/assistant/ask', methods=['POST'])
@login_required
@limiter.limit("20 per minute", methods=["POST"])
def assistant_ask():
    """API endpoint for evidence-based AI assistant questions with persistent conversation tracking."""
    from app.services import financial_assistant_service
    from app.models.chat_history import ChatHistory
    
    data = request.get_json(silent=True) or {}
    question = data.get('question')
    conversation_id = data.get('conversation_id')
    
    if not question or not isinstance(question, str) or not question.strip():
        return jsonify({
            "status": "error",
            "answer": "Question text cannot be empty.",
            "intent": "UNKNOWN",
            "confidence": 0.0,
            "facts": {},
            "sources": []
        }), 400

    if len(question.strip()) > 500:
        return jsonify({
            "status": "error",
            "answer": "Question is too long (maximum 500 characters).",
            "intent": "UNKNOWN",
            "confidence": 0.0,
            "facts": {},
            "sources": []
        }), 400

    # User isolation check on conversation_id
    if conversation_id:
        if not isinstance(conversation_id, str) or len(conversation_id) > 64:
            return jsonify({
                "status": "error",
                "answer": "Invalid conversation identifier.",
                "intent": "UNKNOWN",
                "confidence": 0.0,
                "facts": {},
                "sources": []
            }), 400

        # Verify client-supplied conversation_id belongs to current user
        existing_other = ChatHistory.query.filter_by(conversation_id=conversation_id.strip()).first()
        if existing_other and existing_other.user_id != current_user.id:
            return jsonify({
                "status": "error",
                "answer": "Unauthorized: cannot modify another user's conversation.",
                "intent": "UNKNOWN",
                "confidence": 0.0,
                "facts": {},
                "sources": []
            }), 403

    try:
        response = financial_assistant_service.ask_question(
            user_id=current_user.id,
            question=question,
            conversation_id=conversation_id.strip() if conversation_id else None
        )
        status_code = 200
        if response.get("status") == "error":
            status_code = 500
        elif response.get("status") in ["not_found", "unauthorized"]:
            status_code = 404
            
        return jsonify(response), status_code
    except Exception as e:
        logger.error(f"Error processing assistant question for user {current_user.id}: {e}")
        return jsonify({
            "status": "error",
            "answer": "An unexpected server error occurred while processing your question.",
            "intent": "UNKNOWN",
            "confidence": 0.0,
            "facts": {},
            "sources": []
        }), 500


@placeholders_bp.route('/assistant/api/history', methods=['GET'])
@placeholders_bp.route('/api/assistant/history', methods=['GET'])
@login_required
def assistant_history():
    """API endpoint for fetching user-isolated chat history and conversation list."""
    from app.services import financial_assistant_service
    try:
        history = financial_assistant_service.get_user_chat_history(current_user.id)
        conversations = financial_assistant_service.get_user_conversations(current_user.id)
        return jsonify({
            "status": "success",
            "history": history,
            "conversations": conversations
        }), 200
    except Exception as e:
        logger.error(f"Error fetching assistant chat history for user {current_user.id}: {e}")
        return jsonify({
            "status": "error",
            "history": [],
            "conversations": []
        }), 500


@placeholders_bp.route('/assistant/api/conversation/<conversation_id>', methods=['GET'])
@placeholders_bp.route('/api/assistant/conversation/<conversation_id>', methods=['GET'])
@login_required
def assistant_conversation(conversation_id):
    """API endpoint for fetching all messages in a user-owned conversation in chronological order."""
    from app.services import financial_assistant_service
    if not conversation_id or len(conversation_id) > 64:
        return jsonify({
            "status": "error",
            "message": "Invalid conversation ID."
        }), 400

    messages = financial_assistant_service.get_conversation_messages(
        user_id=current_user.id,
        conversation_id=conversation_id.strip()
    )
    if messages is None:
        return jsonify({
            "status": "error",
            "message": "Conversation not found or access denied."
        }), 404

    return jsonify({
        "status": "success",
        "conversation_id": conversation_id,
        "messages": messages
    }), 200


@placeholders_bp.route('/reports', methods=['GET'])
@login_required
def reports():
    """Reports view showing user reports history and creation form."""
    user_reports = report_service.get_user_reports(current_user.id)
    return render_template('dashboard/reports.html', title='Reports', reports=user_reports)


@placeholders_bp.route('/reports/create', methods=['POST'])
@login_required
@limiter.limit("5 per minute", methods=["POST"])
def create_report():
    """Generate a new financial report."""
    if request.is_json:
        data = request.get_json() or {}
        report_type = data.get('report_type')
        period = data.get('period', 'all_time')
        title = data.get('report_title')
        custom_start = data.get('start_date')
        custom_end = data.get('end_date')
    else:
        report_type = request.form.get('report_type')
        period = request.form.get('period', 'all_time')
        title = request.form.get('report_title')
        custom_start = request.form.get('start_date')
        custom_end = request.form.get('end_date')

    res = report_service.generate_report(
        user_id=current_user.id,
        report_type=report_type,
        period=period,
        report_title=title,
        custom_start=custom_start,
        custom_end=custom_end
    )

    if request.is_json or request.headers.get("Accept") == "application/json":
        if res.get("status") == "error":
            return jsonify(res), 400
        return jsonify(res), 200

    if res.get("status") == "error":
        flash(res.get("message", "Error generating report."), "danger")
        return redirect(url_for('placeholders.reports'))

    flash("Financial report generated successfully!", "success")
    return redirect(url_for('placeholders.report_detail', report_id=res["report_id"]))


@placeholders_bp.route('/reports/<int:report_id>', methods=['GET'])
@login_required
def report_detail(report_id):
    """View report metadata and detail summary."""
    report = report_service.get_user_report(report_id, current_user.id)
    if not report:
        if request.is_json:
            return jsonify({"status": "error", "message": "Report not found or unauthorized."}), 404
        flash("Report not found or access is unauthorized.", "danger")
        return redirect(url_for('placeholders.reports'))

    dataset = report_service.data_service.get_report_dataset(
        user_id=current_user.id,
        report_type=report.report_type,
        period_start=report.period_start,
        period_end=report.period_end
    )

    return render_template('dashboard/report_detail.html', title=report.report_name, report=report, dataset=dataset)


@placeholders_bp.route('/reports/<int:report_id>/download', methods=['GET'])
@login_required
def download_report(report_id):
    """Secure report download enforcing user ownership and path traversal defense."""
    reports_dir, safe_filename = report_service.get_report_download_path(report_id, current_user.id)
    if not reports_dir or not safe_filename:
        if request.is_json:
            return jsonify({"status": "error", "message": "Report file not found or unauthorized."}), 404
        flash("Report file not found or unauthorized.", "danger")
        return redirect(url_for('placeholders.reports'))

    report = report_service.get_user_report(report_id, current_user.id)
    clean_name = "".join([c if c.isalnum() else "_" for c in (report.report_name if report else safe_filename)])
    download_name = f"{clean_name}.pdf"

    return send_from_directory(
        reports_dir,
        safe_filename,
        as_attachment=True,
        download_name=download_name
    )


@placeholders_bp.route('/reports/<int:report_id>/delete', methods=['POST'])
@login_required
def delete_report(report_id):
    """Secure report deletion enforcing user ownership."""
    success = report_service.delete_report(report_id, current_user.id)
    if not success:
        if request.is_json:
            return jsonify({"status": "error", "message": "Report not found or unauthorized."}), 404
        flash("Report not found or access is unauthorized.", "danger")
        return redirect(url_for('placeholders.reports'))

    if request.is_json:
        return jsonify({"status": "success", "message": "Report deleted successfully."}), 200

    flash("Report deleted successfully.", "success")
    return redirect(url_for('placeholders.reports'))



@placeholders_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """View and update user profile & password."""
    profile_form = ProfileForm(prefix="profile")
    password_form = ChangePasswordForm(prefix="password")
    
    # Initialize forms with current user data if GET
    if request.method == 'GET':
        profile_form.full_name.data = current_user.full_name
        profile_form.username.data = current_user.username
        profile_form.email.data = current_user.email
        
    if profile_form.validate_on_submit() and profile_form.submit.data:
        from app.models.user import User
        # Check uniqueness of username
        existing_user = User.query.filter(User.username == profile_form.username.data, User.id != current_user.id).first()
        if existing_user:
            flash("Username is already taken.", "danger")
            return redirect(url_for('placeholders.profile'))
            
        # Check uniqueness of email
        existing_email = User.query.filter(User.email == profile_form.email.data.lower().strip(), User.id != current_user.id).first()
        if existing_email:
            flash("Email is already registered.", "danger")
            return redirect(url_for('placeholders.profile'))
            
        current_user.full_name = profile_form.full_name.data
        current_user.username = profile_form.username.data
        current_user.email = profile_form.email.data.lower().strip()
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('placeholders.profile'))
        
    if password_form.validate_on_submit() and password_form.submit.data:
        if not current_user.check_password(password_form.current_password.data):
            flash("Incorrect current password.", "danger")
            return redirect(url_for('placeholders.profile'))
            
        current_user.set_password(password_form.new_password.data)
        db.session.commit()
        flash("Password updated successfully!", "success")
        return redirect(url_for('placeholders.profile'))
        
    return render_template(
        'dashboard/profile.html',
        title='Profile',
        profile_form=profile_form,
        password_form=password_form
    )


@placeholders_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """View and update session-based application settings."""
    if request.method == 'POST':
        session['reduced_motion'] = request.form.get('reduced_motion', 'false')
        session['dashboard_animation'] = request.form.get('dashboard_animation', 'true')
        session['default_ocr_pref'] = request.form.get('default_ocr_pref', 'formatted')
        session['theme'] = request.form.get('theme', 'light')
        flash("Settings saved successfully!", "success")
        return redirect(url_for('placeholders.settings'))
        
    current_settings = {
        'reduced_motion': session.get('reduced_motion', 'false'),
        'dashboard_animation': session.get('dashboard_animation', 'true'),
        'default_ocr_pref': session.get('default_ocr_pref', 'formatted'),
        'theme': session.get('theme', 'light')
    }
    
    return render_template(
        'dashboard/settings.html',
        title='Settings',
        settings=current_settings
    )

