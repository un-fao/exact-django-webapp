"""
Django management command to sync Firebase email addresses with Django user model emails.

This command:
1. Iterates through all users in the database
2. Checks if Firebase email matches Django model email
3. Updates Firebase email if they don't match
4. Sends verification email to the user
"""

from django.core.management.base import BaseCommand
from firebase_admin import auth as firebase_admin_auth
from firebase_admin.exceptions import NotFoundError
import logging

from api.models import CustomUser
import accounts.utils as account_utils

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Command(BaseCommand):
    help = "Sync Firebase email addresses with Django user model emails and send verification emails"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without actually updating",
        )
        parser.add_argument(
            "--skip-email",
            action="store_true",
            help="Update Firebase email but skip sending verification email",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_email = options["skip_email"]

        users = CustomUser.objects.filter(firebase_uid__isnull=False).exclude(firebase_uid="")
        total_users = users.count()
        updated_count = 0
        error_count = 0
        skipped_count = 0

        self.stdout.write(self.style.SUCCESS(f"Processing {total_users} users with Firebase UIDs..."))

        for user in users:
            try:
                django_email = user.email.casefold().strip()

                try:
                    firebase_user = firebase_admin_auth.get_user(user.firebase_uid)
                    firebase_email = firebase_user.email

                    if firebase_email:
                        firebase_email_normalized = firebase_email.casefold().strip()
                    else:
                        firebase_email_normalized = None
                except NotFoundError:
                    self.stdout.write(self.style.WARNING(f"User {user.pk} ({user.email}): Firebase user not found for UID {user.firebase_uid}"))
                    skipped_count += 1
                    continue

                if firebase_email_normalized != django_email:
                    if dry_run:
                        self.stdout.write(self.style.WARNING(f"[DRY RUN] Would update user {user.pk} ({user.email}): Firebase email '{firebase_email}' -> Django email '{user.email}'"))
                        updated_count += 1
                    else:
                        try:
                            firebase_admin_auth.update_user(user.firebase_uid, email=django_email, email_verified=False)

                            if not skip_email:
                                display_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                                if not display_name:
                                    display_name = user.email
                                account_utils.send_email_verification_link_sync(django_email, display_name)

                            self.stdout.write(self.style.SUCCESS(f"Updated user {user.pk} ({user.email}): Firebase email '{firebase_email}' -> '{django_email}'"))
                            updated_count += 1
                        except Exception as e:
                            logger.error(f"Failed to update Firebase email for user {user.pk} ({user.email}): {e}")
                            self.stdout.write(self.style.ERROR(f"Error updating user {user.pk} ({user.email}): {str(e)}"))
                            error_count += 1
                else:
                    if dry_run:
                        self.stdout.write(f"User {user.pk} ({user.email}): Emails match, skipping")

            except Exception as e:
                logger.error(f"Error processing user {user.pk} ({user.email}): {e}")
                self.stdout.write(self.style.ERROR(f"Error processing user {user.pk} ({user.email}): {str(e)}"))
                error_count += 1

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("Summary:"))
        self.stdout.write(self.style.SUCCESS(f"  Total users processed: {total_users}"))
        self.stdout.write(self.style.SUCCESS(f"  Updated: {updated_count}"))
        self.stdout.write(self.style.SUCCESS(f"  Skipped (no Firebase user): {skipped_count}"))
        self.stdout.write(self.style.ERROR(f"  Errors: {error_count}"))
        if dry_run:
            self.stdout.write(self.style.WARNING("  [DRY RUN] No actual changes were made"))
