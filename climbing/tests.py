from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ClimbSchedule, Crag


class ClimberJourneyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('climber', password='safe-password-1')
        self.crag = Crag.objects.create(name='Test Wall', slug='test-wall')
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
