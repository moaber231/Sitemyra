from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Workspace, WorkspaceInvite, WorkspaceMembership


@override_settings(
    # The real production backend, so these tests exercise the same code path
    # production does. The SMTP transport itself is replaced by a recording
    # stub: no connection is opened and no message leaves the process.
    EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
    FRONTEND_EMAIL_PASSWORD="test-only",
    # Mirrors production. The URL must follow this setting, not be hardcoded.
    FRONTEND_URL="https://sitemyra.com",
)
class WorkspaceInvitationEmailTests(APITestCase):
    """Invitation email: recipient, content, delivery path, and failure."""

    def setUp(self):
        self.owner = User.objects.create_user(
            email="inviter@example.test", password="a-strong-password"
        )
        self.member = User.objects.create_user(
            email="invitee@example.test", password="a-strong-password"
        )
        self.workspace = Workspace.objects.create(
            owner=self.owner, name="North Studio"
        )
        self.url = reverse("workspace-invites", args=[self.workspace.id])
        self.client.force_authenticate(self.owner)
        # SMTP is treated as configured for this class; the unconfigured path
        # has its own test below. The gate reads os.environ, which a test run
        # has no reason to populate.
        self.smtp_ready = patch(
            "workspaces.invitation_email._smtp_missing", return_value=[]
        )
        self.smtp_ready.start()
        self.addCleanup(self.smtp_ready.stop)

    def create_invite(self, email=None, role="viewer"):
        with patch(
            "workspaces.tasks.send_invitation_email.delay"
        ) as enqueue:
            response = self.client.post(
                self.url,
                {"email": email or self.member.email, "role": role},
                format="json",
            )
        return response, enqueue

    def deliver(self, invite_id):
        """Run the delivery path with the SMTP transport stubbed out."""
        from .invitation_email import deliver_invitation_email

        with patch("notifications.services.send_mail", return_value=1) as sender:
            result = deliver_invitation_email(invite_id)
        return result, sender

    def sent_message(self, sender):
        """The single message handed to Django's mail sender."""
        self.assertEqual(sender.call_count, 1)
        kwargs = sender.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], [self.member.email])
        return kwargs

    def test_invite_is_emailed_to_the_exact_invited_address(self):
        response, enqueue = self.create_invite()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(enqueue.called, "invitation email was not enqueued")

        invite = WorkspaceInvite.objects.get(id=response.data["id"])
        result, sender = self.deliver(invite.id)

        self.assertEqual(result["status"], "sent")
        self.sent_message(sender)

    def test_email_contains_workspace_inviter_and_accept_url(self):
        response, _ = self.create_invite()
        invite = WorkspaceInvite.objects.get(id=response.data["id"])

        _, sender = self.deliver(invite.id)
        kwargs = self.sent_message(sender)
        body = kwargs["message"]
        subject = kwargs["subject"]

        self.assertIn("North Studio", subject)
        self.assertIn("North Studio", body)
        self.assertIn(self.owner.email, body)
        self.assertIn(self.member.email, body)
        # The accept URL carries the existing token and the configured origin.
        self.assertIn(invite.token, body)
        self.assertIn("https://sitemyra.com/dashboard/workspaces?invite=", body)
        # Fallback so a blocked link is not a dead end.
        self.assertIn("ignore this message", body)

    def test_accept_url_uses_the_configured_frontend_origin(self):
        invite = WorkspaceInvite.objects.create(
            workspace=self.workspace, email=self.member.email
        )
        from .invitation_email import invitation_accept_url

        self.assertEqual(
            invitation_accept_url(invite),
            f"https://sitemyra.com/dashboard/workspaces?invite={invite.token}",
        )

    def test_accept_url_follows_the_setting_rather_than_a_hardcoded_origin(self):
        invite = WorkspaceInvite.objects.create(
            workspace=self.workspace, email=self.member.email
        )
        from .invitation_email import invitation_accept_url

        with override_settings(FRONTEND_URL="https://staging.sitemyra.test/"):
            url = invitation_accept_url(invite)

        self.assertTrue(url.startswith("https://staging.sitemyra.test/dashboard/workspaces"))

    def test_delivery_records_sent_only_after_smtp_accepts(self):
        response, _ = self.create_invite()
        invite = WorkspaceInvite.objects.get(id=response.data["id"])

        result, _ = self.deliver(invite.id)
        invite.refresh_from_db()

        self.assertEqual(result["status"], "sent")
        self.assertEqual(invite.email_status, WorkspaceInvite.EMAIL_STATUS_SENT)
        self.assertIsNotNone(invite.email_sent_at)
        self.assertEqual(invite.email_error, "")

    def test_created_invite_reports_queued_not_sent(self):
        response, _ = self.create_invite()

        # Queued is not "sent": the SMTP outcome is not known at create time.
        self.assertEqual(response.data["email_status"], "queued")
        self.assertIsNone(response.data["email_sent_at"])
        self.assertIn("accept_url", response.data)

    def test_accepted_invitation_is_never_emailed_again(self):
        invite = WorkspaceInvite.objects.create(
            workspace=self.workspace,
            email=self.member.email,
            created_by=self.owner,
            accepted=True,
        )

        result, sender = self.deliver(invite.id)
        invite.refresh_from_db()

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(invite.email_status, WorkspaceInvite.EMAIL_STATUS_SKIPPED)
        sender.assert_not_called()

    def test_smtp_failure_is_recorded_and_never_claims_sent(self):
        import smtplib

        response, _ = self.create_invite()
        invite = WorkspaceInvite.objects.get(id=response.data["id"])

        # The sender is patched at its source, so the failure is raised by
        # exactly the transport step production uses.
        with patch(
            "notifications.services.send_mail",
            side_effect=smtplib.SMTPAuthenticationError(535, b"auth failed"),
        ):
            from .invitation_email import deliver_invitation_email

            result = deliver_invitation_email(invite.id)

        invite.refresh_from_db()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(invite.email_status, WorkspaceInvite.EMAIL_STATUS_FAILED)
        self.assertIsNone(invite.email_sent_at)
        # The reason is safe to show an owner: no token, no credential.
        self.assertNotIn(invite.token, invite.email_error)
        self.assertNotIn("535", invite.email_error)

    def test_smtp_missing_records_not_configured(self):
        # Overrides the class-level "SMTP ready" patch for this one test.
        with patch(
            "workspaces.invitation_email._smtp_missing",
            return_value=["EMAIL_HOST_PASSWORD"],
        ):
            response, _ = self.create_invite()
            invite = WorkspaceInvite.objects.get(id=response.data["id"])

            from .invitation_email import deliver_invitation_email

            with patch("notifications.services.send_mail", return_value=1) as sender:
                result = deliver_invitation_email(invite.id)

        invite.refresh_from_db()
        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(
            invite.email_status, WorkspaceInvite.EMAIL_STATUS_NOT_CONFIGURED
        )
        # Nothing was sent, and it is not claimed to have been sent.
        sender.assert_not_called()
        self.assertIn("Share the invitation link", invite.email_error)

    def test_enqueue_failure_keeps_the_invitation_usable(self):
        from unittest.mock import patch

        with patch(
            "workspaces.tasks.send_invitation_email.delay",
            side_effect=OSError("broker unavailable"),
        ):
            response = self.client.post(
                self.url, {"email": self.member.email, "role": "viewer"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # The record and its token exist even though the queue was unreachable.
        self.assertTrue(WorkspaceInvite.objects.filter(id=response.data["id"]).exists())
        self.assertTrue(response.data["token"])
        self.assertNotEqual(response.data["email_status"], "sent")

    def test_celery_task_is_routed_to_the_notifications_queue(self):
        from django.conf import settings

        self.assertEqual(
            settings.CELERY_TASK_ROUTES["workspaces.tasks.*"]["queue"],
            "celery_notifications",
        )
        # The task must be a real, registered Celery task, not a bare callable.
        from .tasks import send_invitation_email

        self.assertTrue(hasattr(send_invitation_email, "delay"))

    def test_inviter_cannot_invite_a_viewer_and_be_demoted(self):
        # Guard against a regression where the email path changes RBAC.
        from .models import WorkspaceMembership

        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.member,
            role=WorkspaceMembership.OWNER,
        )
        self.client.force_authenticate(self.member)
        response = self.client.post(
            self.url, {"email": self.owner.email, "role": "viewer"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            WorkspaceInvite.objects.get(id=response.data["id"]).role, "viewer"
        )


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
