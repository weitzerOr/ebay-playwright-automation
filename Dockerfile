# Keep this tag in sync with the Playwright version in requirements.txt.
FROM mcr.microsoft.com/playwright/python:v1.64.0-noble

WORKDIR /app

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb openjdk-21-jre-headless wget \
    && wget -qO /tmp/allure.tgz https://github.com/allure-framework/allure2/releases/download/2.32.0/allure-2.32.0.tgz \
    && tar -xzf /tmp/allure.tgz -C /opt \
    && ln -s /opt/allure-2.32.0/bin/allure /usr/local/bin/allure \
    && rm /tmp/allure.tgz \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/scripts/docker-entrypoint.sh \
    && mkdir -p /app/allure-results /app/allure-report /app/reports/screenshots /app/reports/traces \
    && chown -R pwuser:pwuser /app

USER pwuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RUNNING_IN_DOCKER=1 \
    HEADLESS=false \
    BROWSER_CHANNEL=

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["pytest"]
