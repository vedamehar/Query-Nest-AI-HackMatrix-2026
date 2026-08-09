# QueryNest AI Platform

Intelligent chatbot infrastructure for secure, multi-tenant knowledge access across enterprise and customer-facing environments.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-blue)](https://fastapi.tiangolo.com)

## Project Title

**QueryNest AI Platform: Intelligent Chatbot Infrastructure for Secure Knowledge Access**

## Team Name

**Technological Coder**

## Problem Statement

Modern organizations are not constrained by lack of data, but by their inability to operationalize knowledge efficiently and securely across both internal and external touchpoints.

- Customer-facing systems still rely on static navigation, leading to user drop-offs, lower conversions, and reduced engagement.
- Internal teams depend on manual policy retrieval, causing delayed decisions, inconsistent understanding, and compliance risks.

Identified gaps:

1. Absence of unified knowledge access.
2. Lack of context-aware intelligence.
3. Weak data governance in AI systems.
4. Inability to support dual environments (enterprise + public website).
5. Limited integration and deployment flexibility.

## Solution Overview

QueryNest AI is a dual-mode, multi-tenant RAG platform designed for secure knowledge operations:

- Internal Compliance Assistant: operates in controlled/offline enterprise environments.
- External Website Chatbot: handles public customer interactions through embeddable widgets.
- Admin-controlled ingestion: only approved data sources are ingested.
- RAG-grounded responses: answers are generated from approved sources to reduce hallucinations.
- Multi-source knowledge support: URLs, PDFs, docs, platform content, and video transcription.
- Tenant-isolated architecture: data remains segregated and secure per organization.

## PPT Link

- Project deck : [HackMatrix_2026.pptx.pdf](HackMatrix_2026.pptx.pdf)

## Live Demonstration Link

- Live demonstration (YouTube):
- Optional production URL: ADD_LIVE_WEBSITE_LINK_HERE

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, Next.js, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, Python 3.11 |
| RAG & Orchestration | LangChain, LlamaIndex, FlashRank |
| AI/LLM | Gemini, Anthropic Claude, OpenAI |
| Embeddings | Voyage AI (1024-dim), OpenAI fallback |
| Vector Database | ChromaDB |
| Data & Auth | Supabase (PostgreSQL, JWT, RLS, RBAC) |
| Ingestion | Crawl4AI, PyMuPDF/OCR, Whisper transcription |
| Analytics | Recharts, conversation logging |
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
# Root template (documents both frontend/backend variables)
cp .env.example .env

# Backend
cp backend/.env.example backend/.env

# Frontend
cp frontend/.env.example frontend/.env.local
```

Update these files with your actual keys and URLs.

### 3. Set up Supabase

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
