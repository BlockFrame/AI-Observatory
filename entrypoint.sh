#!/bin/bash
set -e

echo "Starting R[AI]DAR..."

# Seed only missing configuration files. A bind-mounted operator configuration
# remains authoritative, while a fresh named/empty volume becomes runnable.
mkdir -p /app/config /app/data /app/web/data /app/logs
cp -an /app/config-defaults/. /app/config/

# Set up cron job only if enabled
if [ "${ENABLE_CRON:-false}" = "true" ]; then
    CRON_SCHEDULE="${COLLECTION_SCHEDULE:-0 6 * * *}"
    # Debian cron does not reliably inherit the container environment. Persist
    # a shell-quoted allowlist so scheduled runs receive the same routes and
    # controls as an interactive container run.
    python3 - <<'PY'
import os
import shlex

exact = {
    "GEMINI_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY", "GOOGLE_API_KEY",
    "GETXAPI_KEY", "GITHUB_TOKEN", "LESSWRONG_PROXY_URL", "PIPELINE_PROXY_URL",
    "LOOKBACK_HOURS", "TARGET_DATE", "TZ",
}
prefixes = ("LLM_", "OPENROUTER_", "PIPELINE_", "ANALYZER_", "MAX_ANALYSIS_")
with open("/app/.pipeline-env", "w", encoding="utf-8") as handle:
    for key in sorted(os.environ):
        if key in exact or key.startswith(prefixes):
            handle.write(f"export {key}={shlex.quote(os.environ[key])}\n")
PY
    chmod 0600 /app/.pipeline-env
    echo "$CRON_SCHEDULE cd /app && /bin/bash -lc '. /app/.pipeline-env && { python3 /app/scripts/check_openrouter_pricing.py && python3 /app/run_pipeline.py --config-dir /app/config --data-dir /app/data --web-dir /app/web && cp /app/llms.txt /app/ai-index.json /app/web/; } >> /app/logs/cron.log 2>&1'" > /etc/cron.d/ai-news-cron
    chmod 0644 /etc/cron.d/ai-news-cron
    crontab /etc/cron.d/ai-news-cron
    echo "Cron job scheduled: $CRON_SCHEDULE"
    cron
else
    echo "Cron scheduler disabled (set ENABLE_CRON=true to enable)"
fi

# Start nginx in foreground
echo "Starting web server on port 80..."
nginx -g 'daemon off;'
