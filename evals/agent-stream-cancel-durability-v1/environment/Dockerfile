# Published production dependency image. The commit-style tag resolves to
# sha256:75b224f86a60c02e9343ca085fb4f195251a2554119b78e0972c3e09966c0e34.
FROM registry.digitalocean.com/ragsystemregistry/backend:3a436b2-r1

USER root

# Repair malformed numpy metadata inherited from the pinned application image.
RUN python -m pip install --no-cache-dir --force-reinstall numpy==1.26.4

# The full FastAPI import loads an entity-extraction module that asks tiktoken
# for cl100k_base at module scope. Pre-populate that immutable asset during the
# image build so the runtime network can remain model-host-only.
RUN mkdir -p /opt/tiktoken-cache && \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache \
    python -c 'import tiktoken; tiktoken.get_encoding("cl100k_base")'

# Only backend runtime source and this task's adapter enter the Harness image.
# The approved spec, verifier, truth, and calibration fixtures stay outside it.
COPY backend/ /app/
COPY evals/agent-stream-cancel-durability-v1/environment/run_agent.py /benchmark/run_agent.py

RUN chmod 0555 /benchmark/run_agent.py && chown -R appuser:appuser /app /benchmark

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache

WORKDIR /app
USER appuser
ENTRYPOINT []
