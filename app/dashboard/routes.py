"""Dashboard routes."""

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.services import document_repository

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard home page."""
    # Get statistics for the dashboard
    counts = document_repository.count_user_documents_by_status(current_user.id)
    recent_docs = document_repository.get_recent_user_documents(current_user.id, limit=5)
    
    return render_template(
        'dashboard/index.html', 
        title='Dashboard',
        counts=counts,
        recent_docs=recent_docs
    )
