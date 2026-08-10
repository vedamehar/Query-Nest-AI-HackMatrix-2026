# QueryNest AI Platform
Intelligent chatbot infrastructure for secure, multi-tenant knowledge access and enterprise compliance workflows.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-blue)](https://fastapi.tiangolo.com)

## Project Title

**QueryNest AI Platform**

## Team Name

**Technological Coder**

## Problem Statement

Organizations struggle to operationalize knowledge efficiently and securely across both public and internal touchpoints. Customers face static navigation and slow support, while internal users depend on manual retrieval of policies, SOPs, and compliance documents.

## Solution Overview

QueryNest AI Platform is the umbrella product story for the repository. It combines the website chatbot and enterprise knowledge workflows into one secure, multi-tenant system.

CompliAssist is one major sub-module within QueryNest AI. It focuses on enterprise compliance assistance with grounded responses, document ingestion, video transcription, and audit-friendly workflows.

Shared capabilities across the platform include admin-controlled ingestion, RAG-grounded responses, multi-source knowledge support, tenant isolation, structured compliance analysis, and secure widget-based deployment.

## PPT Link

- Project deck: [HackMatrix_2026.pptx.pdf](HackMatrix_2026.pptx.pdf)

## Live Demonstration Link

- Live demonstration: ADD_LIVE_WEBSITE_LINK_HERE

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, Next.js, Tailwind CSS, shadcn/ui, Material UI |
| Backend | FastAPI, Python |
| AI/LLM | Gemini, Anthropic Claude, OpenAI, Ollama |
| Retrieval & Orchestration | LangChain, LlamaIndex, FlashRank, FAISS |
| Embeddings | Voyage AI, Sentence Transformers |
| Vector Database | ChromaDB |
| Data & Auth | Supabase (PostgreSQL, JWT, RLS, RBAC), SQLite |
| Ingestion | Crawl4AI, PyMuPDF/OCR, Whisper transcription |
| Analytics & Logging | Recharts, audit logging |
| Deployment | Docker, Railway, Vercel |

## Team Members

1. Harshal Sudhakar Marathe
2. Vedant Narayan Mehar
3. Mayur R Chikhale
4. Aum Santosh Mishra

## Setup Instructions

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker Desktop
- Supabase account
- LLM API key(s): Anthropic or Gemini
- Voyage AI API key (recommended)

### 1. Clone the repository

```bash
git clone https://github.com/<your-team>/<your-repo-name>.git
cd <your-repo-name>
```

### 2. Configure environment files

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Update the values for your local environment.

### 3. Set up the database

1. Create a Supabase project.
2. Open SQL Editor.
3. Run [supabase/schema.sql](supabase/schema.sql).

### 4. Start local infrastructure

```bash
docker-compose up -d
```

### 5. Run backend

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --port 8000
```

### 6. Run frontend

```bash
cd frontend
npm install
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).