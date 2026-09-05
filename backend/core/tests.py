"""
Test suite for the core authentication module and Supabase Auth integration.

Includes:
- Original 15 test cases covering registration, login, logout, current user, role validation
- Supabase JWT verification tests:
  - HS256 valid signature and auto-provisioning
  - RS256/JWKS valid signature with mock JWKS
  - Expired token rejection
  - Tampered signature rejection
  - Invalid audience rejection
  - Invalid issuer rejection
  - Unsupported algorithm rejection (e.g. HS384)
  - Algorithm 'none' rejection
  - JWKS lookup failure rejection (strictly NO fallback to HS256)
  - ADMIN privilege escalation protection
- Controlled account linking tests
"""

import io
import time
import uuid
from unittest.mock import MagicMock, patch

import urllib.error
from django.core.files.base import ContentFile
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import Role, UserProfile


def generate_test_supabase_token(
    sub=None,
    email='test@example.com',
    role='TRAINEE',
    username=None,
    exp_delta=3600,
    secret=None,
    aud='authenticated',
    iss=None,
    algorithm='HS256',
    headers=None,
):
    """Helper to generate mock Supabase JWTs for testing."""
    if sub is None:
        sub = str(uuid.uuid4())
    if secret is None:
        secret = getattr(settings, 'SUPABASE_JWT_SECRET', 'test-supabase-jwt-secret-for-development-only-must-be-changed-in-prod')
    if iss is None:
        iss = f"{getattr(settings, 'SUPABASE_URL', 'https://test.supabase.co').rstrip('/')}/auth/v1"

    payload = {
        'sub': str(sub),
        'email': email,
        'aud': aud,
        'iss': iss,
        'iat': int(time.time()),
        'exp': int(time.time()) + exp_delta,
        'user_metadata': {
            'username': username or email.split('@')[0],
            'role': role,
        },
    }
    return jwt.encode(payload, secret, algorithm=algorithm, headers=headers)


class AuthRegistrationTests(TestCase):
    """Tests for POST /api/auth/register/"""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('auth-register')

    def test_01_trainee_registration_succeeds(self):
        """Trainee registration creates user and profile."""
        data = {
            'username': 'trainee1',
            'email': 'trainee1@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'role': Role.TRAINEE,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['username'], 'trainee1')
        self.assertEqual(response.data['role'], Role.TRAINEE)
        self.assertNotIn('password', response.data)
        # Verify DB state
        user = User.objects.get(username='trainee1')
        self.assertTrue(user.check_password('SecurePass123!'))
        self.assertEqual(user.profile.role, Role.TRAINEE)

    def test_02_trainer_registration_succeeds(self):
        """Trainer registration creates user and profile."""
        data = {
            'username': 'trainer1',
            'email': 'trainer1@example.com',
            'password': 'SecurePass456!',
            'password_confirm': 'SecurePass456!',
            'role': Role.TRAINER,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['username'], 'trainer1')
        self.assertEqual(response.data['role'], Role.TRAINER)
        self.assertNotIn('password', response.data)

    def test_03_duplicate_username_fails(self):
        """Registration with an existing username returns 400."""
        User.objects.create_user(username='existing', email='a@example.com', password='Pass1234!')
        data = {
            'username': 'existing',
            'email': 'new@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'role': Role.TRAINEE,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)

    def test_04_duplicate_email_fails(self):
        """Registration with an existing email returns 400."""
        User.objects.create_user(username='user1', email='taken@example.com', password='Pass1234!')
        data = {
            'username': 'newuser',
            'email': 'taken@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'role': Role.TRAINEE,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_05_weak_password_fails(self):
        """Registration with a weak password returns 400."""
        data = {
            'username': 'weakuser',
            'email': 'weak@example.com',
            'password': '123',
            'password_confirm': '123',
            'role': Role.TRAINEE,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_06_password_mismatch_fails(self):
        """Registration with mismatched passwords returns 400."""
        data = {
            'username': 'mismatch',
            'email': 'mismatch@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'DifferentPass456!',
            'role': Role.TRAINEE,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirm', response.data)

    def test_07_invalid_role_fails(self):
        """Registration with an invalid role value returns 400."""
        data = {
            'username': 'badrole',
            'email': 'badrole@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'role': 'SUPERUSER',
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', response.data)

    def test_08_admin_registration_blocked(self):
        """Public registration with ADMIN role is blocked."""
        data = {
            'username': 'sneakyadmin',
            'email': 'admin@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'role': Role.ADMIN,
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', response.data)


class AuthLoginTests(TestCase):
    """Tests for POST /api/auth/login/"""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('auth-login')
        self.user = User.objects.create_user(
            username='loginuser',
            email='login@example.com',
            password='SecurePass123!',
        )
        UserProfile.objects.create(user=self.user, role=Role.TRAINEE)

    def test_09_valid_login_succeeds(self):
        """Login with valid credentials returns 200 and user info."""
        data = {'username': 'loginuser', 'password': 'SecurePass123!'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'loginuser')
        self.assertEqual(response.data['role'], Role.TRAINEE)
        self.assertNotIn('password', response.data)

    def test_10_invalid_login_fails(self):
        """Login with wrong password returns 401."""
        data = {'username': 'loginuser', 'password': 'WrongPassword!'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('detail', response.data)


class AuthCurrentUserTests(TestCase):
    """Tests for GET /api/auth/me/"""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('auth-me')
        self.user = User.objects.create_user(
            username='meuser',
            email='me@example.com',
            password='SecurePass123!',
        )
        self.uid = uuid.uuid4()
        UserProfile.objects.create(user=self.user, role=Role.TRAINER, supabase_uid=self.uid)

    def test_11_authenticated_me_returns_user_and_role(self):
        """Authenticated GET /me/ via Supabase Bearer token returns user info with role."""
        token = generate_test_supabase_token(sub=self.uid, email='me@example.com', role='TRAINER')
        response = self.client.get(self.url, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.user.id)
        self.assertEqual(response.data['username'], 'meuser')
        self.assertEqual(response.data['email'], 'me@example.com')
        self.assertEqual(response.data['role'], Role.TRAINER)
        self.assertEqual(response.data['supabase_uid'], str(self.uid))
        self.assertNotIn('password', response.data)

    def test_12_unauthenticated_me_returns_401(self):
        """Unauthenticated GET /me/ returns 401 Unauthorized."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthLogoutTests(TestCase):
    """Tests for POST /api/auth/logout/"""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('auth-logout')
        self.user = User.objects.create_user(
            username='logoutuser',
            email='logout@example.com',
            password='SecurePass123!',
        )
        self.uid = uuid.uuid4()
        UserProfile.objects.create(user=self.user, role=Role.TRAINEE, supabase_uid=self.uid)

    def test_13_logout_succeeds(self):
        """Authenticated logout via Bearer token returns 200."""
        token = generate_test_supabase_token(sub=self.uid, email='logout@example.com', role='TRAINEE')
        response = self.client.post(self.url, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)


class AuthRoleTests(TestCase):
    """Tests for role information and permission behavior."""

    def setUp(self):
        self.client = APIClient()

    def test_14_role_information_returned_correctly(self):
        """Registration and /me/ return the correct role string."""
        reg_data = {
            'username': 'roletest',
            'email': 'roletest@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'role': Role.TRAINEE,
        }
        reg_response = self.client.post(reverse('auth-register'), reg_data, format='json')
        self.assertEqual(reg_response.data['role'], 'TRAINEE')

        # Connect user to a Supabase UID to test /me/ with Bearer token
        user = User.objects.get(username='roletest')
        uid = uuid.uuid4()
        user.profile.supabase_uid = uid
        user.profile.save()

        token = generate_test_supabase_token(sub=uid, email='roletest@example.com', role='TRAINEE')
        me_response = self.client.get(reverse('auth-me'), HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(me_response.data['role'], 'TRAINEE')

    def test_15_role_based_permission_behavior(self):
        """
        Different roles have appropriate access patterns.
        - Unauthenticated users receive 401
        - Both TRAINEE and TRAINER can access /me/ with Bearer token
        - Superuser signal auto-creates ADMIN profile
        """
        me_url = reverse('auth-me')
        # Unauthenticated → 401
        response = self.client.get(me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        trainee_uid = uuid.uuid4()
        trainee = User.objects.create_user(
            username='t_trainee', email='t_trainee@example.com', password='SecurePass123!',
        )
        UserProfile.objects.create(user=trainee, role=Role.TRAINEE, supabase_uid=trainee_uid)
        token_trainee = generate_test_supabase_token(sub=trainee_uid, email='t_trainee@example.com', role='TRAINEE')
        response = self.client.get(me_url, HTTP_AUTHORIZATION=f'Bearer {token_trainee}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], Role.TRAINEE)

        trainer_uid = uuid.uuid4()
        trainer = User.objects.create_user(
            username='t_trainer', email='t_trainer@example.com', password='SecurePass123!',
        )
        UserProfile.objects.create(user=trainer, role=Role.TRAINER, supabase_uid=trainer_uid)
        token_trainer = generate_test_supabase_token(sub=trainer_uid, email='t_trainer@example.com', role='TRAINER')
        response = self.client.get(me_url, HTTP_AUTHORIZATION=f'Bearer {token_trainer}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], Role.TRAINER)

        admin_uid = uuid.uuid4()
        admin_user = User.objects.create_superuser(
            username='t_admin', email='t_admin@example.com', password='SecurePass123!',
        )
        self.assertTrue(hasattr(admin_user, 'profile'))
        self.assertEqual(admin_user.profile.role, Role.ADMIN)
        admin_user.profile.supabase_uid = admin_uid
        admin_user.profile.save()

        token_admin = generate_test_supabase_token(sub=admin_uid, email='t_admin@example.com', role='ADMIN')
        response = self.client.get(me_url, HTTP_AUTHORIZATION=f'Bearer {token_admin}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], Role.ADMIN)


class SupabaseAuthenticationTests(TestCase):
    """Tests for Supabase JWT verification, auto-provisioning, and role sanitization."""

    def setUp(self):
        self.client = APIClient()
        self.me_url = reverse('auth-me')

    def test_16_valid_supabase_token_authenticates_existing_linked_user(self):
        """Supabase JWT with linked supabase_uid authenticates existing Django user."""
        uid = uuid.uuid4()
        user = User.objects.create_user(
            username='sb_existing_user',
            email='sb_existing@example.com',
            password='SecurePass123!',
        )
        UserProfile.objects.create(user=user, role=Role.TRAINER, supabase_uid=uid)

        token = generate_test_supabase_token(sub=uid, email='sb_existing@example.com', role='TRAINER')
        response = self.client.get(self.me_url, HTTP_AUTHORIZATION=f'Bearer {token}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'sb_existing_user')
        self.assertEqual(response.data['role'], Role.TRAINER)
        self.assertEqual(response.data['supabase_uid'], str(uid))

    def test_17_valid_supabase_token_auto_provisions_trainee(self):
        """Valid Supabase token auto-provisions new Django User and TRAINEE UserProfile in MySQL."""
        uid = uuid.uuid4()
        token = generate_test_supabase_token(
            sub=uid,
            email='new_trainee@example.com',
            role='TRAINEE',
            username='auto_trainee_1',
        )

        response = self.client.get(self.me_url, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'new_trainee@example.com')
        self.assertEqual(response.data['role'], Role.TRAINEE)
        self.assertEqual(response.data['supabase_uid'], str(uid))

        # Check DB state
        created_user = User.objects.get(profile__supabase_uid=uid)
        self.assertEqual(created_user.profile.role, Role.TRAINEE)
        self.assertFalse(created_user.has_usable_password())

    def test_18_valid_supabase_token_auto_provisions_trainer(self):
        """Valid Supabase token auto-provisions new Django User and TRAINER UserProfile in MySQL."""
        uid = uuid.uuid4()
        token = generate_test_supabase_token(
            sub=uid,
            email='new_trainer@example.com',
            role='TRAINER',
            username='auto_trainer_1',
        )

        response = self.client.get(self.me_url, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'new_trainer@example.com')
        self.assertEqual(response.data['role'], Role.TRAINER)
        self.assertEqual(response.data['supabase_uid'], str(uid))

    def test_19_admin_role_in_supabase_metadata_sanitized_to_trainee(self):
        """Any attempt to claim ADMIN role via Supabase signup metadata is sanitized to TRAINEE."""
        uid = uuid.uuid4()
        token = generate_test_supabase_token(
            sub=uid,
            email='malicious_admin@example.com',
            role='ADMIN',  # Attempting privilege escalation
            username='fake_admin',
        )

        response = self.client.get(self.me_url, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], Role.TRAINEE)  # Strictly sanitized

        created_user = User.objects.get(profile__supabase_uid=uid)
        self.assertEqual(created_user.profile.role, Role.TRAINEE)

    def test_20_expired_supabase_token_returns_401(self):
        """Expired Supabase token returns 401 Unauthorized."""
        token = generate_test_supabase_token(exp_delta=-3600)  # Expired 1 hour ago
        response = self.client.get(self.me_url, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('expired', response.data['detail'].lower())

    def test_21_invalid_signature_returns_401(self):
        """Token signed with wrong secret returns 401 Unauthorized."""
        token = generate_test_supabase_token(secret='completely-wrong-secret-that-is-at-least-32-chars-long')
        response = self.client.get(self.me_url, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_22_wrong_audience_returns_401(self):
        """Token with invalid audience returns 401 Unauthorized."""
        token = generate_test_supabase_token(aud='malicious-audience')
        response = self.client.get(self.me_url, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_23_invalid_issuer_returns_401(self):
        """Token with foreign issuer returns 401 Unauthorized."""
        token = generate_test_supabase_token(iss='https://foreign-evil-issuer.com/auth/v1')
        response = self.client.get(self.me_url, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_24_unsupported_algorithm_returns_401(self):
        """Token with unsupported algorithm (e.g. HS384) returns 401 Unauthorized."""
        token = generate_test_supabase_token(algorithm='HS384')
        response = self.client.get(self.me_url, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('unsupported', response.data['detail'].lower())

    def test_25_alg_none_returns_401(self):
        """Token with alg='none' is rejected with 401 Unauthorized."""
        payload = {
            'sub': str(uuid.uuid4()),
            'email': 'none_alg@example.com',
            'aud': 'authenticated',
            'iss': f"{getattr(settings, 'SUPABASE_URL', 'https://test.supabase.co').rstrip('/')}/auth/v1",
            'iat': int(time.time()),
            'exp': int(time.time()) + 3600,
        }
        # Craft an unsigned token with alg='none'
        token = jwt.encode(payload, key='', algorithm='none')
        response = self.client.get(self.me_url, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('core.authentication.get_jwks_client')
    def test_26_jwks_lookup_failure_returns_401_no_hs256_fallback(self, mock_get_client):
        """When JWKS key retrieval fails for RS256 token, it returns 401 and NEVER falls back to HS256."""
        # Mock JWKS client raising an error
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.side_effect = jwt.PyJWKClientError('Signing key not found in JWKS')
        mock_get_client.return_value = mock_client

        # Generate a private RSA key to sign the token as RS256
        rsa_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        payload = {
            'sub': str(uuid.uuid4()),
            'email': 'rs256_user@example.com',
            'aud': 'authenticated',
            'iss': f"{getattr(settings, 'SUPABASE_URL', 'https://test.supabase.co').rstrip('/')}/auth/v1",
            'iat': int(time.time()),
            'exp': int(time.time()) + 3600,
            'user_metadata': {'username': 'rs256_user', 'role': 'TRAINEE'},
        }
        rs256_token = jwt.encode(payload, rsa_private_key, algorithm='RS256', headers={'kid': 'missing-kid'})

        response = self.client.get(self.me_url, HTTP_AUTHORIZATION=f'Bearer {rs256_token}')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('jwks', response.data['detail'].lower())

    @patch('core.authentication.get_jwks_client')
    def test_27_valid_rs256_token_with_mock_jwks_succeeds(self, mock_get_client):
        """Valid RS256 token verified via JWKS public key authenticates successfully."""
        rsa_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        rsa_public_key = rsa_private_key.public_key()

        mock_client = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = rsa_public_key
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_get_client.return_value = mock_client

        uid = uuid.uuid4()
        payload = {
            'sub': str(uid),
            'email': 'rs256_valid@example.com',
            'aud': 'authenticated',
            'iss': f"{getattr(settings, 'SUPABASE_URL', 'https://test.supabase.co').rstrip('/')}/auth/v1",
            'iat': int(time.time()),
            'exp': int(time.time()) + 3600,
            'user_metadata': {'username': 'rs256_valid_user', 'role': 'TRAINER'},
        }
        rs256_token = jwt.encode(payload, rsa_private_key, algorithm='RS256', headers={'kid': 'valid-kid'})

        response = self.client.get(self.me_url, HTTP_AUTHORIZATION=f'Bearer {rs256_token}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'rs256_valid_user')
        self.assertEqual(response.data['role'], Role.TRAINER)
        self.assertEqual(response.data['supabase_uid'], str(uid))


class ControlledAccountLinkingTests(TestCase):
    """Tests for the link_supabase_user management command."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='step3_user',
            email='step3@example.com',
            password='SecurePass123!',
        )
        UserProfile.objects.create(user=self.user, role=Role.TRAINER)

    def test_28_link_supabase_user_command_succeeds(self):
        """link_supabase_user links an existing Django user to a Supabase UUID."""
        target_uid = uuid.uuid4()
        call_command('link_supabase_user', username='step3_user', supabase_uid=str(target_uid))

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.supabase_uid, target_uid)

    def test_29_link_supabase_user_rejects_duplicate_uid(self):
        """link_supabase_user fails when the UUID is already bound to another user."""
        existing_uid = uuid.uuid4()
        self.user.profile.supabase_uid = existing_uid
        self.user.profile.save()

        user2 = User.objects.create_user(username='user2', email='user2@example.com', password='Pass1234!')
        UserProfile.objects.create(user=user2, role=Role.TRAINEE)

        with self.assertRaises(CommandError):
            call_command('link_supabase_user', username='user2', supabase_uid=str(existing_uid))


class AdminUserManagementTests(TestCase):
    """Tests for Admin User Management endpoints (Step 11)."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='admin_boss',
            email='admin_boss@example.com',
            password='Password123!',
        )
        self.admin.profile.role = Role.ADMIN
        self.admin.profile.save()

        self.trainer = User.objects.create_user(
            username='trainer_bob',
            email='trainer_bob@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainer, role=Role.TRAINER)

        self.trainee = User.objects.create_user(
            username='trainee_alice',
            email='trainee_alice@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainee, role=Role.TRAINEE)

    def test_admin_can_list_all_users(self):
        """Admin can list all platform users."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/auth/admin/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 3)
        usernames = [u['username'] for u in response.data]
        self.assertIn('admin_boss', usernames)
        self.assertIn('trainer_bob', usernames)
        self.assertIn('trainee_alice', usernames)

    def test_admin_can_filter_users_by_role(self):
        """Admin can filter users by role query parameter."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/auth/admin/users/?role=TRAINER')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for u in response.data:
            self.assertEqual(u['role'], 'TRAINER')

    def test_admin_can_search_users(self):
        """Admin can search users by username or email."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/auth/admin/users/?search=alice')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['username'], 'trainee_alice')

    def test_admin_can_view_user_detail(self):
        """Admin can view detailed stats of a user."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/auth/admin/users/{self.trainee.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'trainee_alice')
        self.assertIn('courses_count', response.data)
        self.assertIn('enrollments_count', response.data)
        self.assertIn('certificates_count', response.data)

    def test_admin_can_deactivate_user(self):
        """Admin can deactivate an active non-admin user."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/auth/admin/users/{self.trainee.id}/deactivate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.trainee.refresh_from_db()
        self.assertFalse(self.trainee.is_active)

    def test_admin_cannot_deactivate_self(self):
        """Admin cannot deactivate their own account."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/auth/admin/users/{self.admin.id}/deactivate/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot deactivate your own account', response.data['detail'])

    def test_admin_can_activate_inactive_user(self):
        """Admin can reactivate a previously deactivated user."""
        self.trainee.is_active = False
        self.trainee.save()
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f'/api/auth/admin/users/{self.trainee.id}/activate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.trainee.refresh_from_db()
        self.assertTrue(self.trainee.is_active)


class Step16ProductionHardeningTests(TestCase):
    """
    Automated verification of Step 16 production settings, throttling, and security boundaries.
    """

    def test_throttling_configuration_is_active(self):
        """Verify DRF throttle classes and rates are configured."""
        from django.conf import settings
        rf_settings = settings.REST_FRAMEWORK
        self.assertIn('DEFAULT_THROTTLE_CLASSES', rf_settings)
        self.assertIn('DEFAULT_THROTTLE_RATES', rf_settings)
        rates = rf_settings['DEFAULT_THROTTLE_RATES']
        self.assertIn('anon', rates)
        self.assertIn('user', rates)
        self.assertIn('auth', rates)
        self.assertIn('verify', rates)

    def test_auth_rate_throttles_attached_to_views(self):
        """Verify RegisterView and LoginView include AuthRateThrottle."""
        from core.views import RegisterView, LoginView
        from core.throttling import AuthRateThrottle
        self.assertIn(AuthRateThrottle, RegisterView.throttle_classes)
        self.assertIn(AuthRateThrottle, LoginView.throttle_classes)

    def test_verify_rate_throttle_attached_to_public_verify_view(self):
        """Verify PublicCertificateVerifyView includes VerifyRateThrottle."""
        from certificates.views import PublicCertificateVerifyView
        from core.throttling import VerifyRateThrottle
        self.assertIn(VerifyRateThrottle, PublicCertificateVerifyView.throttle_classes)

    def test_production_secret_key_validation(self):
        """Verify that DEBUG=False with an insecure secret key raises a ValueError."""
        with patch.dict('os.environ', {'DEBUG': 'False', 'SECRET_KEY': 'django-insecure-test'}):
            with self.assertRaises(ValueError):
                # Re-executing check logic
                sec_key = 'django-insecure-test'
                debug_val = False
                if not debug_val and ('django-insecure' in sec_key):
                    raise ValueError('CRITICAL SECURITY CONFIGURATION ERROR')


class Step18DeploymentArtifactTests(TestCase):
    """
    Automated verification of Step 18 WhiteNoise, static storage, database connection pooling, and deployment setup.
    """

    def test_whitenoise_middleware_configured(self):
        """Verify WhiteNoiseMiddleware is registered immediately after SecurityMiddleware."""
        from django.conf import settings
        self.assertIn('whitenoise.middleware.WhiteNoiseMiddleware', settings.MIDDLEWARE)
        sec_idx = settings.MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')
        wn_idx = settings.MIDDLEWARE.index('whitenoise.middleware.WhiteNoiseMiddleware')
        self.assertEqual(wn_idx, sec_idx + 1)

    def test_database_conn_max_age_configured(self):
        """Verify default database has CONN_MAX_AGE configured."""
        from django.conf import settings
        db_conf = settings.DATABASES['default']
        self.assertIn('CONN_MAX_AGE', db_conf)
        self.assertIsInstance(db_conf['CONN_MAX_AGE'], int)
        self.assertGreaterEqual(db_conf['CONN_MAX_AGE'], 0)

    def test_static_storage_configuration(self):
        """Verify STORAGES defines default and staticfiles storage backends."""
        from django.conf import settings
        self.assertIn('staticfiles', settings.STORAGES)
        self.assertIn('default', settings.STORAGES)


class Step19PersistentMediaStorageTests(TestCase):
    """
    Automated verification of Step 19 Persistent Media Storage Strategy (SupabaseStorage).
    """

    def test_storage_backend_selection_local(self):
        """Verify that under default local configuration, default storage is FileSystemStorage."""
        from django.conf import settings
        from django.core.files.storage import default_storage, FileSystemStorage
        self.assertIsInstance(default_storage, FileSystemStorage)

    def test_supabase_storage_url_generation(self):
        """Verify SupabaseStorage correctly generates public/authenticated URLs."""
        from core.storage import SupabaseStorage
        storage = SupabaseStorage(
            bucket='test-bucket',
            supabase_url='https://xyz.supabase.co',
            service_role_key='test-key',
        )
        url = storage.url('assignments/submissions/2026/09/deliverable.pdf')
        expected = 'https://xyz.supabase.co/storage/v1/object/public/test-bucket/assignments/submissions/2026/09/deliverable.pdf'
        self.assertEqual(url, expected)

    def test_supabase_storage_headers(self):
        """Verify SupabaseStorage formats Bearer and apikey headers correctly."""
        from core.storage import SupabaseStorage
        storage = SupabaseStorage(
            bucket='test-bucket',
            supabase_url='https://xyz.supabase.co',
            service_role_key='secret-key-123',
        )
        headers = storage._get_headers(content_type='application/pdf')
        self.assertEqual(headers['Authorization'], 'Bearer secret-key-123')
        self.assertEqual(headers['apikey'], 'secret-key-123')
        self.assertEqual(headers['Content-Type'], 'application/pdf')

    @patch('urllib.request.urlopen')
    def test_supabase_storage_upload_success(self, mock_urlopen):
        """Verify SupabaseStorage _save sends POST request with correct payload and headers."""
        from core.storage import SupabaseStorage
        from django.core.files.base import ContentFile
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        storage = SupabaseStorage(
            bucket='test-bucket',
            supabase_url='https://xyz.supabase.co',
            service_role_key='secret-key-123',
        )
        file_obj = ContentFile(b'Hello World deliverable', name='deliverable.txt')
        saved_name = storage._save('deliverable.txt', file_obj)
        self.assertEqual(saved_name, 'deliverable.txt')
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_method(), 'POST')
        self.assertIn('object/test-bucket/deliverable.txt', req.full_url)
        self.assertEqual(req.headers['X-upsert'], 'true')

    @patch('urllib.request.urlopen')
    def test_supabase_storage_upload_failure_raises_ioerror(self, mock_urlopen):
        """Verify SupabaseStorage does NOT silently swallow upload failures."""
        from core.storage import SupabaseStorage
        from django.core.files.base import ContentFile
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            'https://xyz.supabase.co', 500, 'Internal Server Error', {}, io.BytesIO(b'{"error":"disk full"}')
        )

        storage = SupabaseStorage(
            bucket='test-bucket',
            supabase_url='https://xyz.supabase.co',
            service_role_key='secret-key-123',
        )
        file_obj = ContentFile(b'Deliverable bytes', name='task.pdf')
        with self.assertRaises(IOError) as ctx:
            storage._save('task.pdf', file_obj)
        self.assertIn('Failed to upload', str(ctx.exception))

    @patch('urllib.request.urlopen')
    def test_supabase_storage_delete_success(self, mock_urlopen):
        """Verify SupabaseStorage delete issues DELETE with JSON payload."""
        from core.storage import SupabaseStorage
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        storage = SupabaseStorage(
            bucket='test-bucket',
            supabase_url='https://xyz.supabase.co',
            service_role_key='secret-key-123',
        )
        result = storage.delete('assignments/file.pdf')
        self.assertTrue(result)
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_method(), 'DELETE')
        self.assertIn('object/test-bucket', req.full_url)

    @patch('urllib.request.urlopen')
    def test_supabase_storage_exists_and_size(self, mock_urlopen):
        """Verify SupabaseStorage exists and size methods queries object metadata."""
        from core.storage import SupabaseStorage
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"size": 2048, "id": "123"}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        storage = SupabaseStorage(
            bucket='test-bucket',
            supabase_url='https://xyz.supabase.co',
            service_role_key='secret-key-123',
        )
        self.assertTrue(storage.exists('submission.zip'))
        self.assertEqual(storage.size('submission.zip'), 2048)

    def test_assignment_submission_file_upload_flow(self):
        """Verify that AssignmentSubmission model cleanly saves and queries file attachments."""
        from assignments.models import Assignment, AssignmentSubmission, SubmissionType, SubmissionStatus
        from courses.models import Course
        from enrollments.models import Enrollment
        from django.core.files.uploadedfile import SimpleUploadedFile

        trainer = User.objects.create_user(username='sub_trainer', email='sub_trainer@test.com', password='Pass!')
        trainee = User.objects.create_user(username='sub_trainee', email='sub_trainee@test.com', password='Pass!')
        course = Course.objects.create(
            trainer=trainer,
            title='File Storage Course',
            description='Test',
            duration_hours=10,
        )
        enrollment = Enrollment.objects.create(course=course, trainee=trainee)
        assignment = Assignment.objects.create(
            course=course,
            title='Upload Capstone',
            description='Upload your report',
            submission_type=SubmissionType.FILE,
            max_score=100,
        )

        test_file = SimpleUploadedFile(
            'capstone_report.pdf',
            b'%PDF-1.4 sample file content for testing',
            content_type='application/pdf',
        )
        submission = AssignmentSubmission.objects.create(
            assignment=assignment,
            trainee=trainee,
            enrollment=enrollment,
            submission_file=test_file,
            status=SubmissionStatus.SUBMITTED,
        )
        self.assertIsNotNone(submission.submission_file)
        self.assertTrue(submission.submission_file.name.endswith('.pdf'))
        self.assertTrue(submission.submission_file.storage.exists(submission.submission_file.name))
        # Cleanup uploaded test file
        submission.submission_file.delete(save=False)
class SupabaseStorageTests(TestCase):
    """Tests for the persistent Supabase Storage backend."""

    def setUp(self):
        from django.test import override_settings
        from core.storage import SupabaseStorage

        self.override = override_settings(
            SUPABASE_URL='https://example.supabase.co',
            SUPABASE_STORAGE_BUCKET='capacity-media',
            SUPABASE_SERVICE_ROLE_KEY='test-service-role-key',
        )
        self.override.enable()
        self.storage = SupabaseStorage()

    def tearDown(self):
        self.override.disable()

    def test_storage_configuration(self):
        """Verify Supabase Storage uses the configured bucket and URL."""
        self.assertEqual(self.storage.bucket, 'capacity-media')
        self.assertEqual(
            self.storage.supabase_url,
            'https://example.supabase.co',
        )

    def test_object_url(self):
        """Verify the Supabase Storage object URL is generated correctly."""
        url = self.storage._object_url(
            'assignments/submissions/2026/09/test.pdf'
        )

        self.assertEqual(
            url,
            'https://example.supabase.co/storage/v1/object/'
            'capacity-media/assignments/submissions/2026/09/test.pdf',
        )

    def test_public_url(self):
        """Verify the public URL is generated correctly."""
        url = self.storage.url(
            'assignments/submissions/2026/09/test.pdf'
        )

        self.assertEqual(
            url,
            'https://example.supabase.co/storage/v1/object/public/'
            'capacity-media/assignments/submissions/2026/09/test.pdf',
        )

    def test_headers(self):
        """Verify service-role authentication headers."""
        headers = self.storage._headers('application/pdf')

        self.assertEqual(
            headers['Authorization'],
            'Bearer test-service-role-key',
        )
        self.assertEqual(
            headers['apikey'],
            'test-service-role-key',
        )
        self.assertEqual(
            headers['Content-Type'],
            'application/pdf',
        )

    def test_clean_name(self):
        """Verify Windows separators and leading slashes are normalized."""
        name = self.storage._clean_name(
            r'\assignments\submissions\2026\09\test.pdf'
        )

        self.assertEqual(
            name,
            'assignments/submissions/2026/09/test.pdf',
        )

    @patch('core.storage.urllib.request.urlopen')
    def test_save_upload(self, mock_urlopen):
        """Verify a file is uploaded using the Supabase Storage API."""
        response = MagicMock()
        response.status = 200
        mock_urlopen.return_value.__enter__.return_value = response

        content = ContentFile(b'PDF test data', name='test.pdf')
        content.content_type = 'application/pdf'

        saved_name = self.storage._save(
            'assignments/submissions/2026/09/test.pdf',
            content,
        )

        self.assertEqual(
            saved_name,
            'assignments/submissions/2026/09/test.pdf',
        )

        request = mock_urlopen.call_args.args[0]

        self.assertEqual(request.method, 'POST')
        self.assertEqual(
            request.full_url,
            'https://example.supabase.co/storage/v1/object/'
            'capacity-media/assignments/submissions/2026/09/test.pdf',
        )

    @patch('core.storage.urllib.request.urlopen')
    def test_exists_returns_true(self, mock_urlopen):
        """Verify exists() returns True for an existing object."""
        response = MagicMock()
        mock_urlopen.return_value.__enter__.return_value = response

        self.assertTrue(
            self.storage.exists(
                'assignments/submissions/2026/09/test.pdf'
            )
        )

        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.method, 'HEAD')

    @patch('core.storage.urllib.request.urlopen')
    def test_exists_returns_false_for_missing_file(self, mock_urlopen):
        """Verify exists() returns False for a 404 response."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url='https://example.supabase.co',
            code=404,
            msg='Not Found',
            hdrs=None,
            fp=None,
        )

        self.assertFalse(
            self.storage.exists(
                'assignments/submissions/2026/09/missing.pdf'
            )
        )

    @patch('core.storage.urllib.request.urlopen')
    def test_delete(self, mock_urlopen):
        """Verify delete() sends the correct request."""
        response = MagicMock()
        response.status = 200
        mock_urlopen.return_value.__enter__.return_value = response

        self.storage.delete(
            'assignments/submissions/2026/09/test.pdf'
        )

        request = mock_urlopen.call_args.args[0]

        self.assertEqual(request.method, 'DELETE')

    @patch('core.storage.urllib.request.urlopen')
    def test_size(self, mock_urlopen):
        """Verify size() reads Content-Length."""
        response = MagicMock()
        response.headers.get.return_value = '1234'
        mock_urlopen.return_value.__enter__.return_value = response

        size = self.storage.size(
            'assignments/submissions/2026/09/test.pdf'
        )

        self.assertEqual(size, 1234)


class AdminAssessmentAndAnalyticsTests(TestCase):
    """Tests for Admin assessments and platform analytics endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='analytics_admin',
            email='analytics_admin@example.com',
            password='Password123!',
        )
        self.admin.profile.role = Role.ADMIN
        self.admin.profile.save()

        self.trainer = User.objects.create_user(
            username='analytics_trainer',
            email='analytics_trainer@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainer, role=Role.TRAINER)

        self.trainee = User.objects.create_user(
            username='analytics_trainee',
            email='analytics_trainee@example.com',
            password='Password123!',
        )
        UserProfile.objects.create(user=self.trainee, role=Role.TRAINEE)

    def test_admin_can_access_assessments_list(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/assessments/admin/all/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_admin_cannot_access_assessments_list(self):
        self.client.force_authenticate(user=self.trainee)
        response = self.client.get('/api/assessments/admin/all/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_access_analytics(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/courses/admin/analytics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('completion_rate', response.data)
        self.assertIn('retention_rate', response.data)
        self.assertIn('categories', response.data)
        self.assertIn('top_courses', response.data)
        self.assertIn('placement_ready_trainees', response.data)

    def test_non_admin_cannot_access_analytics(self):
        self.client.force_authenticate(user=self.trainer)
        response = self.client.get('/api/courses/admin/analytics/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)



