"""Live notification toasts: the API feeds static/js/toast.js; the page loads it only for signed-in users."""
from django.test import TestCase
from django.urls import reverse

from apps.core.testing import PASSWORD, make_customer, make_service, make_user
from apps.jobs import services as job_services
from apps.notifications.models import Notification
from apps.notifications.services import notify


class ToastApiTests(TestCase):
    def setUp(self):
        self.manager = make_user("manager")
        self.customer, self.vehicle = make_customer(with_login=True)
        self.job = job_services.create_job(
            customer=self.customer, vehicle=self.vehicle, services=[make_service()], created_by=self.manager
        )

    def login(self, user):
        self.client.login(username=user.username, password=PASSWORD)

    def test_api_links_staff_to_job_page_and_customers_to_portal_page(self):
        notify(self.manager, "info", "Hello", "Staff message", job=self.job)
        notify(self.customer.user, "info", "Hi", "Customer message", job=self.job)
        self.login(self.manager)
        staff = self.client.get(reverse("notifications:api")).json()["results"]
        self.assertIn(reverse("jobs:detail", args=[self.job.pk]), [n["url"] for n in staff])
        self.client.logout()
        self.login(self.customer.user)
        customer = self.client.get(reverse("notifications:api")).json()["results"]
        self.assertEqual({n["url"] for n in customer}, {reverse("portal:job_detail", args=[self.job.pk])})

    def test_notification_without_job_links_to_the_list(self):
        notify(self.manager, "info", "General", "No job attached")
        self.login(self.manager)
        item = self.client.get(reverse("notifications:api")).json()["results"][0]
        self.assertEqual(item["url"], reverse("notifications:list"))

    def test_api_only_returns_own_notifications(self):
        notify(self.customer.user, "info", "Private", "Only for the customer")
        self.login(self.manager)
        titles = [n["title"] for n in self.client.get(reverse("notifications:api")).json()["results"]]
        self.assertNotIn("Private", titles)

    def test_api_requires_login(self):
        self.assertEqual(self.client.get(reverse("notifications:api")).status_code, 302)

    def test_toast_script_only_loads_when_signed_in(self):
        self.assertNotContains(self.client.get(reverse("accounts:login")), "js/toast.js")
        self.login(self.manager)
        self.assertContains(self.client.get(reverse("dashboard:home")), "js/toast.js")

    def test_every_notification_type_has_a_bootstrap_icon(self):
        for value, _ in Notification.Type.choices:
            self.assertRegex(Notification(type=value).icon, r"^bi-[a-z0-9-]+$")
