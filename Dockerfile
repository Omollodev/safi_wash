# syntax=docker/dockerfile:1.7
# Multi-stage build: small final image, no build tools, runs as an unprivileged user.

ARG PYTHON_VERSION=3.13

# ---------------------------------------------------------------- base
FROM python:${PYTHON_VERSION}-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# ---------------------------------------------------------------- builder: install dependencies
FROM base AS builder
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------------------------------------------------------------- runtime: what production runs
FROM base AS runtime
RUN groupadd --system --gid 10001 app \
 && useradd  --system --uid 10001 --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# pip bundles its own copies of msgpack, urllib3 and setuptools. Trivy reports them (HIGH) and pip has no
# fixed release yet. The running app never needs a package manager, so remove pip from the venv and the base image.
RUN /opt/venv/bin/python -m pip uninstall -y pip \
 && /usr/local/bin/python -m pip uninstall -y pip
COPY . .
# The key below exists only so collectstatic can start; it is NOT used at runtime.
RUN DJANGO_SETTINGS_MODULE=config.settings.prod DJANGO_SECRET_KEY=build-time-placeholder \
    python manage.py collectstatic --noinput \
 && mkdir -p /app/media \
 && chown app:app /app/media \
 && chmod +x /app/docker/entrypoint.sh
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=4).status == 200 else 1)"]
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "-c", "gunicorn.conf.py"]

# ---------------------------------------------------------------- test: runtime + security tools (never deployed)
FROM runtime AS test
USER 0:0
COPY requirements-dev.txt .
# pip was removed from the runtime image above; this test-only stage puts it back to install the tools.
RUN python -m ensurepip \
 && pip install -r requirements-dev.txt
USER 10001:10001
