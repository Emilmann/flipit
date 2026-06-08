# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Python-Verhalten für Container: kein .pyc, ungepuffertes stdout/stderr (Logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Abhängigkeiten zuerst kopieren → besseres Layer-Caching bei Code-Änderungen
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Anwendungs-Code
COPY src/ ./src/

EXPOSE 8501

# Healthcheck gegen Streamlits eingebauten Endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "src/flipit/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]
