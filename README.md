# Legal RAG 

RAG for German tenancy law (BGB §§535-580a), built with Azure OpenAI, Azure AI Search, and a React frontend.

The LLM never generates norm text. Instead:

1. The LLM outputs `[1]`, `[2]` citation markers via structured output (JSON schema enforced)
2. Post-processing replaces markers with **verbatim text** from a pre-parsed norm cache
3. Source validation drops any invalid references

This makes citations deterministic.

```
User query → Query rewrite (GPT-4o-mini)
  → Azure AI Search (hybrid: BM25 + vector)
  → GPT-4o structured output: { explanation: "...[1]...[2]...", cited_sources: [1,2], confidence: "high" }
  → Post-processing: source validation → citation injection → URL generation
  → Response with grounded citations
```

## Architecture

| Component | Technology |
|-----------|-----------|
| Backend | Python / Quart (async) |
| Frontend | React + TypeScript + Fluent UI |
| Search | Azure AI Search (hybrid: BM25 + vector) |
| LLM | Azure OpenAI GPT-4o (structured output) |
| Embeddings | text-embedding-3-large |
| Data source | BMJ XML (gesetze-im-internet.de) |
| Deployment | Azure Container Apps, Bicep IaC |
| Auth | HTTP Basic Auth |

## RAG Approaches

Two interchangeable implementations:

- **Custom** (`RAG_APPROACH=custom`): Direct Azure SDK, full control over pipeline
- **LangChain** (`RAG_APPROACH=langchain`): LCEL chain with identical post-processing

Both share the same anti-hallucination post-processing layer.

## Evaluation Dashboard

The `/evaluation` page provides:

- **Strategy comparison**: BM25 vs vector vs hybrid (Recall@5, Precision@5, groundedness, citation accuracy)
- **Category breakdown**: Metrics sliced by query type (technical, colloquial, multi-part, etc.)
- **Pattern recommendations**: Data-driven decisions on whether to adopt query rewrite, HyDE, query decomposition, or semantic ranker

Golden dataset: 36 Mietrecht Q&A pairs tagged by category.

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Azure subscription with OpenAI access

### Setup

```bash
# Clone and configure
cp .env.sample .env
# Edit .env with your Azure credentials

# Backend
cd app/backend
pip install -r requirements.txt

# Ingest data
python prepdocs.py --download

# Run backend
python main.py

# Frontend (separate terminal)
cd app/frontend
npm install
npm run dev
```

### Docker

```bash
docker-compose up
```

### Azure Deployment

```bash
azd auth login
azd up
```

## Project Structure

```
legal-rag/
├── app/
│   ├── backend/
│   │   ├── approaches/          # RAG implementations (custom + LangChain)
│   │   ├── core/                # Authentication
│   │   ├── evaluation/          # Metrics, evaluator, strategy comparison
│   │   ├── models/              # Pydantic models (chat, norm, evaluation)
│   │   ├── postprocessing/      # Citation injection, source validation, URL gen
│   │   ├── prepdocslib/         # XML parser, chunker, embeddings, search manager
│   │   ├── app.py               # Quart app + routes
│   │   └── prepdocs.py          # Ingestion CLI
│   └── frontend/                # React + TypeScript + Fluent UI
├── data/                        # BMJ XML, golden dataset
├── infra/                       # Bicep IaC
├── tests/                       # pytest
└── .github/workflows/           # CI/CD
```

## Tests

```bash
cd app/backend
python -m pytest ../../tests/backend -v
```
