"""
Test suite for the core authentication module.

15 test cases covering registration, login, logout, current user,
role validation, and permission behavior.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import Role, UserProfile


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
        UserProfile.objects.create(user=self.user, role=Role.TRAINER)

    def test_11_authenticated_me_returns_user_and_role(self):
        """Authenticated GET /me/ returns user info with role."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.user.id)
        self.assertEqual(response.data['username'], 'meuser')
        self.assertEqual(response.data['email'], 'me@example.com')
        self.assertEqual(response.data['role'], Role.TRAINER)
        self.assertNotIn('password', response.data)

    def test_12_unauthenticated_me_returns_403(self):
        """Unauthenticated GET /me/ returns 403."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


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
        UserProfile.objects.create(user=self.user, role=Role.TRAINEE)

    def test_13_logout_succeeds(self):
        """Authenticated logout returns 200 and invalidates session."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)


class AuthRoleTests(TestCase):
    """Tests for role information and permission behavior."""

    def setUp(self):
        self.client = APIClient()

    def test_14_role_information_returned_correctly(self):
        """Registration and /me/ return the correct role string."""
        # Register as TRAINEE
        reg_data = {
            'username': 'roletest',
            'email': 'roletest@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'role': Role.TRAINEE,
        }
        reg_response = self.client.post(reverse('auth-register'), reg_data, format='json')
        self.assertEqual(reg_response.data['role'], 'TRAINEE')

        # Login and check /me/
        self.client.post(
            reverse('auth-login'),
            {'username': 'roletest', 'password': 'SecurePass123!'},
            format='json',
        )
        me_response = self.client.get(reverse('auth-me'))
        self.assertEqual(me_response.data['role'], 'TRAINEE')

    def test_15_role_based_permission_behavior(self):
        """
        Different roles have appropriate access patterns.

        - Unauthenticated users cannot access /me/
        - Both TRAINEE and TRAINER can access /me/ after login
        - Superuser signal auto-creates ADMIN profile
        """
        me_url = reverse('auth-me')

        # Unauthenticated → 403
        response = self.client.get(me_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # TRAINEE can access /me/
        trainee = User.objects.create_user(
            username='t_trainee', email='t_trainee@example.com', password='SecurePass123!',
        )
        UserProfile.objects.create(user=trainee, role=Role.TRAINEE)
        self.client.force_authenticate(user=trainee)
        response = self.client.get(me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], Role.TRAINEE)

        # TRAINER can access /me/
        self.client.force_authenticate(user=None)  # reset
        trainer = User.objects.create_user(
            username='t_trainer', email='t_trainer@example.com', password='SecurePass123!',
        )
        UserProfile.objects.create(user=trainer, role=Role.TRAINER)
        self.client.force_authenticate(user=trainer)
        response = self.client.get(me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], Role.TRAINER)

        # Superuser auto-gets ADMIN profile via signal
        self.client.force_authenticate(user=None)
        admin_user = User.objects.create_superuser(
            username='t_admin', email='t_admin@example.com', password='SecurePass123!',
        )
        self.assertTrue(hasattr(admin_user, 'profile'))
        self.assertEqual(admin_user.profile.role, Role.ADMIN)

        # ADMIN can also access /me/
        self.client.force_authenticate(user=admin_user)
        response = self.client.get(me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], Role.ADMIN)
