# Published production dependency image. The commit-style tag resolves to
# sha256:75b224f86a60c02e9343ca085fb4f195251a2554119b78e0972c3e09966c0e34.
FROM registry.digitalocean.com/ragsystemregistry/backend:3a436b2-r1

USER root

# Repair malformed numpy metadata inherited from the pinned application image.
RUN python -m pip install --no-cache-dir --force-reinstall numpy==1.26.4

# Specs and verifier truth are deliberately absent from the Harness image.
COPY backend/ /app/
COPY evals/rag-retrieval-safety-grounding-v1/environment/run_agent.py /benchmark/run_agent.py
COPY evals/rag-retrieval-safety-grounding-v1/environment/mock_services/fixtures.json /benchmark/retrieval-fixtures.json

RUN chmod 0444 /benchmark/retrieval-fixtures.json \
    && chmod 0555 /benchmark/run_agent.py \
    && chown -R appuser:appuser /app /benchmark

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
USER appuser
ENTRYPOINT []
