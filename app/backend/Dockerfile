FROM python:3.12.8-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN adduser --disabled-password --gecos "" appuser
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:50505/health')" || exit 1

EXPOSE 50505

CMD ["hypercorn", "main:app", "--bind", "0.0.0.0:50505"]
