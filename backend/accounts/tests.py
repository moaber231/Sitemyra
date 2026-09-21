from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class AuthenticationApiTests(APITestCase):
    def test_register_login_and_me(self):
        response = self.client.post(
            reverse("register"),
            {"email": "User@Example.com", "password": "a-strong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["email"], "user@example.com")
        self.assertNotIn("password", response.data["user"])

        login = self.client.post(
            reverse("login"),
            {"email": "user@example.com", "password": "a-strong-password"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        me = self.client.get(reverse("me"))
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["email"], "user@example.com")

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user("user@example.com", "a-strong-password")
        response = self.client.post(
            reverse("register"),
            {"email": "USER@example.com", "password": "another-password"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
