# Product Requirements Document (PRD): Universal Insurance AI Agent

**Version:** 1.0  
**Status:** Draft  
**Date:** 2025-12-26  
**Owner:** Product Team

---

## 1. Executive Summary
The **Universal Insurance AI Agent** is a RAG-based (Retrieval-Augmented Generation) conversational platform. It ingests unstructured policy documents (PDFs) and converts them into a structured, queryable knowledge base. Its primary goal is to resolve information asymmetry by allowing users to ask natural language questions about coverage, exclusions, and costs with high legal accuracy.

## 2. Problem Statement
* [cite_start]**Opacity:** Policyholders rarely understand the specific "Exclusions" in their 20+ page contracts[cite: 177, 178].
* [cite_start]**Support Load:** Agents face repetitive queries regarding deductibles and service caps[cite: 40, 67].
* [cite_start]**LLM Hallucination:** Standard LLMs fail to distinguish between "General Insurance" knowledge and specific "Contractual" constraints (e.g., distinguishing between accident insurance and mechanical warranty [cite: 1, 62]).

## 3. Functional Requirements

### 3.1 Policy Ingestion Engine (ETL)
The system must ingest PDF/Image files and perform the following:
* [cite_start]**OCR & Layout Preservation:** Extract text while maintaining the relationship between labels and values (e.g., "Customer ID" next to "443534234")[cite: 18, 20].
* **Semantic Segmentation:** Classify text blocks into:
    * `Identity_Data` (Name, Vehicle, ID)
    * [cite_start]`Coverage_Inclusions` (e.g., Engine, Gearbox) [cite: 165, 166]
    * [cite_start]`Coverage_Exclusions` (e.g., Turbo, Timing Belt) [cite: 178, 179]
    * [cite_start]`Financial_Logic` (Deductibles, Caps, Expiration) [cite: 40, 188]

### 3.2 The "Coverage Guardrail" Logic
To prevent liability, the AI must strictly follow this decision tree:
1.  [cite_start]**Check Exclusions First:** If a requested part/service appears in the Exclusion list, return `Negative` immediately[cite: 181].
2.  **Check Inclusions Second:** Only if the item is explicitly included, check for conditions.
3.  [cite_start]**Check Conditionals:** Verify if the user has remaining credits (e.g., "2 treatments per year") or is within mileage limits[cite: 146, 188].

### 3.3 Context-Aware Financials
The AI must append financial context to every positive answer:
* [cite_start]**Deductibles:** Quote the specific co-pay (e.g., 400 NIS per visit).
* [cite_start]**Exceptions:** Quote specific rates for special items (e.g., Battery replacement at 300 NIS)[cite: 189].

---

## 4. Technical Architecture

### 4.1 Tech Stack Recommendation
* **Backend:** Python (FastAPI)
* **OCR:** AWS Textract / Azure Document Intelligence (for table extraction)
* **LLM:** GPT-4o / Claude 3.5 Sonnet (for logic reasoning)
* **Database:** * PostgreSQL (Structured User/Policy Data)
    * Pinecone/Milvus (Vector Store for "Terms & Conditions" text chunks)

### 4.2 Data Schema (Target Output)

The ingestion pipeline must transform the PDF into this JSON structure:

```json
{
  "policy_meta": {
    "policy_id": "String",
    "provider_name": "String",
    "policy_type": "String", // e.g., "Mechanical Warranty", "Health HMO"
    "status": "Active | Suspended | Expired",
    "validity_period": {
      "start_date": "ISO8601",
      "end_date_calculated": "ISO8601",
      "termination_condition": "String" // e.g., "Earlier of 24 months or 40k km"
    }
  },

  "client_obligations": {
    "description": "Conditions the client MUST fulfill for the policy to remain valid.",
    "mandatory_actions": [
      {
        "action": "String", // e.g., "Routine Maintenance"
        "condition": "String", // e.g., "According to manufacturer schedule"
        "grace_period": "String", // e.g., "Up to 1,500km overdue allowed"
        "penalty_for_breach": "String" // e.g., "Void warranty immediately"
      }
    ],
    "payment_terms": {
      "amount": "Float",
      "frequency": "Monthly | Annual",
      "method": "String" // e.g., "Credit Card Standing Order"
    },
    "restrictions": [
      "String" // e.g., "Do not install LPG systems", "Do not go to unauthorized providers"
    ]
  },

  "coverage_details": [
    {
      "category": "String", // e.g., "Engine", "Dental", "Plumbing"
      "items_included": [
        "String" // e.g., "Pistons", "Cylinder Head"
      ],
      "specific_limitations": "String", // e.g., "Excludes damage from overheating due to lack of fluids"
      "financial_terms": {
        "deductible": "Float", // The co-pay for this specific category
        "coverage_cap": "Float | String" // e.g., "Unlimited" or "Up to 5000 NIS"
      }
    },
    {
      "category": "String", // e.g., "Roadside Assistance"
      "items_included": ["Jumpstart", "Tire Change"],
      "specific_limitations": "Does NOT include towing (Graph & Go only)",
      "financial_terms": {
        "deductible": 0
      }
    }
  ],

  "service_network": {
    "description": "Approved suppliers and providers.",
    "network_type": "Closed | Open | Hybrid", // "Closed" means specific list only
    "approved_suppliers": [
      {
        "name": "String", // e.g., "Hatzev Trade"
        "service_type": "String", // e.g., "Tire Repair"
        "contact_info": "String"
      },
      {
        "name": "String", // e.g., "Shlomo Service Centers"
        "service_type": "String", // e.g., "General Mechanics"
        "contact_info": "String"
      }
    ],
    "access_method": "String" // e.g., "Must book via App", "Call *9406"
  }
}