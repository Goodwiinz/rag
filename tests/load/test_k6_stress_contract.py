"""Contract guard for the maximum shared-dev K6 stress profile.

K6 scripts cannot run under Python/CI here, so this is a source-level contract
guard (not a behavioural test): it asserts the repaired harness targets current
backend/Supabase routes, carries setup auth into VUs, and cleans up after itself.
Coarse by design — see docs/plans/2026-07-15-shared-dev-maximum-stress-test.md.
"""

from pathlib import Path
import unittest

SOURCE = Path(__file__).with_name("k6-stress-testing.js").read_text()

_RUNNER_PATH = Path(__file__).with_name("run-shared-dev-max.sh")
# Empty string when absent → assertions fail cleanly (RED) instead of erroring.
RUNNER = _RUNNER_PATH.read_text() if _RUNNER_PATH.exists() else ""


class K6StressContractTest(unittest.TestCase):
    def test_uses_current_backend_routes(self) -> None:
        for route in (
            "/api/v1/search/",
            "/api/v1/documents",
            "/api/v1/auth/me",
            "/api/v1/files/upload",
        ):
            self.assertIn(route, SOURCE, f"missing current route: {route}")

    def test_drops_stale_routes(self) -> None:
        # Supabase owns auth; profile/upload moved. These must be gone.
        for stale in (
            "/api/v1/users/profile",
            "/api/v1/documents/upload",
            "/auth/register",
            "/auth/login",
        ):
            self.assertNotIn(stale, SOURCE, f"stale route still present: {stale}")

    def test_supabase_admin_setup(self) -> None:
        self.assertIn("/auth/v1/admin/users", SOURCE)
        self.assertIn("grant_type=password", SOURCE)
        self.assertIn("email_confirm", SOURCE)

    def test_setup_data_reaches_virtual_users(self) -> None:
        # setup() must RETURN authenticated users; the default fn must read
        # them from its `data` argument (module-level state does NOT cross the
        # setup->VU VM boundary in k6).
        self.assertRegex(SOURCE, r"return\s*\{[\s\S]*?\busers\b")
        self.assertRegex(SOURCE, r"export\s+default\s+function\s*\(\s*data\s*\)")
        self.assertIn("data.users", SOURCE)

    def test_run_scoped_cleanup_and_summary(self) -> None:
        self.assertIn("run_id", SOURCE)      # uploads tagged with the run id
        self.assertIn("http.del", SOURCE)    # teardown deletes what it created
        self.assertIn("handleSummary", SOURCE)  # machine-readable summary out


class RunnerSafetyContractTest(unittest.TestCase):
    """Safety guard for the monitored runner (run-shared-dev-max.sh)."""

    def test_targets_only_shared_dev(self) -> None:
        self.assertIn("dev-api.gen-text.app", RUNNER)
        self.assertIn("rag-dev", RUNNER)

    def test_reads_supabase_credentials_secret(self) -> None:
        self.assertIn("supabase-credentials", RUNNER)
        for key in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
            self.assertIn(key, RUNNER)

    def test_does_not_leak_secrets_via_docker_e_flag(self) -> None:
        # Secrets go to the container via --env-file (hidden from `ps`), never
        # `-e KEY=$VALUE` (which exposes values in the host process list).
        self.assertIn("--env-file", RUNNER)
        self.assertNotIn("-e SUPABASE", RUNNER)

    def test_health_gating_and_restart_baseline(self) -> None:
        self.assertIn("/health", RUNNER)
        self.assertIn("/health/readiness", RUNNER)
        self.assertIn("restartCount", RUNNER)

    def test_strict_mode_and_traps(self) -> None:
        self.assertIn("set -euo pipefail", RUNNER)
        self.assertIn("trap", RUNNER)

    def test_results_dir_and_modes(self) -> None:
        self.assertIn("/tmp/rag-stress", RUNNER)
        self.assertIn("--preflight", RUNNER)
        self.assertIn("--full", RUNNER)

    def test_full_requires_preflight_marker(self) -> None:
        # --full must refuse to run without a successful preflight marker.
        self.assertRegex(RUNNER, r"(?s)--full.*marker|marker.*--full|PREFLIGHT_MARKER")


if __name__ == "__main__":
    unittest.main()
