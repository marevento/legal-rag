# Legal RAG

[![CI](https://github.com/marevento/legal-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/marevento/legal-rag/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Azure](https://img.shields.io/badge/deployed-Azure%20Container%20Apps-0078d4)](https://azure.microsoft.com/en-us/products/container-apps)

RAG system for German tenancy law (BGB §§535-580a). Retrieves statutory norms via hybrid search and grounds every citation in verbatim source text through deterministic post-processing.

Try it: https://ca-lafrvru2frc2k.gentleocean-0fa95861.swedencentral.azurecontainerapps.io/

> **Note:** The app scales to zero instances when idle to minimize costs. The first request may take ~30 seconds (cold start).

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, Quart (async), Pydantic |
| Frontend | React 18, TypeScript, Fluent UI |
| Search | Azure AI Search (BM25 + vector hybrid) |
| LLM | Azure OpenAI GPT-4o (structured output), GPT-4o-mini |
| Embeddings | text-embedding-3-large (3072 dims) |
| Auth | JWT + magic-link email (Azure Communication Services) |
| Infrastructure | Azure Container Apps, Bicep IaC, Docker |
| CI/CD | GitHub Actions (lint, test, pip-audit) |
| Data | BMJ XML from gesetze-im-internet.de |

## How It Works

```
User query
  → Query transform (configurable): none | rewrite | HyDE
  → Optional: query decomposition (parallel sub-queries → merge by norm ID)
  → Hybrid retrieval (BM25 + vector via Azure AI Search)
  → GPT-4o structured output → { explanation, cited_sources[], confidence }
  → Post-processing: source validation → citation injection → URL generation
  → Response with verbatim statutory citations
```

GPT-4o outputs citation markers (`[1]`, `[2]`) via JSON schema enforcement. A post-processing layer validates each marker against the retrieval set, injects verbatim norm text from a pre-parsed cache, and generates deep links to gesetze-im-internet.de. Invalid markers are dropped.

## Features

### Configurable Retrieval

Composable options, selectable from the UI settings panel:

- **Query transform** (dropdown): Raw query, Query Rewrite (colloquial → legal terminology via GPT-4o-mini), or HyDE (hypothetical document embedding for better semantic matching)
- **Query decomposition** (toggle): Splits multi-part questions into sub-queries, retrieves in parallel via `asyncio.gather`, deduplicates by norm ID

### Citation Pipeline

1. **Structured output** — JSON schema constrains GPT-4o to `{ explanation, cited_sources, confidence }`. Sources referenced by index only.
2. **Source validation** — Out-of-range indices are dropped.
3. **Citation injection** — Markers replaced with verbatim statutory text from the norm cache.
4. **URL generation** — Deep links to official gesetze-im-internet.de source.

### Two RAG Implementations

Same retrieval and post-processing, two orchestration layers: **Custom** (direct Azure SDK) and **LangChain** (LCEL chain) — for comparing abstraction trade-offs.

### Evaluation Dashboard

Runs the pipeline against a golden dataset (37 Q&A pairs) across strategy combinations:

- **Strategy comparison** — BM25 vs vector vs hybrid: Recall@5, Precision@5, groundedness (LLM-as-judge), citation accuracy
- **Category breakdown** — Metrics per query type (technical, colloquial, multi-part, definition, complex)
- **Pattern recommendations** — Data-driven: does rewrite improve colloquial recall? Does HyDE? Does decomposition help multi-part queries?

### Auth and Admin

Magic-link email authentication (Azure Communication Services), JWT sessions with admin/viewer roles, rate limiting. Admin dashboard with query analytics, latency tracking, and strategy distribution.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Structured output over prompting | JSON schema enforcement guarantees response shape |
| Deterministic citation injection | Post-processing replaces markers with verbatim norm text — no LLM-generated legal text |
| Compute-then-stream | Structured output must complete before citation injection can run |
| Two RAG approaches | Same pipeline with and without LangChain for abstraction comparison |
| Hybrid search default | Legal text benefits from keyword matching (§-numbers) and semantic similarity |
| Configurable query transform | Rewrite and HyDE address the vocabulary gap differently; composable with decomposition for evaluation |

## Quick Start

### Prerequisites

- Python 3.12+, Node.js 20+
- Azure subscription with OpenAI access

### Local Development

```bash
cp .env.sample .env    # Edit with your Azure credentials

# Backend
cd app/backend
pip install -r requirements.txt
python prepdocs.py --download    # Ingest norms into Azure AI Search
python main.py

# Frontend (separate terminal)
cd app/frontend
npm install && npm run dev

# Tests
cd app/backend && python -m pytest ../../tests/backend -v
```

### Docker

```bash
docker-compose up
```

### Azure Deployment

```bash
azd auth login && azd up
```

Provisions: Container App, Azure OpenAI (GPT-4o + GPT-4o-mini + embeddings), AI Search, Container Registry, Key Vault.

## Project Structure

```
legal-rag/
├── app/
│   ├── backend/
│   │   ├── approaches/          # RAG pipelines (custom + LangChain)
│   │   │   └── prompts/         # Jinja2 templates (chat, rewrite, HyDE, decompose)
│   │   ├── core/                # Auth, usage tracking
│   │   ├── evaluation/          # Evaluator, metrics (retrieval, groundedness, citation)
│   │   ├── models/              # Pydantic models (chat, norm, evaluation)
│   │   ├── postprocessing/      # Citation injection, source validation, URL generation
│   │   ├── prepdocslib/         # BMJ XML parser, chunker, embeddings, search index
│   │   └── app.py               # Quart app factory + routes
│   └── frontend/                # React + TypeScript + Fluent UI
│       └── src/pages/           # Chat, Evaluation dashboard, Admin
├── data/                        # BMJ XML, golden dataset (37 Q&A pairs)
├── infra/                       # Bicep IaC
├── tests/                       # 45 tests (pytest)
└── .github/workflows/           # CI (lint + test + audit)
```
