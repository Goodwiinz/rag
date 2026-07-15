"""Contract guard for the maximum shared-dev K6 stress profile.

K6 scripts cannot run under Python/CI here, so this is a source-level contract
guard (not a behavioural test): it asserts the repaired harness targets current
backend/Supabase routes, carries setup auth into VUs, and cleans up after itself.
Coarse by design — see docs/plans/2026-07-15-shared-dev-maximum-stress-test.md.
"""

from pathlib import Path
import unittest

SOURCE = Path(__file__).with_name("k6-stress-testing.js").read_text()


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
        self.assertRegex(SOURCE, r"return\s*\{[\s\S]*?users:")
        self.assertRegex(SOURCE, r"export\s+default\s+function\s*\(\s*data\s*\)")
        self.assertIn("data.users", SOURCE)

    def test_run_scoped_cleanup_and_summary(self) -> None:
        self.assertIn("run_id", SOURCE)      # uploads tagged with the run id
        self.assertIn("http.del", SOURCE)    # teardown deletes what it created
        self.assertIn("handleSummary", SOURCE)  # machine-readable summary out


if __name__ == "__main__":
    unittest.main()
