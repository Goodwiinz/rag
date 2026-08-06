# CI and release workflows

GitHub Actions owns CI, image construction, and release orchestration. Dev has
one release owner: `release-dev.yml`.

## Dev release flow

```text
push to develop
      |
      v
Test Pipeline at source SHA
      |
      | completed/success + Release Gate completed/success
      v
Release Dev (single writer)
      |
      +-- re-fetch develop; stop if source SHA is stale
      |
      +-- call Docker Build with that exact source SHA
      |     `backend:<full-source-SHA>` is a trace tag
      |     `sha256:...` is the immutable deployment identity
      |
      +-- validate Helm in a read-only job; stop if source SHA is stale
      |
      `-- on a fresh runner, prepare a bounded two-file commit
            recheck develop, mint the App token only at the write boundary,
            then force-with-lease only deploy/dev
```

Before this repair, Test Pipeline and Docker Build triggered independently on
`develop` pushes, then GitOps Image Update listened to Docker Build. That let an
image and dev manifest advance without proving that the same SHA passed the
required test gate. Docker Build no longer has a push trigger, and GitOps Image
Update no longer has a `workflow_run` trigger or a job that writes to `develop`.

The source tag is not treated as immutable because DigitalOcean Container
Registry tag immutability has not been proven. The digest returned by BuildKit
is what `deploy/dev` promotes and the Helm chart renders.

## Workflow responsibilities

| Workflow | Trigger | Responsibility |
| --- | --- | --- |
| `test-pipeline.yml` | Push and pull request | Run all required checks and publish the exact `Release Gate` result. |
| `release-dev.yml` | Completed Test Pipeline run on `develop` | Authorize the producer run, prevent stale releases, build once, and update `deploy/dev`. |
| `docker-build.yml` | Reusable call or manual dispatch | Check out an explicit full SHA, assert `HEAD`, push the full-SHA trace tag, and return its digest. |
| `gitops-image-update.yml` | Manual dispatch only | Retained legacy production image update; it has no dev role. |
| `deploy.yml` | Manual dispatch only | Retained legacy staging/production Helm path; it has no dev role and requires an explicit image tag. |
| `helm-validate.yml` | Push and pull request | Validate the Helm chart and environment values. |
| `workflow-lint.yml` | Workflow changes | Run `actionlint` across all workflows. |

The frontend is deployed separately through Vercel. The backend, migration init
container, Celery worker, Celery beat, and synthetic-traffic workloads share the
same backend digest through the Helm image helper.

## Release authorization

`release-dev.yml` fails closed unless all of these facts agree:

1. The event is a completed, successful Test Pipeline `push` run for
   `develop` in this repository.
2. The producer run returned by the Actions API has the same event, repository,
   branch, `workflow_run.head_sha`, and `workflow_run.run_attempt`.
3. The attempt-specific jobs endpoint returns exactly one producer job named
   `Release Gate`, and its status/conclusion are exactly `completed`/`success`
   for that SHA. A rerun can never borrow the gate result from another attempt.
4. A fresh `develop` read still points to the tested SHA before build.
5. Read-only Helm validation succeeds for the built digest, followed by another
   `develop` check.
6. A fresh promotion runner checks `develop` before preparing the bounded
   commit and again immediately before minting a write token.

`release-dev` uses a single concurrency group with cancellation. A source SHA
superseded before build produces no image. A source SHA superseded after build
may leave an unused image, but it does not produce a promotion commit after the
final check observes the newer branch tip. The ref check and update of another
ref are not an atomic transaction; `force-with-lease` protects `deploy/dev`
from an undetected competing update.

Each completed build records the source SHA, producer run ID/attempt/URL,
full-SHA trace tag, and digest in the job summary. Promotion also uploads
`release-evidence.json` and writes bounded `release-dev.json` metadata in the
release commit.

The job that executes the source-controlled Helm assertion has read-only
permissions and no App credential. Promotion runs on a fresh runner, does not
execute repository scripts, checks out with `persist-credentials: false`, and
prepares and verifies the exact two-file commit before minting the short-lived
App token. That token is passed only to the final `deploy/dev` push.

## Required repository configuration

The workflow code expects:

| Name | Kind | Purpose |
| --- | --- | --- |
| `DO_REGISTRY_TOKEN` | Actions secret | Authenticate the backend image push. |
| `DO_SPACES_ACCESS_KEY` | Actions secret | Read/write the BuildKit cache. |
| `DO_SPACES_SECRET_KEY` | Actions secret | Read/write the BuildKit cache. |
| `DEV_RELEASE_APP_ID` | Actions variable | ID of the dedicated dev-release GitHub App. |
| `DEV_RELEASE_APP_PRIVATE_KEY` | Actions secret | Mint a short-lived installation token. |

The App must be installed only where release commits are needed and granted
repository Contents write. Repository rules must allow it to update only
`deploy/dev` and must not give it a bypass on `develop` or other protected source
branches. The workflow's ordinary `GITHUB_TOKEN` remains read-only during dev
release orchestration.

These settings are external state and are not created by the workflow change.
Bootstrap them in this order so a write-capable release credential is never
available while source changes can bypass review:

1. Add a first-stage `develop` ruleset requiring pull requests, approval, and
   resolved conversations, and block direct pushes. Do not require the new
   `Release Gate` yet because it has not produced a proven check run.
2. Seed `deploy/dev` and add a ruleset that permits only the dedicated release
   App to perform the workflow's non-fast-forward update. Give the App no
   bypass on `develop` or other protected source refs.
3. Only then provision `DEV_RELEASE_APP_ID` and
   `DEV_RELEASE_APP_PRIVATE_KEY` and run shadow releases.
4. After one same-SHA green run, extend the `develop` ruleset with the required
   `Release Gate`, up-to-date branch, and secret-scanning requirements.

The workflow does not create `deploy/dev`, configure either ruleset, or change
Argo CD.

## Argo CD cutover

Landing these workflows does not prove or perform the live cutover. Keep Argo
tracking `develop` while shadow releases establish the exact chain:

```text
Test Pipeline source SHA -> registry digest -> deploy/dev release commit
```

Changing the Argo Application to track `deploy/dev`, pausing/re-enabling root
auto-sync, manually syncing the cutover, and collecting Application/revision and
live pod `imageID` evidence are separate, explicitly authorized operations.

## Manual Docker build

Manual image construction is available for diagnostics, but it cannot promote
dev:

1. Open **Actions -> Docker Build -> Run workflow**.
2. Supply a full lowercase 40-character commit SHA.
3. Record the returned full-SHA trace tag and registry digest.

No branch tip or short SHA is inferred.

## Local validation

Run the same workflow validator used in CI:

```bash
actionlint
```

For changes that also touch the release values/helper, lint and render each
real base-plus-environment combination. The base values file is intentionally
incomplete and does not lint on its own.

```bash
chart=infrastructure/helm/knowledge-graph-analytics
for env in dev staging production; do
  helm lint "$chart" -f "$chart/values.yaml" -f "$chart/values-$env.yaml"
  helm template rag "$chart" \
    -f "$chart/values.yaml" -f "$chart/values-$env.yaml" >/dev/null
done
bash "$chart/tests/backend_image_digest_render_test.sh"
```
