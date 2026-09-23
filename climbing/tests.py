from datetime import timedelta
import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ClimbSchedule, Crag, Route


class ClimberJourneyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('climber', password='safe-password-1')
        self.crag = Crag.objects.create(name='Test Wall', slug='test-wall')
        Route.objects.create(crag=self.crag, name='Practice Line', grade='4A')
        self.client.force_login(self.user)

    def test_future_climb_is_saved_and_confirmed(self):
        future = timezone.localtime(timezone.now() + timedelta(days=2))
        response = self.client.post(reverse('schedule', args=[self.crag.id]), {
            'climb_date': future.strftime('%Y-%m-%d'), 'climb_time': future.strftime('%H:%M'),
            'friends': 'Alex', 'notes': 'Bring chalk',
        })
        self.assertContains(response, 'Your climb is confirmed')
        self.assertEqual(ClimbSchedule.objects.filter(user=self.user, crag=self.crag).count(), 1)
        self.assertContains(self.client.get(reverse('profile')), 'Test Wall')

    @patch('climbing.crag_views.live_singapore_weather')
    def test_weather_endpoint_returns_live_provider_shape(self, weather):
        weather.return_value = {'location': 'Singapore', 'current': {'temperature': 30}, 'forecast': []}
        response = self.client.get(reverse('api_crag_weather', args=[self.crag.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results']['location'], 'Singapore')
        weather.assert_called_once()

    def test_reset_request_uses_a_generic_local_notice(self):
        response = self.client.post(reverse('api_password_reset'), {'email': self.user.email}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertNotIn('reset_url', response.json())

    def test_legacy_home_page_is_not_routable(self):
        self.assertEqual(self.client.get('/home/').status_code, 404)

    def test_anonymous_schedule_uses_the_project_login_and_returns_here(self):
        self.client.logout()
        schedule_url = reverse('schedule', args=[self.crag.id])
        response = self.client.get(schedule_url)
        self.assertRedirects(response, f'/login/?next={schedule_url}')

    def test_anonymous_detail_hides_ar_and_scheduling(self):
        self.client.logout()
        response = self.client.get(reverse('crag_detail', args=[self.crag.slug]))
        self.assertNotContains(response, 'onclick="openAR(', html=False)
        self.assertNotContains(response, 'Schedule a Climb Here')

    def test_admin_login_accepts_a_fresh_csrf_token(self):
        User.objects.create_superuser('presentation-admin', 'admin@example.com', 'safe-password-2')
        csrf_client = Client(enforce_csrf_checks=True)
        admin_login_url = f"{reverse('admin:login')}?next=/admin/"
        login_page = csrf_client.get(admin_login_url)
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login_page.content.decode())
        self.assertIsNotNone(match)
        response = csrf_client.post(admin_login_url, {
            'username': 'presentation-admin',
            'password': 'safe-password-2',
            'csrfmiddlewaretoken': match.group(1),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/admin/')
