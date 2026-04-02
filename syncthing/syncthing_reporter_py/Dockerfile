FROM python:3.12-slim
ARG REPORTER_BUILD_VERSION=2026-03-17.1
LABEL org.opencontainers.image.title="syncthing_reporter_py" \
      org.opencontainers.image.version="$REPORTER_BUILD_VERSION" \
      org.opencontainers.image.description="Syncthing reporter with DE/EN support" \
      org.opencontainers.image.authors="Roman Glos"
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    REPORTER_BUILD_VERSION=$REPORTER_BUILD_VERSION
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY report.py /app/report.py
COPY entry.sh /app/entry.sh
COPY scheduler.sh /app/scheduler.sh
RUN sed -i 's/\r$//' /app/entry.sh /app/scheduler.sh && \
    chmod 755 /app/entry.sh /app/scheduler.sh && \
    chmod 644 /app/report.py
VOLUME ["/state"]
ENV STATE_DIR=/state ATTACH_DIR=/state/attach
ENTRYPOINT ["/app/entry.sh"]
