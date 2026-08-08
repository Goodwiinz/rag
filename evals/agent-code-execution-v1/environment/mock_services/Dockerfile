FROM python:3.11-slim

WORKDIR /service
COPY server.py /service/

RUN useradd --create-home --uid 10001 benchmark \
    && mkdir -p /service/scratch \
    && chown -R benchmark:benchmark /service

USER benchmark
EXPOSE 8080
ENTRYPOINT ["python", "/service/server.py"]
