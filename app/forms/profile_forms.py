"""WTForms for profile management and password changes."""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Regexp

class ProfileForm(FlaskForm):
    """Form to update basic user profile metadata."""
    full_name = StringField('Full Name', validators=[Length(max=150)])
    username = StringField(
        'Username', 
        validators=[
            DataRequired(), 
            Length(min=3, max=80),
            Regexp(r'^[\w.@+-]+$', message="Username can contain only letters, numbers, and . @ + - _")
        ]
    )
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField('Update Profile')

class ChangePasswordForm(FlaskForm):
    """Form to safely update account password."""
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        'Confirm New Password', 
        validators=[
            DataRequired(), 
            EqualTo('new_password', message='New passwords must match')
        ]
    )
    submit = SubmitField('Change Password')
