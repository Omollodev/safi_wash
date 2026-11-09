"""Smoke tests: every main page renders without a template or query error."""
from django.test import TestCase
from django.urls import reverse

from apps.core.testing import PASSWORD, make_customer, make_service, make_user
from apps.jobs import services as job_services


class PagesRenderTests(TestCase):
    def setUp(self):
        self.manager = make_user("manager")
        self.admin = make_user("admin")
        self.worker = make_user("worker")
        self.customer, self.vehicle = make_customer(with_login=True)
        self.wash = make_service("Wash")
        self.job = job_services.create_job(
            customer=self.customer, vehicle=self.vehicle, services=[self.wash], created_by=self.manager,
            assigned_worker=self.worker.worker_profile,
        )

    def ok(self, user, *urls):
        self.client.logout()
        if user:
            self.client.login(username=user.username, password=PASSWORD)
        for url in urls:
            with self.subTest(url=url, user=user and user.role):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_public_pages(self):
        self.ok(None, reverse("dashboard:landing"), reverse("accounts:login"), reverse("portal:signup"),
                reverse("accounts:resend_verification"))

    def test_staff_pages(self):
        job, cust, veh = self.job.pk, self.customer.pk, self.vehicle.pk
        self.ok(
            self.manager,
            reverse("dashboard:home"), reverse("dashboard:reports"), reverse("dashboard:api_stats"),
            reverse("jobs:list"), reverse("jobs:list") + "?status=waiting&q=K0", reverse("jobs:create"),
            reverse("jobs:detail", args=[job]), reverse("jobs:edit", args=[job]), reverse("jobs:print", args=[job]),
            reverse("jobs:api_board"), reverse("jobs:api_alerts"), reverse("jobs:api_detail", args=[job]),
            reverse("jobs:api_timeline", args=[job]),
            reverse("customers:list"), reverse("customers:detail", args=[cust]), reverse("customers:create"),
            reverse("customers:edit", args=[cust]), reverse("customers:vehicle_create", args=[cust]),
            reverse("customers:vehicle_edit", args=[veh]), reverse("customers:vehicle_detail", args=[veh]),
            reverse("customers:quick_add"), reverse("customers:api_customers") + "?q=Cust",
            reverse("customers:api_vehicles") + "?q=K0", reverse("customers:api_customer_vehicles", args=[cust]),
            reverse("catalog:list"), reverse("catalog:create"), reverse("catalog:edit", args=[self.wash.pk]),
            reverse("catalog:api_list"),
            reverse("workforce:list"), reverse("workforce:detail", args=[self.worker.worker_profile.pk]),
            reverse("workforce:edit", args=[self.worker.worker_profile.pk]), reverse("workforce:api_available"),
            reverse("notifications:list"), reverse("notifications:api"),
            reverse("accounts:profile"), reverse("accounts:change_password"),
        )

    def test_admin_pages(self):
        self.ok(self.admin, reverse("accounts:user_list"), reverse("accounts:user_create"),
                reverse("accounts:user_edit", args=[self.worker.pk]))

    def test_worker_pages(self):
        self.ok(self.worker, reverse("workforce:my_jobs"), reverse("jobs:list"), reverse("jobs:detail", args=[self.job.pk]))

    def test_customer_pages(self):
        self.ok(
            self.customer.user,
            reverse("portal:home"), reverse("portal:profile"), reverse("portal:vehicle_add"), reverse("portal:book"),
            reverse("portal:job_detail", args=[self.job.pk]),
        )

    def test_home_redirects_by_role(self):
        for user, target in [(self.worker, "workforce:my_jobs"), (self.customer.user, "portal:home")]:
            self.client.login(username=user.username, password=PASSWORD)
            self.assertRedirects(self.client.get(reverse("dashboard:home")), reverse(target))
            self.client.logout()

    def test_end_to_end_through_the_browser_flow(self):
        """Create job via the form, work it, take payment, check the customer sees it all."""
        self.client.login(username=self.manager.username, password=PASSWORD)
        res = self.client.post(reverse("jobs:create"), {
            "vehicle": self.vehicle.pk, "services": [self.wash.pk], "priority": "high", "discount": "0",
            "auto_assign": "on",
        })
        job = self.vehicle.jobs.latest("id")
        self.assertRedirects(res, reverse("jobs:detail", args=[job.pk]))
        self.assertIsNotNone(job.assigned_worker)  # auto-assigned
        self.client.post(reverse("jobs:change_status", args=[job.pk]), {"status": "in_progress"})
        line = job.job_services.get()
        self.client.post(reverse("jobs:service_complete", args=[job.pk, line.pk]), {"notes": "shiny"})
        self.client.post(reverse("jobs:change_status", args=[job.pk]), {"status": "completed"})
        self.client.post(reverse("payments:cash", args=[job.pk]), {"amount": "500"})
        job.refresh_from_db()
        self.assertEqual((job.status, job.payment_status), ("completed", "paid"))
        self.client.logout()
        self.client.login(username=self.customer.user.username, password=PASSWORD)
        self.assertContains(self.client.get(reverse("portal:job_detail", args=[job.pk])), "Paid")

    def test_error_pages(self):
        self.client.login(username=self.customer.user.username, password=PASSWORD)
        self.assertEqual(self.client.get(reverse("customers:list")).status_code, 403)
