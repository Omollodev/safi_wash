# Safi Wash

A car wash & detailing management system built with **Django + Bootstrap 5**, designed to be **read, run and learned from by students**.

> ⭐ This is a community project. If it helps you, please **star the repo** and share it with other students and developers. Contributions are welcome!

## What it does

| Role | Can do |
|------|--------|
| **Customer** | Sign up (email-verified), add vehicles, book a wash, track progress, pay with M-Pesa |
| **Worker** | See assigned jobs, tick off services (with photo + notes), move jobs through the workflow |
| **Manager** | Create jobs (incl. walk-ins), assign workers, add extra services, take cash, refund, print job cards, view reports |
| **Admin** | Everything above + manage users |

Highlights: job workflow with enforced rules, live job board, extra-service alerts, per-job timeline, payment ledger, M-Pesa STK Push (with a safe *fake mode*), optional SMS, in-app notifications, reports.

## Quick start (5 minutes)

```bash
https://github.com/Omollodev/safi_wash.git && cd safi_wash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # defaults work as-is for local use
python manage.py migrate
python manage.py seed_demo --sample-photos              # sample services, one user per role, placeholder gallery photos
python manage.py runserver
```

Open http://127.0.0.1:8000. `seed_demo` prints a random password **once**; log in as `admin_demo`, `manager_demo`, `worker_demo` or `customer_demo`.

### Landing page & gallery
The public home page (`/`) shows your services (grouped into tabs, straight from the catalog), a photo gallery and real stats.
- **Default hero photo:** `static/img/hero.webp` is shown until you feature a photo of your own. `seed_demo --sample-photos` loads it as the featured gallery photo.
- **Add your own photos:** open `/admin/` -> *Gallery photos* -> add (max 5 MB each). Tick *Is featured* for the big hero photo; use *Display order* to arrange the rest. Delete the `Sample:` placeholders.
- **Business details** (name, phone, address, hours) come from `BUSINESS_NAME`, `BUSINESS_PHONE`, `BUSINESS_ADDRESS`, `BUSINESS_HOURS` in `.env`.
- Only `/media/gallery/` is public. Job photos of customers' cars are served through a permission-checked view.
Verification emails print in the terminal running `runserver`.

Run the tests: `python manage.py test`

Prefer shortcuts? `make install env migrate seed run` does the same. Run `make help` to see every command.

## Project layout

```
config/          settings (base/dev/prod), root urls
apps/
  core/          shared helpers: role permissions, form styling, template tags ({% icon %}) and filters
  accounts/      User model (roles), login, email verification, user admin
  customers/     Customer + Vehicle
  catalog/       Service catalogue (prices, categories)
  workforce/     Worker profiles, availability, auto-assignment
  jobs/          Job, JobService, JobEvent  <- the heart of the system
  payments/      Payment ledger, M-Pesa STK Push, callbacks
  notifications/ In-app notifications (+ optional SMS)
  portal/        Customer self-service screens
  dashboard/     Landing page, staff dashboard, reports
templates/  static/
```

New to the codebase? Read **[ARCHITECTURE.md](ARCHITECTURE.md)** first, then `apps/jobs/services.py` and `apps/jobs/tests/test_services.py`.

## M-Pesa

`MPESA_MODE=fake` (default) simulates payments with a button on the customer's job page, so you can build and demo the full flow without credentials.
For the real Daraja sandbox set `MPESA_MODE=sandbox` plus the `MPESA_*` values in `.env` (see `.env.example`). Safaricom must reach your callback URL, so use a public HTTPS URL (e.g. a tunnel) as `MPESA_CALLBACK_BASE_URL`.

## Security (and a student exercise)

Built-in protections: role checks in one file, ownership-scoped customer queries (no IDOR), POST-only state changes, CSRF everywhere except the token-protected M-Pesa callback, safe `next` redirects, signed email-verification links, no secrets in code, production settings that refuse to start without a real `DJANGO_SECRET_KEY`.
The tests in `apps/accounts/tests/test_security.py` document each one. **Exercise:** try to break them, then add a test for what you find.

## Docker

| Goal | Command | Compose file |
|------|---------|--------------|
| **Develop** (live reload + PostgreSQL) | `make docker-dev` | `docker-compose.yml` + `docker-compose.dev.yml` |
| **Test** (throw-away PostgreSQL, nothing kept) | `make docker-test` | `docker-compose.test.yml` |
| **Security tools in containers** | `make docker-security` | `docker-compose.test.yml` |
| **Production-style** | `make docker-up` | `docker-compose.yml` |

Production-style start:

```bash
cp .env.example .env     # set DJANGO_SECRET_KEY, POSTGRES_PASSWORD, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS
docker compose up -d --build
```

Put an HTTPS reverse proxy or your host's load balancer in front (it must send `X-Forwarded-Proto`). To try the production containers on plain `http://localhost`, set `SECURE_SSL_REDIRECT=False` in `.env` (never on the internet).
The container image uses a multi-stage build, runs as an unprivileged user, has a read-only filesystem with all Linux capabilities dropped, and keeps the database on an internal network with no published port. `.env` is excluded from the image by `.dockerignore`.

## DevSecOps: security is checked at every step

| Stage | What | Tool | Where it runs |
|-------|------|------|---------------|
| Secrets | Leaked keys/passwords, **whole git history** | gitleaks | `make gitleaks`, `security.yml`, weekly |
| Code (SAST) | Insecure Python patterns | bandit | `make bandit`, `security.yml` |
| Dependencies (SCA) | Known CVEs in `requirements.txt` | pip-audit, dependency-review, Dependabot | `make audit`, `security.yml` |
| Container | Dockerfile lint, image CVEs, misconfigurations | hadolint, trivy | `make docker-lint docker-scan`, `security.yml` |
| Config | Django production checklist | `check --deploy` | `ci.yml` |
| Tests | Role access, IDOR, payments, workflow (on SQLite **and** PostgreSQL) | Django tests | `make test docker-test`, `ci.yml` |

Run everything locally: `make security`. Tool versions are pinned in the `Makefile` and the workflows.
**If gitleaks ever reports a real secret: rotate it first, then remove it.** Deleting it from the latest commit does not remove it from git history.

## Deploying

Set `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and `DATABASE_URL`, then use the Docker image above, or without Docker:
`DJANGO_SETTINGS_MODULE=config.settings.prod`, then `python manage.py collectstatic --noinput && python manage.py migrate && gunicorn config.wsgi -c gunicorn.conf.py`.
Uploaded photos use the `media` volume; use object storage on hosts with ephemeral disks.

## License

MIT — see [LICENSE](LICENSE).


## Live notifications
Signed-in users get a white pop-up card in the corner when something new happens (a job assigned, an extra service, a payment). The browser checks for new notifications every 8 seconds (paused while the tab is hidden), the card fades after 7 seconds, and hovering over it pauses the timer. Change the timing in `templates/base.html` (`pollMs`, `toastMs`). The code is in `static/js/toast.js`.
