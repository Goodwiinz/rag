"""Public health diagnostics stay limited to the Kubernetes readiness route."""

from fastapi.routing import APIRoute

from src.health.checker import HealthChecker
from src.health.endpoints import router


def test_health_router_exposes_only_readiness_without_expensive_dispatch() -> None:
    routes = {
        (route.path, method)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in (route.methods or set())
    }

    assert routes == {("/health/readiness", "GET")}
    assert {name for name in dir(HealthChecker) if name.startswith("check_")} == {
        "check_database",
        "check_redis",
    }
