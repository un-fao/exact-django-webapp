from django.contrib.auth import get_user_model
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class AdminAuthenticationMiddleware:
    """
    Middleware that automatically authenticates all requests with admin@admin.com credentials.
    This bypasses the normal Firebase authentication for development/testing purposes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip authentication for certain paths
        skip_paths = [
            "/api/accounts/register/",
            "/api/accounts/login/",
            "/api/accounts/token/refresh/",
            "/api/accounts/password-reset/",
            "/admin",
            "/api/swagger/",
        ]

        # Check if the request path should skip authentication
        should_skip = any(request.path.startswith(path) for path in skip_paths)

        if not should_skip:
            try:
                # Get or create the admin user
                admin_user, created = User.objects.get_or_create(
                    email="admin@admin.com",
                    defaults={
                        "is_staff": True,
                        "is_superuser": True,
                        "is_active": True,
                    },
                )

                # Set the password if user was just created
                if created:
                    admin_user.set_password("admin")
                    admin_user.save()
                    logger.info("Created admin user with email: admin@admin.com")

                # Authenticate the request with the admin user
                request.user = admin_user
                request._force_auth_user = admin_user  # Flag to indicate forced authentication

                logger.debug(f"Authenticated request as admin user: {admin_user.email}")

            except Exception as e:
                logger.error(f"Failed to authenticate as admin user: {e}")
                # If something goes wrong, let the request proceed without authentication
                # The existing permission classes will handle it
                pass

        response = self.get_response(request)
        return response
