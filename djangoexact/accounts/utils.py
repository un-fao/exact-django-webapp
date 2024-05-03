from django.conf import settings
from django.core.mail import send_mail

from accounts.firebase import auth as firebase_admin_auth


# Create custom email verification link
def send_email_verification_link(user_email, display_name):
    action_code_settings = {
        firebase_admin_auth.ActionCodeSettings(
            url="https://exact.fao.org/",
            handle_code_in_app=True,
        )
    }
    custom_email_link = firebase_admin_auth.generate_email_verification_link(user_email)
    subject = "Verify your email address"
    message = f"Hi {display_name},\n\nPlease verify your email address by clicking on the link below:\n\n{custom_email_link}"
    send_mail(subject, message, settings.EMAIL_HOST_USER, [user_email], fail_silently=False)
