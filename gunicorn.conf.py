"""Gunicorn settings for the production container."""
import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("WEB_CONCURRENCY") or 3)
worker_tmp_dir = "/dev/shm"  # RAM-backed, so the container's filesystem can stay read-only
accesslog = "-"
errorlog = "-"
timeout = 30
