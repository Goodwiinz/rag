"""The Host allow-list must stay env-configurable without losing prod hosts.

`TrustedHostMiddleware` answers 400 "Invalid host header" for any host outside
the allow-list. A server-side Next.js rewrite proxies with the DESTINATION host
(CI: `backend`), so environments must be able to extend the list from env —
while the default keeps the deployed hostnames (`*.gen-text.app`, in-cluster
service DNS) that dev depends on.
"""

from src.core.config import Settings, get_settings


def test_default_trusted_hosts_keep_deployed_hostnames() -> None:
    hosts = get_settings().trusted_hosts_list
    for required in ("localhost", "*.gen-text.app", "*.svc.cluster.local"):
        assert required in hosts, (
            f"{required} missing from TRUSTED_HOSTS — the backend would answer "
            "400 Invalid host header for that origin"
        )


def test_trusted_hosts_parses_env_override() -> None:
    settings = Settings(TRUSTED_HOSTS=" localhost , backend ,, frontend ")
    assert settings.trusted_hosts_list == ["localhost", "backend", "frontend"]
