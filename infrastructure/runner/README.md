# Self-Hosted GitHub Actions Runner

A persistent GitHub Actions runner on a DigitalOcean droplet for CI/CD jobs
that need Docker or heavy compute (image builds, test suites).

## Host

| Property | Value                             |
| -------- | --------------------------------- |
| Droplet  | `moltbot1241onubuntu` (DO, NYC3)  |
| IP       | `138.197.36.44`                   |
| Specs    | 8 vCPU / 16 GB RAM / 320 GB disk  |
| OS       | Ubuntu 24.04 LTS                  |
| Docker   | 28.2                              |
| Runner   | GitHub Actions Runner 2.333.1     |
| Labels   | `self-hosted`, `linux`, `x64`     |
| User     | `runner` (non-root, docker group) |

## Workflows Using This Runner

- `.github/workflows/docker-build.yml` - backend + frontend image builds
- `.github/workflows/test-runner.yml` - test execution

Both use `runs-on: [self-hosted, linux]`.

## Service Management

```bash
ssh root@138.197.36.44

# Status / stop / start
systemctl status actions.runner.Goodwiinz-rag.do-droplet-runner
systemctl stop   actions.runner.Goodwiinz-rag.do-droplet-runner
systemctl start  actions.runner.Goodwiinz-rag.do-droplet-runner

# Logs
journalctl -u actions.runner.Goodwiinz-rag.do-droplet-runner -f
```

## Re-registering the Runner

If the runner loses its registration (token expired, repo transfer, etc.):

```bash
# 1. Generate a new registration token (requires classic PAT with repo scope)
read -s "GH_PAT?Classic PAT: " && export GH_PAT
REG_TOKEN=$(curl -sL -X POST \
  -H "Authorization: token $GH_PAT" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repositories/1073120335/actions/runners/registration-token \
  | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['token'])")

# 2. SSH in and reconfigure
ssh root@138.197.36.44
systemctl stop actions.runner.Goodwiinz-rag.do-droplet-runner
su - runner -c 'cd ~/actions-runner && ./config.sh remove --token <OLD_TOKEN>'
su - runner -c 'cd ~/actions-runner && ./config.sh \
  --url https://github.com/Goodwiinz/rag \
  --token <REG_TOKEN> \
  --name do-droplet-runner \
  --labels self-hosted,linux,x64 \
  --work _work \
  --replace \
  --unattended'
systemctl start actions.runner.Goodwiinz-rag.do-droplet-runner
```

## Notes

- The runner is **not ephemeral** (unlike the previous ARC/K8s setup) - it persists
  across jobs. Periodic Docker cleanup is recommended:
  `ssh root@138.197.36.44 "docker system prune -af --volumes"`
- ARC on DOKS was decommissioned in favor of this setup (see `infrastructure/arc/`
  for historical reference).
- The repo owner is `Goodwiinz` (capital G) - using `goodwiins` causes 404s due to
  GitHub's redirect behavior with the runner binary.
