FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng lame \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home app \
    && install -d -o app -g app /var/lib/liquid-briefing

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY briefing/ briefing/

ENV BRIEFING_DATA_DIR=/data BRIEFING_STATE_DIR=/var/lib/liquid-briefing
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
CMD ["python", "-m", "uvicorn", "briefing.app:app", "--host", "0.0.0.0", "--port", "8000"]
