# Published production dependency image. The commit-style tag resolves to
# sha256:75b224f86a60c02e9343ca085fb4f195251a2554119b78e0972c3e09966c0e34.
FROM registry.digitalocean.com/ragsystemregistry/backend:3a436b2-r1

USER root

# The pinned source image has a malformed numpy dist-info METADATA file.  A
# clean reinstall repairs dependency introspection used by transformers and
# langchain-core without changing the application dependency surface.
RUN python -m pip install --no-cache-dir --force-reinstall numpy==1.26.4

# Build context is the repository root.  Only runtime backend source, the
# shared eval helpers, and this task's adapter enter the image; evals/specs is
# intentionally never copied.
COPY backend/ /app/
COPY evals/harbor_common /app/evals/harbor_common
# `evals` ships no package marker in the repository, so create one here:
# without it `evals.harbor_common` does not resolve under PYTHONPATH=/app.
RUN printf '' > /app/evals/__init__.py
COPY evals/agent-arxiv-research-flow-v1/environment/run_agent.py /benchmark/run_agent.py

RUN chmod 0555 /benchmark/run_agent.py && chown -R appuser:appuser /app /benchmark

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
USER appuser

# Harbor supplies its own long-running command and executes the adapter with
# ``docker compose exec``.  Do not inherit the production Gunicorn wrapper.
ENTRYPOINT []
