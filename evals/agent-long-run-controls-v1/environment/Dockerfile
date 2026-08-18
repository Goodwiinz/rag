FROM registry.digitalocean.com/ragsystemregistry/backend:3a436b2-r1

USER root
RUN python -m pip install --no-cache-dir --force-reinstall numpy==1.26.4

COPY backend/ /app/
COPY evals/harbor_common /app/evals/harbor_common
RUN printf '' > /app/evals/__init__.py
COPY evals/agent-long-run-controls-v1/environment/run_agent.py /benchmark/run_agent.py

RUN chmod 0555 /benchmark/run_agent.py && chown -R appuser:appuser /app /benchmark

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
USER appuser
ENTRYPOINT []
