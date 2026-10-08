"""Gunicorn settings, picked up automatically by `gunicorn config.wsgi:application`.

AI requests (assistant, scanner) can wait on the provider for AI_TIMEOUT seconds. Threads let a
worker keep serving other pages while one request waits, and the timeout is set above
AI_TIMEOUT so a slow AI answer isn't killed mid-response.
"""
import multiprocessing
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 4)))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", 4))
timeout = int(os.environ.get("AI_TIMEOUT", 90)) + 30
graceful_timeout = 30
max_requests = 1000          # recycle workers now and then to contain memory growth
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
