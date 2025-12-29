<p align="center">
  <img src="https://img.shields.io/badge/InsurAI-Insurance%20AI%20Agent-blue?style=for-the-badge" alt="InsurAI"/>
</p>

<h1 align="center">🛡️ InsurAI</h1>

<p align="center">
  <strong>AI-Powered Insurance Policy Assistant</strong><br>
  Transform complex insurance documents into conversational knowledge
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#api-reference">API</a> •
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-0.109+-green.svg" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Next.js-14+-black.svg" alt="Next.js"/>
  <img src="https://img.shields.io/badge/PostgreSQL-17-blue.svg" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/LangGraph-1.0+-purple.svg" alt="LangGraph"/>
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License"/>
</p>

---

## 🎯 What is InsurAI?

InsurAI is a RAG-based (Retrieval-Augmented Generation) conversational AI platform that transforms insurance policy documents into an intelligent, queryable knowledge base. Users can ask natural language questions about their coverage and receive accurate, cited answers.

```
User: "What are the exclusions in my policy?"

AI: "Based on your policy, the following are excluded:
    1. Pre-existing conditions [Page 5, Section 3.2]
    2. Self-inflicted injuries [Page 6, Section 3.4]
    3. Fraudulent claims [Page 8, Section 5.1]"
```

### The Problem We Solve

| Problem | Solution |
|---------|----------|
| 📄 **Opacity** - 20+ page policies are unreadable | Natural language Q&A interface |
| 🤖 **LLM Hallucination** - Generic AI guesses coverage | RAG with policy-specific context |
| ⚖️ **Liability Risk** - Wrong coverage info = lawsuits | "Coverage Guardrail" checks exclusions FIRST |
| 📞 **Support Load** - Repetitive queries to agents | Self-service AI assistant |

---

## ✨ Features

### 🔍 Intelligent Policy Processing
- **OCR Engine** - Extract text from scanned PDFs using PaddleOCR
- **Smart Chunking** - Configurable chunk sizes optimized for your LLM
- **LLM Classification** - Automatic semantic labeling of policy sections
- **Semantic Search** - Find relevant policy sections instantly

### 🛡️ Coverage Guardrail (Air Canada Defense)
```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│  Router  │ ──► │  Exclusion   │ ──► │  Inclusion   │ ──► │ Response │
│          │     │    Check     │     │    Check     │     │          │
└──────────┘     └──────────────┘     └──────────────┘     └──────────┘
                       │
                       ▼
              ❌ "NOT COVERED" 
              (stops here if excluded)
```

### 💬 Conversational Interface
- Real-time streaming responses
- Coverage status badges (Covered ✅ / Not Covered ❌ / Conditional ⚠️)
- Citation references with page numbers
- Conversation history

### 🏢 Multi-Tenant Architecture
- **Policy Isolation** - Each agent only accesses its own policy data
- **Multi-agent Support** - One agent per policy with unique policy IDs
- **User Limitations** - B2B context injection for user-specific constraints
- **Persistent Storage** - PostgreSQL + pgvector for production-ready data

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 17 with pgvector extension
- Google API Key (for Gemini)

### 1. Clone & Install

```bash
# Clone the repository
git clone https://github.com/ohadOrbach/InsurAI.git
cd InsurAI

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### 2. Configure Environment

```bash
# Create .env file
cp .env.example .env

# Edit with your API keys
nano .env
```

Required environment variables:
```env
# LLM
GOOGLE_API_KEY=your_gemini_api_key
LLM_PROVIDER=google
LLM_MODEL=gemini-2.0-flash

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/insur
VECTOR_STORE_TYPE=pgvector

# Embeddings (uses same Google API key)
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=models/text-embedding-004
```

### 3. Setup Database

```bash
# Run the setup script (macOS)
chmod +x scripts/setup_pgvector.sh
./scripts/setup_pgvector.sh
```

### 4. Start the Application

```bash
# Terminal 1: Start backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Start frontend
cd frontend && npm run dev
```

### 5. Open the App

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                                 │
│                     Next.js 14 (localhost:3000)                          │
│         Agent Cards → Chat Interface → Real-time Streaming               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           BACKEND API                                    │
│                    FastAPI (localhost:8000)                              │
│                                                                          │
│   /api/v1/agents     → Create/List/Delete agents                        │
│   /api/v1/chat       → Chat sessions and messages                       │
│   /api/v1/policies   → Policy ingestion (PDF/text)                      │
│   /api/v1/search     → Semantic search                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          CORE SERVICES                                   │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │    OCR       │  │   Vector     │  │  Coverage    │  │     LLM      │ │
│  │   Engine     │  │    Store     │  │    Agent     │  │   Service    │ │
│  │ (PaddleOCR)  │  │  (pgvector)  │  │ (LangGraph)  │  │  (Gemini)    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                                      │
│                                                                          │
│   PostgreSQL 17          pgvector (768d)            Gemini Embeddings   │
│   (Agents, Chats,        (Semantic search           (text-embedding-004) │
│    Users, Sessions)       with vectors)                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📡 API Reference

### Agents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/agents/create/pdf` | Create agent from PDF |
| `POST` | `/api/v1/agents/create/text` | Create agent from text |
| `GET` | `/api/v1/agents` | List all agents |
| `GET` | `/api/v1/agents/{id}` | Get agent details |
| `DELETE` | `/api/v1/agents/{id}` | Delete agent |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/chat/sessions` | Create chat session |
| `POST` | `/api/v1/chat/sessions/{id}/messages` | Send message |
| `GET` | `/api/v1/chat/sessions/{id}` | Get session history |

### Policies

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/policies/ingest/pdf` | Ingest PDF policy |
| `POST` | `/api/v1/policies/ingest/text` | Ingest text policy |
| `GET` | `/api/v1/policies` | List policies |

### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/search?q={query}` | Semantic search |
| `GET` | `/api/v1/search/stats` | Vector store statistics |

> 📚 Full API documentation available at `/docs` when running the server.

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|------------|---------|
| **FastAPI** | High-performance async API framework |
| **LangGraph** | Agent orchestration & reasoning loop |
| **PostgreSQL 17** | Primary database |
| **pgvector** | Vector similarity search |
| **SQLAlchemy** | ORM & database abstraction |

### AI/ML
| Technology | Purpose |
|------------|---------|
| **Gemini 2.0 Flash** | LLM for responses & classification |
| **Gemini text-embedding-004** | 768d embeddings (2048 token context) |
| **PaddleOCR** | OCR for scanned documents |
| **PyMuPDF** | PDF text extraction |

### Frontend
| Technology | Purpose |
|------------|---------|
| **Next.js 14** | React framework with App Router |
| **TypeScript** | Type-safe JavaScript |
| **Tailwind CSS** | Utility-first styling |
| **Lucide Icons** | Beautiful icons |

---

## 📁 Project Structure

```
InsurAI/
├── app/                      # Backend application
│   ├── api/v1/              # API endpoints
│   │   ├── agents.py        # Agent CRUD
│   │   ├── chat.py          # Chat sessions
│   │   ├── policies.py      # Policy ingestion
│   │   └── search.py        # Semantic search
│   ├── services/            # Business logic
│   │   ├── coverage_agent.py    # LangGraph reasoning loop
│   │   ├── chat_service.py      # Chat orchestration
│   │   ├── llm_service.py       # LLM abstraction
│   │   ├── ocr_engine.py        # PDF/OCR processing
│   │   └── vector_store/        # Embeddings & search
│   ├── core/                # Config & security
│   └── db/                  # Database models
├── frontend/                # Next.js frontend
│   └── src/app/            # App router pages
├── docs/                    # Documentation
├── tests/                   # Test suite
└── scripts/                 # Utility scripts
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_coverage_agent.py -v
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run linting
flake8 app/

# Run type checking
mypy app/
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent orchestration
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - OCR engine
- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity for PostgreSQL
- [Google Gemini](https://ai.google.dev/) - LLM & embeddings

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/ohadOrbach">Ohad Orbach</a>
</p>

