from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class Command(BaseCommand):
    help = "Create or update the admin user with email admin@admin.com and password admin"

    def handle(self, *args, **options):
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

            # Set the password (always update it to ensure it's correct)
            admin_user.set_password("admin")
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.is_active = True
            admin_user.save()

            if created:
                self.stdout.write(self.style.SUCCESS("Successfully created admin user with email: admin@admin.com"))
            else:
                self.stdout.write(self.style.SUCCESS("Successfully updated admin user with email: admin@admin.com"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to create/update admin user: {e}"))
            logger.error(f"Failed to create/update admin user: {e}")
