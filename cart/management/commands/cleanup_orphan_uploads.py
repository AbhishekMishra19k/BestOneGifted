"""
Fixes SECURITY_AUDIT.md #14: personalization photos are written to
media/personalizations/ the moment a customer clicks "Add to Cart" — before
any Order exists. If they abandon the cart (extremely common), the file is
never referenced by an OrderItem and sits on disk forever.

Run this periodically (e.g. a daily cron job / Render Cron Job / GitHub
Action scheduled workflow) to delete personalization uploads older than
N days that were never attached to an actual order:

    python manage.py cleanup_orphan_uploads --days 3
    python manage.py cleanup_orphan_uploads --days 3 --dry-run
"""
import os
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import OrderItem


class Command(BaseCommand):
    help = 'Delete orphaned personalization photo uploads not linked to any order.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=3, help='Delete files older than this many days (default: 3)')
        parser.add_argument('--dry-run', action='store_true', help='List what would be deleted without deleting')

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cutoff = timezone.now().timestamp() - (days * 86400)

        personalizations_dir = os.path.join(settings.MEDIA_ROOT, 'personalizations')
        if not os.path.isdir(personalizations_dir):
            self.stdout.write('No personalizations directory found — nothing to do.')
            return

        # Every filename currently referenced by a real order (never delete these)
        in_use = set(
            OrderItem.objects.exclude(custom_photo='').values_list('custom_photo', flat=True)
        )
        in_use_basenames = {os.path.basename(name) for name in in_use if name}

        deleted, kept, skipped_recent = 0, 0, 0
        for filename in os.listdir(personalizations_dir):
            full_path = os.path.join(personalizations_dir, filename)
            if not os.path.isfile(full_path):
                continue
            if filename in in_use_basenames:
                kept += 1
                continue
            if os.path.getmtime(full_path) > cutoff:
                skipped_recent += 1
                continue

            if dry_run:
                self.stdout.write(f'[dry-run] Would delete: {filename}')
            else:
                os.remove(full_path)
            deleted += 1

        action = 'Would delete' if dry_run else 'Deleted'
        self.stdout.write(self.style.SUCCESS(
            f'{action} {deleted} orphaned file(s). Kept {kept} (linked to orders), '
            f'skipped {skipped_recent} (too recent — still might become a real order).'
        ))
