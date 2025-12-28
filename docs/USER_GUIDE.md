# Universal Insurance AI Agent - User Guide

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.0.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/Status-Production%20Ready-green" alt="Status">
  <img src="https://img.shields.io/badge/AI-Gemini%202.5-orange" alt="AI">
</p>

## 🎯 What is Universal Insurance AI?

Universal Insurance AI is your **personal insurance policy assistant**. Instead of reading through 20+ pages of complex policy documents, simply ask questions in plain English and get instant, accurate answers about your coverage.

**New in v2.0:** Create personalized AI agents for each of your insurance policies!

---

## 🚀 Getting Started

### Step 1: Access the Application

Open your web browser and navigate to:
```
http://localhost:3000
```

### Step 2: Create Your First Agent

1. Click **"My Agents"** in the sidebar
2. Click **"New Agent"** or **"Quick Demo"**
3. Upload your policy PDF or use demo data
4. Your personalized agent is ready!

### Step 3: Start Chatting

Click on your agent card to open the chat interface. Ask anything about your coverage!

---

## 🤖 Understanding Agents

### What is an Agent?

An **Agent** is a personalized AI assistant that understands one specific insurance policy. Each agent:
- Knows your policy's coverage, exclusions, and limits
- Remembers your conversation history
- Provides accurate, policy-specific answers

### Personal Agents (B2C)

For individual users:
- **One agent per policy** you own
- Includes your personal details
- Private to your account
- Example: "My Car Insurance", "Home Policy Agent"

### Shared Agents (B2B)

For businesses and organizations:
- **Generic policy** without personal data
- Serves multiple users
- User-specific limitations injected per session
- Example: "Company Health Plan Agent"

---

## 📋 Creating an Agent

### From PDF Upload

1. Go to **My Agents** → **New Agent**
2. Select **PDF Upload** tab
3. Drag & drop your policy PDF (or click to browse)
4. Enter a name for your agent (e.g., "My Car Insurance")
5. Choose a color theme
6. Click **"Create Agent"**
7. Wait for processing (30-60 seconds)

### From Text

1. Go to **My Agents** → **New Agent**
2. Select **Paste Text** tab
3. Paste your policy document text
4. Enter agent details
5. Click **"Create Agent"**

### Quick Demo

For testing without uploading:
1. Go to **My Agents**
2. Click **"Quick Demo"**
3. A demo agent with sample policy is created instantly

---

## 💬 Chatting with Your Agent

### Starting a Conversation

1. Go to **My Agents**
2. Click on an agent card
3. You'll see a welcome message from your agent
4. Type your question and press Enter

### What You Can Ask

**Coverage Questions:**
- *"Is my engine covered?"*
- *"What about transmission repairs?"*
- *"Does my policy cover roadside assistance?"*

**Exclusion Questions:**
- *"What is NOT covered?"*
- *"Are timing belts excluded?"*
- *"What are the main exclusions?"*

**Financial Questions:**
- *"What is my deductible for engine repairs?"*
- *"What's the coverage cap for electrical work?"*
- *"How much will I pay out of pocket?"*

**Policy Information:**
- *"When does my policy expire?"*
- *"What are my obligations?"*
- *"Which service centers can I use?"*

---

## 🔍 Understanding Responses

### ✅ Covered
```
Status: COVERED
The item is explicitly included in your policy coverage.
```
**Example:** "Pistons are covered under your Engine coverage with a 400 NIS deductible."

### ❌ Not Covered
```
Status: NOT_COVERED
The item is explicitly excluded from your policy.
```
**Example:** "Turbochargers are listed as an exclusion and are not covered."

### ⚠️ Conditional
```
Status: CONDITIONAL
Coverage depends on specific conditions being met.
```
**Example:** "Roadside assistance is covered, limited to 4 services per year."

### ❓ Unknown
```
Status: UNKNOWN
The item was not found in the policy. Contact your provider.
```

---

## 👥 B2B Features (For Organizations)

### Shared Agents

Organizations can create shared agents that serve multiple users:

1. Create agent with `agent_type: "shared"`
2. Upload a generic policy template (without personal data)
3. Multiple users can chat with the same agent

### User Limitations

For B2B scenarios, administrators can add user-specific limitations:

**Examples:**
- "User has used 3 of 4 annual roadside assists"
- "User's deductible is 600 NIS due to claim history"
- "User is in 30-day grace period"

These limitations are automatically injected into the conversation context, so the agent knows about user-specific constraints.

**Adding Limitations (API):**
```
POST /api/v1/agents/{agent_id}/limitations
{
  "limitation_type": "claim_limit",
  "title": "Annual Claim Limit",
  "description": "User has used 3 of 4 annual claims",
  "severity": "warning",
  "current_value": "3",
  "max_value": "4"
}
```

---

## 📱 Navigation

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | Quick chat access |
| **My Agents** | `/agents` | View and manage all agents |
| Agent Chat | `/agents/{id}/chat` | Chat with specific agent |
| Coverage Check | `/coverage` | Quick coverage lookup |
| Policies | `/policies` | View uploaded policies |
| Upload | `/upload` | Upload new policy |

---

## 🔐 Account & Security

### Creating an Account
1. Click **"Sign Up"** on the login page
2. Enter your email and create a password
3. Verify your email address
4. Log in to access your agents

### Your Data is Secure
- All policy documents are encrypted
- Agents are private to your account
- We never share your information
- You can delete agents and data anytime

---

## 📱 Mobile Usage

The application is fully responsive:
- 📱 Smartphones (iOS/Android browsers)
- 📱 Tablets
- 💻 Desktop computers

---

## ❓ FAQ

### Q: How many agents can I create?
**A:** Unlimited for personal use. B2B plans have configurable limits.

### Q: Can I have multiple agents for the same policy?
**A:** Yes, but typically one agent per policy is sufficient.

### Q: How accurate are the answers?
**A:** The AI analyzes your actual policy document. Accuracy depends on document quality.

### Q: Can I trust coverage decisions?
**A:** The AI provides guidance. For official decisions, contact your insurance provider.

### Q: Is my policy document stored securely?
**A:** Yes. All documents are encrypted. Only you can access your agents.

### Q: Can I export chat history?
**A:** Yes. Each chat session can be exported.

### Q: What happens if I delete an agent?
**A:** The agent is archived. You can restore it or permanently delete.

---

## 🔒 Technical Features (v2.1)

### Persistent Storage
Your policy data is stored in **PostgreSQL with pgvector**, ensuring:
- ✅ Data survives server restarts
- ✅ Fast vector similarity search
- ✅ Scales to millions of documents
- ✅ ACID transactions for reliability

### Smart Coverage Detection
Our AI uses **LLM-based semantic evaluation** instead of simple keyword matching:
- ✅ Understands different policy phrasings
- ✅ Handles "We do not insure...", "Excluded items include...", etc.
- ✅ Provides confidence scores for decisions
- ✅ Explains reasoning with citations

### Advanced Embeddings (Optional)
For enterprise users, we support **OpenAI embeddings**:
- 8,000 token context window (vs 512 for basic)
- Better understanding of complex legal text
- Superior semantic search accuracy

---

## 🆘 Need Help?

### Contact Support
- Email: support@universalinsurance.ai
- Phone: 1-800-INSUR-AI

### Report Issues
- Use the feedback button in the app
- Email: bugs@universalinsurance.ai

---

## 📝 Tips for Best Results

1. **Be specific** - Ask about specific items (e.g., "pistons" instead of "engine parts")
2. **One question at a time** - The AI works best with focused questions
3. **Name agents clearly** - Use descriptive names like "2024 Car Insurance"
4. **Check financial context** - Always note the deductible and cap information
5. **Use the right agent** - Make sure you're chatting with the correct policy's agent

---

## 🔄 User Flow Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   1️⃣  CREATE AGENT                                              │
│   ─────────────────                                             │
│   My Agents → New Agent → Upload PDF → Name & Color             │
│                                                                 │
│   2️⃣  PROCESSING                                                │
│   ────────────                                                  │
│   OCR extracts text → AI classifies coverage → Agent ready      │
│                                                                 │
│   3️⃣  CHAT                                                      │
│   ─────                                                         │
│   Click agent → Ask questions → Get instant answers             │
│                                                                 │
│   4️⃣  MANAGE                                                    │
│   ───────                                                       │
│   Edit agent details → View stats → Archive when done           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

<p align="center">
  <strong>Universal Insurance AI</strong><br>
  Making insurance simple, one agent at a time.
</p>
