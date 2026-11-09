from decimal import Decimal

from django.test import TestCase

from apps.core.testing import make_customer, make_service, make_user
from apps.jobs import services
from apps.jobs.models import Job
from apps.jobs.services import JobError
from apps.notifications.models import Notification


class JobWorkflowTests(TestCase):
    def setUp(self):
        self.manager = make_user("manager")
        self.customer, self.vehicle = make_customer(with_login=True)
        self.wash = make_service("Wash", "exterior", "500", 20)
        self.wax = make_service("Wax", "detailing", "1000", 40)

    def new_job(self, **kw):
        return services.create_job(
            customer=self.customer, vehicle=self.vehicle, services=[self.wash],
            created_by=self.manager, **kw,
        )

    def test_create_job_calculates_totals_and_queue_numbers(self):
        job = services.create_job(
            customer=self.customer, vehicle=self.vehicle, services=[self.wash, self.wax],
            created_by=self.manager, discount=Decimal("100"),
        )
        self.assertEqual(job.estimated_price, Decimal("1500"))
        self.assertEqual(job.total_price, Decimal("1400"))
        self.assertEqual(job.estimated_duration, 60)
        self.assertEqual(job.queue_number, 1)
        self.assertEqual(self.new_job().queue_number, 2)
        self.assertEqual(job.events.count(), 1)

    def test_vehicle_must_belong_to_customer(self):
        other_customer, other_vehicle = make_customer()
        with self.assertRaises(JobError):
            services.create_job(customer=self.customer, vehicle=other_vehicle, services=[self.wash])

    def test_needs_at_least_one_service(self):
        with self.assertRaises(JobError):
            services.create_job(customer=self.customer, vehicle=self.vehicle, services=[])

    def test_status_transitions_follow_the_rules(self):
        job = self.new_job()
        with self.assertRaises(JobError):  # waiting -> completed is not allowed
            services.change_status(job, "completed", self.manager)
        services.change_status(job, "in_progress", self.manager)
        self.assertIsNotNone(job.started_at)

    def test_cannot_complete_while_services_pending(self):
        job = self.new_job()
        services.change_status(job, "in_progress", self.manager)
        with self.assertRaisesMessage(JobError, "pending"):
            services.change_status(job, "completed", self.manager)

    def test_full_happy_path_notifies_customer_and_managers(self):
        job = self.new_job()
        services.change_status(job, "in_progress", self.manager)
        services.complete_service(job.job_services.get(), self.manager)
        services.change_status(job, "completed", self.manager)
        job.refresh_from_db()
        self.assertEqual(job.status, "completed")
        self.assertIsNotNone(job.completed_at)
        self.assertIsNotNone(job.actual_duration)
        self.assertTrue(Notification.objects.filter(recipient=self.customer.user, type="job_completed").exists())
        with self.assertRaises(JobError):  # finished jobs are frozen
            services.change_status(job, "in_progress", self.manager)

    def test_adding_extra_service_pauses_job_and_raises_alert(self):
        job = self.new_job()
        services.change_status(job, "in_progress", self.manager)
        services.add_service(job, self.wax, self.manager)
        job.refresh_from_db()
        self.assertEqual(job.status, "awaiting_extra")
        self.assertTrue(job.need_alert)
        self.assertEqual(job.total_price, Decimal("1500"))
        line = job.job_services.get(service=self.wax)
        services.complete_service(line, self.manager)
        job.refresh_from_db()
        self.assertFalse(job.need_alert)

    def test_same_service_cannot_be_added_twice(self):
        job = self.new_job()
        with self.assertRaises(JobError):
            services.add_service(job, self.wash, self.manager)

    def test_price_is_snapshotted(self):
        job = self.new_job()
        self.wash.price = Decimal("9999")
        self.wash.save()
        self.assertEqual(job.job_services.get().price, Decimal("500"))

    def test_worker_can_only_update_their_own_jobs(self):
        worker = make_user("worker")
        other = make_user("worker")
        job = self.new_job()
        services.assign_worker(job, worker.worker_profile, self.manager)
        line = job.job_services.get()
        with self.assertRaises(JobError):
            services.complete_service(line, other)
        services.complete_service(line, worker)  # the assigned worker may

    def test_customers_cannot_complete_services(self):
        job = self.new_job()
        with self.assertRaises(JobError):
            services.complete_service(job.job_services.get(), self.customer.user)

    def test_cancel(self):
        job = self.new_job()
        services.cancel_job(job, self.manager, "customer left")
        self.assertEqual(job.status, "cancelled")
