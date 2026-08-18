# Quick start

## Prerequisites

- Python 3.11+
- Node.js 20+
- Git
- Provider keys for the routes enabled in `config/providers.yaml`

## Install

```bash
git clone https://github.com/BlockFrame/wiredframe-radar.git
cd wiredframe-radar

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium

npm run install:frontend
cp .env.example .env
```

Configure these keys in `.env`:

```dotenv
GEMINI_API_KEY=
OPENROUTER_API_KEY=
NVIDIA_API_KEY=
GETXAPI_KEY=
```

`GETXAPI_KEY` is optional; without it, Social collection is skipped and reported as unavailable. Optional proxy and image-generation settings are documented in `.env.example` and `config/providers.yaml.example`.

## Run locally

```bash
python run_pipeline.py
```

Run for an explicit report date:

```bash
python run_pipeline.py --date 2026-08-10
```

The report date is not the same as the content coverage date; the CLI logs the exact window used by the run.

## Recover a run

```bash
python run_pipeline.py --resume
python run_pipeline.py --resume-from 4.5
```

Use `--resume` to auto-detect the most recent valid checkpoint. Use `--resume-from` only when you understand the phase boundary you are replaying.

## Validate without calling providers

```bash
python -m unittest discover -s tests -p '*_test.py'
python scripts/validate_report.py --web-dir ./web --date 2026-08-10
npm run check
npm run build
```

The test suite mocks external providers and should not consume LLM or GetXAPI quota.

## Start the frontend

```bash
npm run dev
```

Open the local URL printed by Vite. The frontend reads generated data from `web/data/`.

## Customize sources

- News feeds: `config/rss_feeds.txt`
- Direct pages: `config/web_scraper_sources.txt`
- Research: `config/research_feeds.txt`
- Dated Research pages: `config/research_web_sources.txt`
- Static Research references: `config/research_reference_sources.txt`
- X accounts: `config/twitter_accounts.txt`

See [Active source inventory](ai_news_sources.md) before adding a new source type.
