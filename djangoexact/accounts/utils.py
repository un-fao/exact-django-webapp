from django.conf import settings
from django.core.mail import send_mail

from accounts.firebase import firebase_admin_auth


# Create custom email verification link
def send_email_verification_link(user_email, display_name):
    custom_email_link = firebase_admin_auth.generate_email_verification_link(user_email)
    subject = "Verify your email address"
    message = f"Hi {display_name},\n\nPlease verify your email address by clicking on the link below:\n\n{custom_email_link}"
    send_mail(subject, message, settings.EMAIL_HOST_USER, [user_email], fail_silently=False)


def send_password_reset_link(user_email):
    custom_email_link = firebase_admin_auth.generate_password_reset_link(user_email)
    subject = "Reset your password"
    message = f"Hi,\n\nPlease reset your password by clicking on the link below:\n\n{custom_email_link}"
    send_mail(subject, message, settings.EMAIL_HOST_USER, [user_email], fail_silently=False)
