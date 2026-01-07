# In minitool/management/commands/cleanup_sqlite.py
from django.core.management.base import BaseCommand
import os
from django.conf import settings


class Command(BaseCommand):
    def handle(self, *args, **options):
        db_path = settings.DATABASES["minitool"]["NAME"]
        wal_file = f"{db_path}-wal"
        shm_file = f"{db_path}-shm"

        for file_path in [wal_file, shm_file]:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.stdout.write(f"Removed {file_path}")
