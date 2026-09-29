from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Monitor, MonitorCheck


class ComplianceReportPdfTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="compliance-owner@example.test", password="a-strong-password"
        )
        self.client.force_authenticate(self.user)
        self.monitor = Monitor.objects.create(
            user=self.user,
            name="Example product page",
            url="https://example.test/pricing?token=PRIVATE_QUERY_MARKER",
            check_interval=3600,
            timeout=15,
        )

    def download(self):
        return self.client.get(
            reverse("monitor-compliance-export"), {"type": "pdf"}
        )

    def render_pdf(self, rows):
        """Render rows through the real PDF renderer and capture drawn text.

        Asserting on the raw PDF bytes is not reliable: reportlab compresses
        the content stream, so text is not readable from the file. Recording
        what was drawn is what the reader actually sees.
        """
        from reportlab.pdfgen import canvas as reportlab_canvas

        from .views import _pdf_response

        drawn = []
        original_canvas = reportlab_canvas.Canvas

        class RecordingCanvas(original_canvas):
            def drawString(self, x, y, text, *args, **kwargs):
                drawn.append(str(text))
                return super().drawString(x, y, text, *args, **kwargs)

        with patch("reportlab.pdfgen.canvas.Canvas", RecordingCanvas):
            response = _pdf_response(rows)
        return response, "\n".join(drawn)

    def download_with_drawn_text(self):
        from reportlab.pdfgen import canvas as reportlab_canvas

        drawn = []
        original_canvas = reportlab_canvas.Canvas

        class RecordingCanvas(original_canvas):
            def drawString(self, x, y, text, *args, **kwargs):
                drawn.append(str(text))
                return super().drawString(x, y, text, *args, **kwargs)

        with patch("reportlab.pdfgen.canvas.Canvas", RecordingCanvas):
            response = self.download()
        return response, "\n".join(drawn)

    def test_no_checks_are_not_reported_as_perfect_availability(self):
        response, text = self.download_with_drawn_text()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("Sitemyra Monitoring Compliance Report", text)
        self.assertIn("No checks have completed", text)
        self.assertNotIn("100.0%", text)

    def test_pdf_uses_clear_labels_and_omits_raw_errors_and_query_values(self):
        checked_at = timezone.now()
        MonitorCheck.objects.create(
            monitor=self.monitor,
            checked_at=checked_at,
            status_code=500,
            response_time_ms=311,
            content_hash="a" * 64,
            error="INTERNAL_TRACE_PRIVATE_MARKER",
        )
        self.monitor.last_checked_at = checked_at
        self.monitor.last_status_code = 500
        self.monitor.save(update_fields=["last_checked_at", "last_status_code"])

        response, text = self.download_with_drawn_text()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Availability: 0.0% across 1 checks", text)
        self.assertIn("SLA target (99.9%): Not met", text)
        self.assertIn("Failed checks: 1", text)
        self.assertIn("Average response: 311.0 ms", text)
        self.assertIn("example.test", text)
        self.assertNotIn("/pricing", text)
        self.assertNotIn("PRIVATE_QUERY_MARKER", text)
        self.assertNotIn("INTERNAL_TRACE_PRIVATE_MARKER", text)
        self.assertNotIn("chg=", text)

    def test_renderer_never_leaks_a_full_url_even_if_a_caller_passes_one(self):
        # The view reduces rows to the host, but the renderer must be safe on
        # its own so a future caller cannot leak paths, queries, or tokens.
        response, text = self.render_pdf(
            [
                {
                    "monitor": "Direct renderer call",
                    "url": "https://example.test/pricing?token=PRIVATE_QUERY_MARKER",
                    "status": "healthy",
                    "total_checks": 1,
                    "failures": 0,
                    "changes": 0,
                    "uptime_pct": 100.0,
                    "sla_met": "Met",
                    "avg_latency_ms": 120,
                    "outage_count": 0,
                    "last_outage_at": "",
                    "last_error": "",
                    "last_checked": "",
                    "last_changed": "",
                    "outages": [],
                }
            ]
        )

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("Website: example.test", text)
        self.assertNotIn("/pricing", text)
        self.assertNotIn("PRIVATE_QUERY_MARKER", text)

    def test_site_label_is_idempotent_and_never_returns_a_path(self):
        from .views import _compliance_site_label

        full = "https://user:SECRET@Example.test:8443/pricing?token=PRIVATE"
        once = _compliance_site_label(full)

        # Hostnames are lower-cased by the URL parser.
        self.assertEqual(once, "example.test:8443")
        # Re-sanitising already-reduced rows must not lose the host.
        self.assertEqual(_compliance_site_label(once), once)
        self.assertEqual(_compliance_site_label(""), "Website unavailable")
        self.assertEqual(_compliance_site_label(None), "Website unavailable")

    def test_csv_omits_private_query_values_and_raw_exception_text(self):
        MonitorCheck.objects.create(
            monitor=self.monitor,
            checked_at=timezone.now(),
            status_code=500,
            response_time_ms=311,
            content_hash="a" * 64,
            error="INTERNAL_TRACE_PRIVATE_MARKER",
        )

        response = self.client.get(
            reverse("monitor-compliance-export"), {"type": "csv"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b"example.test", response.content)
        self.assertNotIn(b"/pricing", response.content)
        self.assertIn(b"Request failed; review the monitor for details.", response.content)
        self.assertNotIn(b"PRIVATE_QUERY_MARKER", response.content)
        self.assertNotIn(b"INTERNAL_TRACE_PRIVATE_MARKER", response.content)
