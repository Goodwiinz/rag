from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text()


class FrontendBuildArgsContractTest(unittest.TestCase):
    def test_local_ci_stage_passes_supabase_build_args(self) -> None:
        script = _read("scripts/ci/stages.sh")

        self.assertIn("--build-arg NEXT_PUBLIC_SUPABASE_URL=", script)
        self.assertIn("--build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=", script)

    def test_depot_e2e_workflow_passes_supabase_build_args(self) -> None:
        workflow = _read(".depot/workflows/test-pipeline.yml")

        self.assertIn("--build-arg NEXT_PUBLIC_SUPABASE_URL=", workflow)
        self.assertIn("--build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=", workflow)

    def test_compose_frontend_build_passes_supabase_build_args(self) -> None:
        compose = _read("config/docker-compose/docker-compose.ci.yml")

        self.assertIn("NEXT_PUBLIC_SUPABASE_URL:", compose)
        self.assertIn("NEXT_PUBLIC_SUPABASE_ANON_KEY:", compose)
