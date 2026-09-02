"""
Management command to safely and explicitly link an existing Django user account to a Supabase user UUID.
"""

import uuid
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from core.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = 'Safely link an existing Django user to a Supabase UUID'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username of the existing Django user to link',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email of the existing Django user to link',
        )
        parser.add_argument(
            '--supabase-uid',
            type=str,
            required=True,
            help='Supabase user UUID to link',
        )

    def handle(self, *args, **options):
        username = options.get('username')
        email = options.get('email')
        supabase_uid_str = options.get('supabase_uid')

        if not username and not email:
            raise CommandError('You must provide either --username or --email to identify the Django user.')

        try:
            supabase_uuid = uuid.UUID(supabase_uid_str)
        except ValueError:
            raise CommandError(f'Invalid UUID format: {supabase_uid_str}')

        # Check if UUID is already linked to another user
        existing_profile_with_uid = UserProfile.objects.filter(supabase_uid=supabase_uuid).first()
        if existing_profile_with_uid:
            raise CommandError(
                f'Supabase UID {supabase_uuid} is already linked to Django user "{existing_profile_with_uid.user.username}".'
            )

        # Find target user
        if username:
            user = User.objects.filter(username=username).first()
            if not user:
                raise CommandError(f'User with username "{username}" not found.')
        else:
            user = User.objects.filter(email=email).first()
            if not user:
                raise CommandError(f'User with email "{email}" not found.')

        if not hasattr(user, 'profile'):
            raise CommandError(f'User "{user.username}" does not have an associated UserProfile.')

        user.profile.supabase_uid = supabase_uuid
        user.profile.save(update_fields=['supabase_uid'])

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully linked Django user "{user.username}" ({user.profile.role}) to Supabase UID {supabase_uuid}.'
            )
        )
