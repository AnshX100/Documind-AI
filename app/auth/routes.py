"""Authentication routes and blueprint registration."""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from urllib.parse import urlsplit

from app.forms.auth_forms import LoginForm, RegistrationForm
from app.services import auth_service

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    form = RegistrationForm()
    if form.validate_on_submit():
        success, message, user = auth_service.register_user(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data,
            full_name=form.full_name.data
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(message, 'danger')
            
    return render_template('auth/register.html', title='Register', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    form = LoginForm()
    if form.validate_on_submit():
        success, message = auth_service.login_user(
            email=form.email.data,
            password=form.password.data,
            remember=form.remember_me.data
        )
        
        if success:
            flash(message, 'success')
            next_page = request.args.get('next')
            # Protect against open redirect attacks
            if not next_page or urlsplit(next_page).netloc != '':
                next_page = url_for('dashboard.index')
            return redirect(next_page)
        else:
            flash(message, 'danger')
            
    return render_template('auth/login.html', title='Sign In', form=form)

@auth_bp.route('/logout')
def logout():
    """User logout route."""
    auth_service.logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
