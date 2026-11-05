# Enterprise IT Support Agentic RAG System

A web-based IT support assistant that answers questions using a company knowledge base first. If the private knowledge base does not provide sufficient evidence, the agent can fall back to external web search. The app shows the agent's workflow trace and answer citations.

## Features

- Chat interface for IT support questions.
- LangGraph workflow that routes questions, retrieves and grades private knowledge, and uses web search when evidence is weak.
- Document ingestion for PDF, TXT, Markdown, and DOCX files.
- Pinecone vector storage with Hugging Face sentence-transformer embeddings.
- FastAPI endpoints and interactive API documentation.
- SQLite audit log of questions, selected sources, and workflow traces.

## Requirements

- Python 3.11 or newer.
- An OpenRouter API key for the language model.
- A Pinecone API key for document retrieval and indexing.
- A Tavily API key for external-search fallback.

The embedding model (`sentence-transformers/all-MiniLM-L6-v2`) runs locally and may be downloaded the first time embeddings are created.

## Run locally

From the project root, create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create a `.env` file in the project root and set at least:

```dotenv
OPENROUTER_API_KEY=your-openrouter-api-key
PINECONE_API_KEY=your-pinecone-api-key
TAVILY_API_KEY=your-tavily-api-key
ADMIN_API_KEY=replace-with-a-private-admin-key
```

`TAVILY_API_KEY` is needed when the agent uses web fallback. Keep API keys private and do not commit `.env`.

To index the included sample knowledge base, run:

```powershell
python ingest_sample_kb.py
```

This creates or connects to the configured Pinecone index and indexes files in `data/sample_kb/`. The default index is `it-support-rag`, in the `company-it-kb` namespace. New indexes are created in AWS `us-east-1`.

Start the application:

```powershell
python run.py
```

Open [http://127.0.0.1:8085](http://127.0.0.1:8085). The interactive API docs are at [http://127.0.0.1:8085/docs](http://127.0.0.1:8085/docs).

## Configuration

Settings are read from environment variables or the root `.env` file. Names are case-insensitive.

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `ENTERPRISE IT SUPPORT AGENTIC RAG SYSTEM` | Application name shown in the UI and health response. |
| `APP_ENV` | `development` | Application environment label. |
| `OPENROUTER_API_KEY` | Empty | Required for routing, evidence grading, and answer generation. |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter-compatible API base URL. |
| `OPENROUTER_MODEL` | `openrouter/free` | Model identifier used by the agent. |
| `TAVILY_API_KEY` | Empty | Required for external web-search fallback. |
| `PINECONE_API_KEY` | Empty | Required for vector retrieval and document indexing. |
| `PINECONE_INDEX_NAME` | `it-support-rag` | Pinecone index name. |
| `PINECONE_NAMESPACE` | `company-it-kb` | Namespace used within the index. |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Hugging Face embedding model; this implementation expects 384 dimensions. |
| `TOP_K` | `4` | Number of knowledge-base matches retrieved. |
| `ADMIN_API_KEY` | `change-me` | Secret required by the document-ingestion endpoint. Set a strong value. |
| `AUDIT_DB_PATH` | `data/audit.db` | SQLite audit database path. |
| `UPLOAD_DIR` | `uploads` | Directory where uploaded source files are saved. |
| `SAMPLE_KB_DIR` | `data/sample_kb` | Directory read by the sample ingestion script. |

## API

- `GET /api/health` — health check.
- `POST /api/chat` — ask a question. JSON body: `{"question": "How do I connect to the company VPN?"}`.
- `POST /api/ingest` — upload a supported document. Include the `X-Admin-Key` header.

Example chat request:

```powershell
curl.exe -X POST http://127.0.0.1:8085/api/chat `
  -H "Content-Type: application/json" `
  -d '{"question":"How do I connect to the company VPN?"}'
```

Example document upload:

```powershell
curl.exe -X POST http://127.0.0.1:8085/api/ingest `
  -H "X-Admin-Key: replace-with-a-private-admin-key" `
  -F "file=@data/sample_kb/company_it_handbook.md"
```

The chat response includes the answer, source used, citations, rewritten query, and agent trace. Uploaded files are indexed into Pinecone and retained in the configured upload directory.

## Docker

Build the image from the project root:

```powershell
docker build -f dockerfile -t enterprise-it-support-rag .
```

Run it with the `.env` file:

```powershell
docker run --env-file .env -p 8080:8080 enterprise-it-support-rag
```

The container listens on port `8080` by default. Open [http://localhost:8080](http://localhost:8080).

## Project layout

```text
app/
  api/          FastAPI routes
  core/         Configuration and logging
  rag/          LangGraph workflow, state, and Pinecone vector store
  services/     Document ingestion and audit logging
data/
  sample_kb/    Example company IT documents
static/         Browser JavaScript and CSS
templates/      Chat UI template
uploads/        Uploaded source documents
```

## Data handling

Audit records include the submitted question, selected source, and workflow trace. Uploaded source files are stored under `UPLOAD_DIR`; indexed document chunks are sent to Pinecone. Questions, and when applicable retrieved context, are sent to the configured language-model provider. Questions may also be sent to Tavily when web fallback is used. Do not submit sensitive information unless your organization's provider and data-handling policies allow it.
