# InsurAI - Technical Summary

> **What exists and works TODAY** - End-to-end system documentation

---

## 🎯 What This System Does

InsurAI takes insurance policy documents (PDF or text), processes them, and allows users to ask natural language questions about their coverage. The AI responds with accurate, cited answers.

**Example:**
```
User: "Is my engine covered?"
AI: "✅ COVERED - Your engine is covered with a $400 deductible 
     and $15,000 cap. [Page 12, Section: Engine Coverage]"
```

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                                 │
│                     Next.js Frontend (localhost:3000)                    │
│         Agent Cards → Chat Interface → Real-time Responses               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           BACKEND API                                    │
│                    FastAPI (localhost:8000)                              │
│                                                                          │
│   /api/v1/agents     → Create/List/Delete agents                        │
│   /api/v1/chat       → Chat sessions and messages                       │
│   /api/v1/coverage   → Direct coverage checks                           │
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
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                                      │
│                                                                          │
│   PostgreSQL 17          pgvector                 SQLAlchemy             │
│   (User data,            (Vector embeddings       (ORM)                  │
│    Agents, Chats)         for semantic search)                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📥 PIPELINE 1: Policy Ingestion

**What happens when you upload a policy document:**

```
PDF Upload
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 1: OCR / TEXT EXTRACTION                                           │
│ File: app/services/ocr_engine.py                                        │
│                                                                          │
│ • If PDF has native text → Extract directly using PyMuPDF (fast)        │
│ • If PDF is scanned/image → Use PaddleOCR to recognize text             │
│ • Output: Raw text + page numbers + text block positions                │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 2: TEXT CLASSIFICATION & CHUNKING                                  │
│ File: app/services/vector_store/policy_vectorizer.py                    │
│                                                                          │
│ • Split text into chunks (~500-1000 characters each)                    │
│ • Detect section titles (ALL CAPS, "1. DEFINITIONS", etc.)              │
│ • Auto-classify each chunk:                                             │
│   - EXCLUSION: "not covered", "excluded", "does not cover"              │
│   - INCLUSION: "we will pay", "coverage includes"                       │
│   - DEFINITION: "means", "defined as"                                   │
│   - LIMITATION: "limit", "maximum", "deductible"                        │
│   - PROCEDURE: "must", "required", "notify"                             │
│ • Attach metadata: page_number, section_title, chunk_type               │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 3: EMBEDDING GENERATION                                            │
│ File: app/services/vector_store/embeddings.py                           │
│                                                                          │
│ • Convert each text chunk into a 384-dimensional vector                 │
│ • Using: Sentence Transformers (all-MiniLM-L6-v2)                       │
│ • Optional: OpenAI text-embedding-3-small (1536 dim, 8k context)        │
│                                                                          │
│ Example: "Engine coverage includes pistons" → [0.23, -0.15, 0.87, ...]  │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 4: VECTOR STORAGE                                                  │
│ File: app/services/vector_store/pgvector_store.py                       │
│                                                                          │
│ • Store in PostgreSQL with pgvector extension                           │
│ • Each chunk stored with:                                               │
│   - id, text, chunk_type, policy_id                                     │
│   - page_number, section_title                                          │
│   - embedding (384 or 1536 floats)                                      │
│ • IVFFlat index for fast similarity search                              │
│                                                                          │
│ Result: Policy is now searchable! 📊                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

**Database Tables Created:**

| Table | Purpose |
|-------|---------|
| `agents` | Stores agent metadata (name, policy_id, color) |
| `policies` | Policy document metadata |
| `vector_chunks` | Text chunks with embeddings |
| `chat_sessions` | Conversation sessions |
| `chat_messages` | Individual messages |
| `users` | User accounts |

---

## 💬 PIPELINE 2: Chat / Question Answering

**What happens when you ask a question:**

```
User: "Is intentional damage covered?"
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 1: INTENT CLASSIFICATION                                           │
│ File: app/services/coverage_agent.py → _classify_intent()               │
│                                                                          │
│ • Analyze the question type:                                            │
│   - CHECK_COVERAGE: "Is X covered?", "Does my policy cover..."         │
│   - EXPLAIN_TERMS: "What does X mean?", "Define..."                    │
│   - GET_LIMITS: "What's the deductible?", "What's the cap?"            │
│   - GENERAL_INFO: Other policy questions                                │
│                                                                          │
│ • Extract items to check: ["intentional damage"]                        │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 2: SEMANTIC SEARCH (RAG Retrieval)                                 │
│ File: app/services/vector_store/policy_vectorizer.py → search()         │
│                                                                          │
│ • Convert question to embedding vector                                  │
│ • Search pgvector for similar chunks (cosine similarity)               │
│ • Return top 8-10 relevant chunks                                       │
│                                                                          │
│ Example results:                                                        │
│ [                                                                        │
│   {text: "EXCLUSIONS: intentional damage...", score: 0.87, type: excl} │
│   {text: "Coverage includes...", score: 0.72, type: incl}              │
│ ]                                                                        │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 3: EXCLUSION CHECK (THE GUARDRAIL) ⚠️                              │
│ File: app/services/coverage_agent.py → _check_exclusions_node()         │
│                                                                          │
│ THIS IS THE CRITICAL STEP - "Air Canada Defense"                        │
│                                                                          │
│ • For each retrieved chunk, ask the LLM:                                │
│   "Does this text EXPLICITLY exclude 'intentional damage'?"            │
│                                                                          │
│ • LLM evaluates semantically (no regex!)                                │
│ • Handles ALL phrasing variations:                                      │
│   - "We do not insure intentional damage"                              │
│   - "The following are not included: intentional acts"                 │
│   - "Exceptions to coverage: deliberate damage"                        │
│                                                                          │
│ • Returns: { is_excluded: true, confidence: 0.95, reason: "..." }      │
│                                                                          │
│ If EXCLUDED → STOP HERE. Return "NOT COVERED" with citation.            │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼ (only if NOT excluded)
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 4: INCLUSION CHECK                                                 │
│ File: app/services/coverage_agent.py → _check_inclusions_node()         │
│                                                                          │
│ • Search for coverage language                                          │
│ • Ask LLM: "Does this text provide COVERAGE for this item?"            │
│ • Returns: { is_covered: true, confidence: 0.82, reason: "..." }       │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 5: FINANCIAL CONTEXT                                               │
│ File: app/services/coverage_agent.py → _get_financial_context_node()    │
│                                                                          │
│ • Search for deductibles, caps, limits                                  │
│ • Extract: deductible=$400, cap=$15,000                                │
└─────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 6: RESPONSE GENERATION                                             │
│ File: app/services/coverage_agent.py → _build_response_node()           │
│                                                                          │
│ • Compile all context:                                                  │
│   - Coverage decision (COVERED/NOT_COVERED/CONDITIONAL)                 │
│   - Relevant policy excerpts                                            │
│   - Financial terms                                                     │
│   - Citations (page numbers, section titles)                            │
│                                                                          │
│ • Send to LLM (Google Gemini) for natural language response             │
│                                                                          │
│ Final Output:                                                           │
│ "❌ NOT COVERED - Intentional damage is explicitly excluded in your    │
│  policy. [Page 8, Section: Exclusions] Quote: 'We do not insure        │
│  damage you intentionally cause...'"                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Key Components Explained

### 1. OCR Engine (`app/services/ocr_engine.py`)

**What it does:** Extracts text from PDF files.

**How it works:**
```python
# For digital PDFs (has selectable text)
PyMuPDF (fitz) → Direct text extraction → Fast!

# For scanned PDFs (images)
PaddleOCR → Deep learning OCR → Slower but works on images
```

### 2. Policy Vectorizer (`app/services/vector_store/policy_vectorizer.py`)

**What it does:** Converts policy text into searchable vectors.

**Key methods:**
- `vectorize_policy()` - Process structured PolicyDocument
- `vectorize_raw_text()` - Process raw text with smart chunking
- `search()` - Find similar chunks by query
- `search_coverage()` - Search specifically for inclusions/exclusions

### 3. Coverage Agent (`app/services/coverage_agent.py`)

**What it does:** The "brain" that decides coverage with LLM reasoning.

**The LangGraph Workflow:**
```
ROUTER → EXCLUSION_CHECK → INCLUSION_CHECK → FINANCIAL_CONTEXT → RESPONSE
           │
           └─► If excluded, skip to RESPONSE immediately
```

### 4. LLM Service (`app/services/llm_service.py`)

**What it does:** Manages AI model interactions.

**Supported providers:**
| Provider | Model | When to use |
|----------|-------|-------------|
| Google | gemini-2.5-flash | Default (fast, cheap) |
| OpenAI | gpt-4o | Higher accuracy |
| Anthropic | claude-3-5-sonnet | Alternative |
| Mock | N/A | Testing without API |

### 5. Vector Store (`app/services/vector_store/`)

**What it does:** Stores and searches text embeddings.

**Components:**
```
pgvector_store.py    → PostgreSQL + pgvector (production)
memory_store.py      → In-memory (development)
embeddings.py        → Generate embeddings (MiniLM/OpenAI)
base.py              → Abstract interfaces
```

---

## 🗄️ Database Schema

```sql
-- Agents table
CREATE TABLE agents (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    policy_id VARCHAR(50),
    agent_type VARCHAR(20),  -- 'personal' or 'shared'
    status VARCHAR(20),
    color VARCHAR(7),
    created_at TIMESTAMP
);

-- Vector chunks (pgvector)
CREATE TABLE vector_chunks (
    id VARCHAR PRIMARY KEY,
    text TEXT,
    chunk_type VARCHAR(50),
    policy_id VARCHAR(50),
    page_number INTEGER,
    section_title VARCHAR(200),
    chunk_metadata JSONB,
    embedding VECTOR(384),  -- or 1536 for OpenAI
    created_at TIMESTAMP
);

-- Chat sessions
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY,
    agent_id INTEGER,
    user_id INTEGER,
    created_at TIMESTAMP
);

-- Chat messages
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY,
    session_id UUID,
    role VARCHAR(20),  -- 'user' or 'assistant'
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP
);
```

---

## 🔄 API Endpoints

### Agents
```
POST   /api/v1/agents/create/pdf    → Upload PDF, create agent
POST   /api/v1/agents/create/text   → Create from text
POST   /api/v1/agents/create/demo   → Create demo agent
GET    /api/v1/agents               → List all agents
GET    /api/v1/agents/{id}          → Get single agent
DELETE /api/v1/agents/{id}          → Delete agent
```

### Chat
```
POST   /api/v1/chat/sessions                    → Create chat session
GET    /api/v1/chat/sessions/{id}               → Get session
POST   /api/v1/chat/sessions/{id}/messages      → Send message, get response
```

### Search
```
POST   /api/v1/search/{policy_id}   → Semantic search in policy
```

---

## ⚙️ Configuration

### Environment Variables (`.env`)

```bash
# Database
DATABASE_URL=postgresql://insur_user:insur_password@localhost:5432/insur

# Vector Store
VECTOR_STORE_TYPE=pgvector    # or "memory"

# Embeddings
EMBEDDING_PROVIDER=sentence_transformer   # or "openai"
EMBEDDING_MODEL=all-MiniLM-L6-v2          # or "text-embedding-3-small"

# LLM
LLM_PROVIDER=google
GOOGLE_API_KEY=your-api-key

# OCR
USE_MOCK_OCR=False
```

---

## 🚀 How to Run

### Backend
```bash
cd /Users/ohadorbach/Documents/insur
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm run dev
# Opens at http://localhost:3000
```

### Database
```bash
# PostgreSQL must be running
brew services start postgresql@17
```

---

## 📊 Data Flow Summary

```
┌──────────┐     ┌───────────┐     ┌──────────────┐     ┌─────────────┐
│   PDF    │────▶│    OCR    │────▶│   Chunking   │────▶│  Embeddings │
│  Upload  │     │  Extract  │     │  & Classify  │     │   (384d)    │
└──────────┘     └───────────┘     └──────────────┘     └─────────────┘
                                                               │
                                                               ▼
┌──────────┐     ┌───────────┐     ┌──────────────┐     ┌─────────────┐
│ Response │◀────│    LLM    │◀────│   Coverage   │◀────│   pgvector  │
│ + Cite   │     │  Gemini   │     │    Agent     │     │   Search    │
└──────────┘     └───────────┘     └──────────────┘     └─────────────┘
                                          ▲
                                          │
                                   ┌──────────────┐
                                   │  User Query  │
                                   │ "Is X covered?"│
                                   └──────────────┘
```

---

## 🎯 Why This Architecture?

| Decision | Why |
|----------|-----|
| **pgvector** | Persistent, scales to millions, ACID transactions |
| **LLM for exclusions** | No brittle regex, handles all carrier phrasing |
| **LangGraph** | Explicit reasoning loop, auditable decisions |
| **Chunk classification** | Faster targeted retrieval (exclusions first!) |
| **Citations** | Legal defensibility ("Air Canada defense") |

---

*Last updated: December 28, 2025*

