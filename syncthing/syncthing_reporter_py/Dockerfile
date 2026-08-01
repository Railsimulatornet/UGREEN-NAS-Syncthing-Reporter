FROM python:3.14-alpine

ARG REPORTER_BUILD_VERSION=2026-05-21.5
ARG REPORTER_BUILD_DATE=2026-05-21

LABEL org.opencontainers.image.title="UGREEN NAS Syncthing Reporter" \
      org.opencontainers.image.version="$REPORTER_BUILD_VERSION" \
      org.opencontainers.image.created="$REPORTER_BUILD_DATE" \
      org.opencontainers.image.description="Bilingual Syncthing HTML report for UGREEN NAS / Docker" \
      org.opencontainers.image.authors="Roman Glos" \
      org.opencontainers.image.source="https://github.com/Railsimulatornet/UGREEN-NAS-Syncthing-Reporter" \
      org.opencontainers.image.licenses="PolyForm-Noncommercial-1.0.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    REPORTER_VERSION=V2.2 \
    REPORTER_BUILD_DATE=$REPORTER_BUILD_DATE \
    REPORTER_BUILD_VERSION=$REPORTER_BUILD_VERSION \
    STATE_DIR=/state \
    ATTACH_DIR=/state/attach

RUN set -eux; \
    apk upgrade --no-cache; \
    apk add --no-cache ca-certificates tzdata; \
    update-ca-certificates

WORKDIR /app

COPY requirements.txt /app/
RUN set -eux; \
    python -m pip install --upgrade pip setuptools wheel; \
    python -m pip install -r /app/requirements.txt; \
    python -m pip install --upgrade "setuptools>=78.1.1" "msgpack>=1.2.1"

COPY report.py /app/report.py
COPY entry.sh /app/entry.sh
COPY scheduler.sh /app/scheduler.sh

RUN set -eux; \
    sed -i 's/\r$//' /app/entry.sh /app/scheduler.sh; \
    chmod 755 /app/entry.sh /app/scheduler.sh; \
    chmod 644 /app/report.py; \
    mkdir -p /state/attach; \
    chmod 775 /state /state/attach

VOLUME ["/state"]
ENTRYPOINT ["/bin/sh", "/app/entry.sh"]
