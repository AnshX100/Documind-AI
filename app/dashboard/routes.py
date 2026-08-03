"""Dashboard routes."""

from flask import Blueprint, render_template
from flask_login import login_required, current_user

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard home page."""
    return render_template('dashboard/index.html', title='Dashboard')
