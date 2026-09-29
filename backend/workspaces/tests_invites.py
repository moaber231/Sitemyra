from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Workspace, WorkspaceInvite, WorkspaceMembership


class WorkspaceInviteSecurityTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="workspace-owner@example.test", password="a-strong-password"
        )
        self.invited_user = User.objects.create_user(
            email="teammate@example.test", password="a-strong-password"
        )
        self.other_user = User.objects.create_user(
            email="other@example.test", password="a-strong-password"
        )
        self.workspace = Workspace.objects.create(
            owner=self.owner, name="North Studio"
        )
        self.invite = WorkspaceInvite.objects.create(
            workspace=self.workspace,
            email=self.invited_user.email,
            role=WorkspaceMembership.VIEWER,
            created_by=self.owner,
        )

    def test_invitation_token_listing_is_owner_admin_only(self):
        url = reverse("workspace-invites", args=[self.workspace.id])
        self.client.force_authenticate(self.owner)

        owner_response = self.client.get(url)

        self.assertEqual(owner_response.status_code, status.HTTP_200_OK)
        self.assertEqual(owner_response.data[0]["token"], self.invite.token)

        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.other_user,
            role=WorkspaceMembership.VIEWER,
        )
        self.client.force_authenticate(self.other_user)
        viewer_response = self.client.get(url)

        self.assertEqual(viewer_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(self.invite.token, str(viewer_response.data))

    def test_invitation_can_only_be_claimed_by_the_invited_email(self):
        url = reverse("workspace-accept-invite", args=[self.invite.token])
        self.client.force_authenticate(self.other_user)

        wrong_user_response = self.client.post(url)

        self.assertEqual(wrong_user_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(WorkspaceInvite.objects.get(pk=self.invite.pk).accepted)
        self.assertFalse(
            WorkspaceMembership.objects.filter(
                workspace=self.workspace, user=self.other_user
            ).exists()
        )

        self.client.force_authenticate(self.invited_user)
        invited_user_response = self.client.post(url)

        self.assertEqual(invited_user_response.status_code, status.HTTP_200_OK)
        self.assertTrue(WorkspaceInvite.objects.get(pk=self.invite.pk).accepted)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=self.workspace,
                user=self.invited_user,
                role=WorkspaceMembership.VIEWER,
            ).exists()
        )
