"""Staff dashboard: every number comes from real records, and nothing is invented for an empty shop."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.testing import PASSWORD, make_customer, make_service, make_user
from apps.dashboard import selectors
from apps.jobs import services as job_services
from apps.payments import services as payment_services
from apps.payments.models import Payment


class TrendTests(TestCase):
    def test_no_trend_without_a_yesterday_figure(self):
        self.assertIsNone(selectors._trend(5, 0))

    def test_up_down_and_flat(self):
        self.assertEqual(selectors._trend(150, 100), {"direction": "up", "pct": 50})
        self.assertEqual(selectors._trend(50, 100), {"direction": "down", "pct": 50})
        self.assertEqual(selectors._trend(100, 100), {"direction": "flat", "pct": 0})
        self.assertEqual(selectors._trend(Decimal("75"), Decimal("100")), {"direction": "down", "pct": 25})


class EmptyShopTests(TestCase):
    """A brand-new install must show honest empty states, not fake figures."""

    def setUp(self):
        self.admin = make_user("admin")
        self.client.login(username=self.admin.username, password=PASSWORD)
        self.html = self.client.get(reverse("dashboard:home")).content.decode()

    def test_headline_cards_are_zero_with_plain_hints(self):
        self.assertIn("The queue is clear", self.html)
        self.assertIn("No jobs finished yet today", self.html)
        self.assertIn("No payments yet today", self.html)

    def test_no_trend_is_shown(self):
        self.assertNotIn("vs yesterday", self.html)
        self.assertNotIn("trend--", self.html)

    def test_sections_show_empty_states(self):
        for text in ("No payments in this period", "Nothing has happened yet", "No payments recorded yet"):
            self.assertIn(text, self.html)

    def test_page_has_the_search_box_refresh_button_and_labels(self):
        self.assertIn('role="search"', self.html)
        self.assertIn('aria-label="Refresh the job board now"', self.html)
        self.assertIn('id="board-data"', self.html)
        self.assertIn("Walk-in", self.html)
        self.assertIn("New job", self.html)


class DashboardDataTests(TestCase):
    def setUp(self):
        self.manager = make_user("manager")
        self.worker = make_user("worker")
        self.idle = make_user("worker")
        self.customer, self.vehicle = make_customer()
        self.wash = make_service("Wash", price="500")
        self.vac = make_service("Vacuum", category="interior", price="300")
        self.job = job_services.create_job(
            customer=self.customer, vehicle=self.vehicle, services=[self.wash, self.vac],
            created_by=self.manager, assigned_worker=self.worker.worker_profile,
        )

    def pay(self, amount, when=None):
        p = payment_services.record_cash_payment(self.job, amount, self.manager)
        if when:
            Payment.objects.filter(pk=p.pk).update(created_at=when)
        return p

    def test_board_payload_has_everything_a_card_shows(self):
        card = selectors.job_selectors.board_payload()["waiting"][0]
        self.assertEqual(card["plate"], self.vehicle.plate_number)
        self.assertEqual(card["customer"], self.customer.name)
        self.assertEqual(card["worker"], self.worker.worker_profile.name)
        self.assertEqual(card["service_summary"], "Wash +1")
        self.assertEqual(card["services"], ["Wash", "Vacuum"])
        self.assertEqual(card["status_display"], "Waiting")
        self.assertIsNone(card["started_at"])
        self.assertEqual(card["total_display"], "KES 800.00")
        self.assertTrue(card["created_at"])

    def test_started_time_appears_once_work_begins(self):
        job_services.change_status(self.job, "in_progress", self.manager)
        card = selectors.job_selectors.board_payload()["in_progress"][0]
        self.assertTrue(card["started_at"])

    def test_api_board_keeps_its_old_keys(self):
        self.client.login(username=self.manager.username, password=PASSWORD)
        card = self.client.get(reverse("jobs:api_board")).json()["board"]["waiting"][0]
        for key in ("id", "queue", "plate", "customer", "priority", "need_alert", "worker"):
            self.assertIn(key, card)

    def test_revenue_series_sums_per_day_and_counts_refunds(self):
        self.pay(500)
        self.pay(100, when=timezone.now() - timedelta(days=2))
        payment_services.record_refund(self.job, 50, self.manager)  # today: 500 - 50
        series = selectors.revenue_series(7)
        self.assertEqual(len(series["points"]), 7)
        self.assertEqual(series["points"][-1]["value"], Decimal("450"))
        self.assertEqual(series["points"][-3]["value"], Decimal("100"))
        self.assertEqual(series["total"], Decimal("550"))
        self.assertTrue(series["has_data"])
        self.assertTrue(series["points"][-1]["is_today"])
        self.assertEqual(series["points"][0]["value"], 0)  # a quiet day is a real zero

    def test_revenue_range_only_allows_7_or_30(self):
        self.assertEqual(selectors.revenue_series(30)["days"], 30)
        self.assertEqual(selectors.revenue_series(99)["days"], 7)
        self.client.login(username=self.manager.username, password=PASSWORD)
        html = self.client.get(reverse("dashboard:home") + "?range=abc").content.decode()
        self.assertIn('aria-current="true" class="is-active">7 days', html)
        html = self.client.get(reverse("dashboard:home") + "?range=30").content.decode()
        self.assertIn('aria-current="true" class="is-active">30 days', html)

    def test_collected_trend_only_when_yesterday_had_payments(self):
        self.pay(200)
        self.assertIsNone(selectors.kpis()["collected_trend"])
        self.pay(300, when=timezone.now() - timedelta(days=1))
        trend = selectors.kpis()["collected_trend"]
        self.assertEqual(trend, {"direction": "down", "pct": 33})  # 200 today vs 300 yesterday

    def test_worker_status_busy_available_off(self):
        job_services.change_status(self.job, "in_progress", self.manager)
        off = make_user("worker")
        off.worker_profile.is_available = False
        off.worker_profile.save()
        rows = {r["worker"].pk: r for r in selectors.worker_status()["rows"]}
        self.assertEqual(rows[self.worker.worker_profile.pk]["state"], "busy")
        self.assertEqual(rows[self.worker.worker_profile.pk]["job"].pk, self.job.pk)
        self.assertEqual(rows[self.idle.worker_profile.pk]["state"], "available")
        self.assertEqual(rows[off.worker_profile.pk]["state"], "off")

    def test_recent_activity_and_transactions_render_on_the_page(self):
        self.pay(500)
        self.client.login(username=self.manager.username, password=PASSWORD)
        html = self.client.get(reverse("dashboard:home")).content.decode()
        self.assertIn("Cash payment recorded", html)
        self.assertIn(self.vehicle.plate_number, html)
        self.assertIn("KES 500.00", html)
        self.assertIn("From 1 payment", html)
        self.assertIn("Revenue collected", html)
        self.assertIn("<svg", html)

    def test_kpi_hints_use_real_data(self):
        cards = {c["stat"]: c for c in selectors.kpi_cards(selectors.kpis())}
        self.assertEqual(cards["waiting"]["value"], 1)
        self.assertTrue(cards["waiting"]["hint"].startswith("Longest wait"))
        self.assertEqual(cards["in_progress"]["hint"], "0 of 2 workers busy")
        self.assertEqual(cards["collected_today"]["value"], "KES 0.00")


class ActivityWordingTests(TestCase):
    def test_status_codes_are_turned_into_plain_words(self):
        self.assertEqual(
            selectors._readable("Status changed from in_progress to awaiting_extra"),
            "Status changed from in progress to awaiting extra services",
        )
        self.assertEqual(selectors._readable("Job created (queue #3)"), "Job created (queue #3)")
