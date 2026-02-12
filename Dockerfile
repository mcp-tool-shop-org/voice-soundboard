FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libsndfile1-dev && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE ./
COPY voice_soundboard/ voice_soundboard/
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir ".[kokoro]"

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 && rm -rf /var/lib/apt/lists/*
RUN groupadd -r vsb && useradd -r -g vsb vsb
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY --chown=vsb:vsb voice_soundboard/ voice_soundboard/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER vsb
ENTRYPOINT ["voice-soundboard"]
CMD ["--help"]
