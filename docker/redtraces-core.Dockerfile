# Reuse the already verified local collector image. This avoids another pull of
# the Python base layer on this device while retaining the same Python 3.12
# runtime used by the existing Telegram service.
FROM redtraces-ai-telegram:latest

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# This is the supplied project's Telegram/API runtime. The full requirements
# remain with its retained source for optional offline rule-generation tools.
COPY docker/redtraces-core-requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY redtraces-core/ /app/
COPY docker/redtraces_telegram_runner.py /app/redtraces_telegram_runner.py
