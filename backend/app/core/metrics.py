"""
SENTINEL — Basic Metrics (Phase 2, minimal track)
=====================================================
A Prometheus /metrics endpoint — request count/latency plus EC-03 job
outcomes, per the Phase 2 build plan's explicit scope ("a Prometheus
/metrics endpoint is enough for now; skip full OpenTelemetry tracing
until Phase 2-Full"). No tracing, no per-request spans, no dashboards
here — just enough to answer "is this thing serving traffic and are
background jobs succeeding."

GET /metrics is deliberately UNAUTHENTICATED: Prometheus scrapers don't
carry a user JWT, and there's no per-tenant concept for infrastructure
metrics anyway. Accepted trade-off for the minimal track — a real
deployment should restrict this at the network level (e.g. don't expose
it on the same public listener as the rest of the API), not bolt app-level
auth onto a scrape endpoint.
"""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

router = APIRouter()

HTTP_REQUESTS_TOTAL = Counter(
    "sentinel_http_requests_total",
    "Total HTTP requests handled",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "sentinel_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)

EC03_JOBS_SCHEDULED_TOTAL = Counter(
    "sentinel_ec03_jobs_scheduled_total",
    "EC-03 mule-withdrawal timers scheduled",
)

EC03_JOBS_FIRED_TOTAL = Counter(
    "sentinel_ec03_jobs_fired_total",
    "EC-03 mule-withdrawal timers that fired (executed the simulated withdrawal)",
)

EC03_JOBS_FAILED_TOTAL = Counter(
    "sentinel_ec03_jobs_failed_total",
    "EC-03 mule-withdrawal timers that failed to schedule (Arq/Redis error)",
)


@router.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
