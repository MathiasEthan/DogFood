from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from .models import User


class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('auth_register')
        self.login_url = reverse('auth_login')
        self.refresh_url = reverse('auth_refresh')
        self.logout_url = reverse('auth_logout')
        self.me_url = reverse('auth_me')
        self.admin_users_url = reverse('admin_user_list')

    def test_register_participant_success(self):
        data = {
            'username': 'alice_participant',
            'email': 'alice@example.com',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!',
            'role': 'participant',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['role'], 'participant')
        self.assertEqual(response.data['user']['username'], 'alice_participant')

        # Verify HttpOnly cookies
        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)
        self.assertTrue(response.cookies['access_token']['httponly'])
        self.assertTrue(response.cookies['refresh_token']['httponly'])

    def test_register_organizer_success(self):
        data = {
            'username': 'bob_organizer',
            'email': 'bob@example.com',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!',
            'role': 'organizer',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['role'], 'organizer')

    def test_register_judge_forbidden(self):
        data = {
            'username': 'carol_judge',
            'email': 'carol@example.com',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!',
            'role': 'judge',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', response.data)

    def test_register_admin_forbidden(self):
        data = {
            'username': 'dave_admin',
            'email': 'dave@example.com',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!',
            'role': 'admin',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', response.data)

    def test_login_with_username_and_email(self):
        user = User.objects.create_user(
            username='eve_user',
            email='eve@example.com',
            password='TestPassword123!',
            role='participant',
        )

        # Login via username
        res1 = self.client.post(self.login_url, {
            'username': 'eve_user',
            'password': 'TestPassword123!',
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', res1.cookies)
        self.assertEqual(res1.data['user']['role'], 'participant')

        # Login via email
        res2 = self.client.post(self.login_url, {
            'username': 'eve@example.com',
            'password': 'TestPassword123!',
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', res2.cookies)

    def test_access_me_via_cookie(self):
        user = User.objects.create_user(
            username='frank_judge',
            email='frank@example.com',
            password='TestPassword123!',
            role='judge',
        )
        login_res = self.client.post(self.login_url, {
            'username': 'frank_judge',
            'password': 'TestPassword123!',
        }, format='json')
        access_token = login_res.cookies['access_token'].value

        # Make request to /api/auth/me/ with cookie
        authed_client = APIClient()
        authed_client.cookies['access_token'] = access_token
        me_res = authed_client.get(self.me_url)
        self.assertEqual(me_res.status_code, status.HTTP_200_OK)
        self.assertEqual(me_res.data['username'], 'frank_judge')
        self.assertEqual(me_res.data['role'], 'judge')

    def test_logout_clears_cookies(self):
        User.objects.create_user(
            username='grace_user',
            email='grace@example.com',
            password='TestPassword123!',
        )
        login_res = self.client.post(self.login_url, {
            'username': 'grace_user',
            'password': 'TestPassword123!',
        }, format='json')
        refresh_token = login_res.cookies['refresh_token'].value

        client = APIClient()
        client.cookies['refresh_token'] = refresh_token
        logout_res = client.post(self.logout_url)
        self.assertEqual(logout_res.status_code, status.HTTP_200_OK)
        self.assertEqual(logout_res.cookies['access_token'].value, '')
        self.assertEqual(logout_res.cookies['refresh_token'].value, '')

    def test_admin_appoints_judge(self):
        admin_user = User.objects.create_superuser(
            username='admin_boss',
            email='admin@hackathon.local',
            password='AdminPassword123!',
        )
        candidate = User.objects.create_user(
            username='helen_candidate',
            email='helen@example.com',
            password='Password123!',
            role='participant',
        )

        appoint_url = reverse('appoint_judge', kwargs={'pk': candidate.pk})

        # Non-admin attempt fails
        user_client = APIClient()
        user_client.force_authenticate(user=candidate)
        fail_res = user_client.post(appoint_url)
        self.assertEqual(fail_res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin attempt succeeds
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)
        success_res = admin_client.post(appoint_url)
        self.assertEqual(success_res.status_code, status.HTTP_200_OK)

        candidate.refresh_from_db()
        self.assertEqual(candidate.role, User.Role.JUDGE)


class RefreshRotationTests(TestCase):
    def test_old_refresh_token_rejected_after_rotation(self):
        User.objects.create_user(username='rot', email='rot@example.com', password='TestPassword123!')
        client = APIClient()
        login = client.post(reverse('auth_login'), {'username': 'rot', 'password': 'TestPassword123!'}, format='json')
        old_refresh = login.cookies['refresh_token'].value

        c1 = APIClient()
        c1.cookies['refresh_token'] = old_refresh
        first = c1.post(reverse('auth_refresh'))
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertNotEqual(first.cookies['refresh_token'].value, old_refresh)

        c2 = APIClient()
        c2.cookies['refresh_token'] = old_refresh
        replay = c2.post(reverse('auth_refresh'))
        self.assertEqual(replay.status_code, status.HTTP_401_UNAUTHORIZED)
