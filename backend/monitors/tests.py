from django.test import TestCase
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import AdvancedMonitorConfig, Monitor


class MonitorApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner@example.com", "a-strong-password")
        self.other_user = User.objects.create_user("other@example.com", "a-strong-password")
        self.client.force_authenticate(self.user)

    def test_create_list_update_pause_resume_and_delete(self):
        response = self.client.post(
            reverse("monitor-list"),
            {
                "name": "My Website",
                "url": "https://example.com",
                "check_interval": 900,
                "timeout": 15,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        monitor_id = response.data["id"]

        detail_url = reverse("monitor-detail", args=[monitor_id])
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.patch(detail_url, {"name": "Updated"}, format="json").status_code, status.HTTP_200_OK)

        pause_url = reverse("monitor-pause", args=[monitor_id])
        self.assertEqual(self.client.post(pause_url).data["active"], False)
        resume_url = reverse("monitor-resume", args=[monitor_id])
        self.assertEqual(self.client.post(resume_url).data["active"], True)
        self.assertEqual(self.client.delete(detail_url).status_code, status.HTTP_204_NO_CONTENT)

    def test_monitor_queryset_is_owned(self):
        monitor = Monitor.objects.create(user=self.other_user, name="Private", url="https://example.com")
        detail_url = reverse("monitor-detail", args=[monitor.id])
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(detail_url, {"name": "Stolen"}, format="json").status_code, status.HTTP_404_NOT_FOUND)

    def test_non_http_url_is_rejected(self):
        response = self.client.post(
            reverse("monitor-list"),
            {"name": "Invalid", "url": "ftp://example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AdvancedMonitoringServiceTests(TestCase):
    def test_normalize_html_removes_scripts_and_normalizes_whitespace(self):
        from .services.dom_diff import normalize_html

        html = """
        <html>
            <script>alert("x")</script>
            <body>
                Hello
                <span>world</span>
            </body>
        </html>
        """

        result = normalize_html(html)

        self.assertEqual(result, "Hello world")

    def test_selector_not_found_raises(self):
        from .services.dom_diff import normalize_html

        with self.assertRaises(ValueError):
            normalize_html(
                "<html><body>Hello</body></html>",
                "#does-not-exist",
            )

    def test_content_hash_is_stable(self):
        from .services.dom_diff import content_hash

        first = content_hash("hello")
        second = content_hash("hello")

        self.assertEqual(first, second)

    def test_content_hash_changes(self):
        from .services.dom_diff import content_hash

        first = content_hash("hello")
        second = content_hash("hello world")

        self.assertNotEqual(first, second)

    def test_price_extraction_eur(self):
        from .services.price_extractor import extract_price

        html = """
        <div class="price">€19.99</div>
        """

        price, currency, raw_value = extract_price(
            html,
            ".price",
        )

        self.assertEqual(str(price), "19.99")
        self.assertEqual(currency, "EUR")
        self.assertEqual(raw_value, "€19.99")

    def test_price_extraction_explicit_currency(self):
        from .services.price_extractor import extract_price

        html = """
        <div class="price">19.99</div>
        """

        price, currency, _ = extract_price(
            html,
            ".price",
            "USD",
        )

        self.assertEqual(str(price), "19.99")
        self.assertEqual(currency, "USD")


class AdvancedMonitorConfigAPITests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(
            email="advanced@example.com",
            password="StrongPassword123!",
        )

        self.client.force_authenticate(
            user=self.user
        )

        self.monitor = Monitor.objects.create(
            user=self.user,
            name="Advanced Test",
            url="https://example.com",
            active=True,
            check_interval=3600,
            timeout=30,
        )

    def test_get_advanced_config_creates_default(self):
        response = self.client.get(
            f"/api/monitors/{self.monitor.id}/advanced/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["mode"],
            AdvancedMonitorConfig.HTTP,
        )

    def test_patch_dom_config(self):
        response = self.client.patch(
            f"/api/monitors/{self.monitor.id}/advanced/",
            {
                "mode": AdvancedMonitorConfig.DOM,
                "selector": "main",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["mode"],
            AdvancedMonitorConfig.DOM,
        )

    def test_dom_requires_selector(self):
        response = self.client.patch(
            f"/api/monitors/{self.monitor.id}/advanced/",
            {
                "mode": AdvancedMonitorConfig.DOM,
                "selector": "",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_price_requires_selector(self):
        response = self.client.patch(
            f"/api/monitors/{self.monitor.id}/advanced/",
            {
                "mode": AdvancedMonitorConfig.PRICE,
                "price_selector": "",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_diffs_endpoint(self):
        response = self.client.get(
            f"/api/monitors/{self.monitor.id}/diffs/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_prices_endpoint(self):
        response = self.client.get(
            f"/api/monitors/{self.monitor.id}/prices/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
