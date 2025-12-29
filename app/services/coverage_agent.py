"""
Coverage Agent - LangGraph-based Reasoning Loop for Insurance Queries.

OPTIMIZED FLOW (3 LLM calls instead of 5):
1. Router → Classify intent + extract items
2. Retrieve → Fetch relevant chunks + ALWAYS include definitions
3. Exclusion Check → GATEKEEPER: If excluded, stream denial immediately
4. Reasoning → MERGED: Check inclusion AND extract financials in ONE call
5. Response → Stream final answer with citations

Key optimizations:
- Merged inclusion + financial checks to reduce latency
- Definitions always injected for context
- Early exit on exclusion detection
- WHOLE-DOC MODE: For small policies (<30 pages), skip RAG and pass entire doc to LLM
- PARALLEL PROCESSING: Multiple items checked concurrently via asyncio.gather()
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional, TypedDict

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


# =============================================================================
# State Definition
# =============================================================================

class QueryIntent(str, Enum):
    """Classified intent of user query."""
    CHECK_COVERAGE = "check_coverage"  # "Is X covered?"
    EXPLAIN_TERMS = "explain_terms"    # "What does X mean?"
    GET_LIMITS = "get_limits"          # "What are the deductibles?"
    GENERAL_INFO = "general_info"      # General policy questions
    UNKNOWN = "unknown"


class CoverageDecision(str, Enum):
    """Final coverage decision with explicit states."""
    COVERED = "covered"
    NOT_COVERED = "not_covered"       # Explicitly excluded
    CONDITIONAL = "conditional"        # Covered with conditions
    REQUIRES_REVIEW = "requires_review"  # Edge case, needs human
    UNKNOWN = "unknown"                # Cannot determine


@dataclass
class SearchResult:
    """A single search result with citation info."""
    text: str
    score: float
    chunk_type: str  # "exclusion", "inclusion", "definition", etc.
    policy_id: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    category: Optional[str] = None


@dataclass 
class CoverageCheckResult:
    """Result of checking a specific item's coverage."""
    item: str
    decision: CoverageDecision
    reason: str
    exclusion_found: bool = False
    exclusion_text: Optional[str] = None
    inclusion_found: bool = False
    inclusion_text: Optional[str] = None
    deductible: Optional[float] = None
    coverage_cap: Optional[str] = None
    citations: list[str] = field(default_factory=list)


class AgentState(TypedDict):
    """State passed between nodes in the graph."""
    # Input
    user_message: str
    policy_id: str
    user_id: Optional[int]
    agent_id: Optional[int]
    
    # Whole-Doc Mode (for small policies)
    full_policy_text: Optional[str]  # Full policy text if small enough
    use_whole_doc_mode: bool         # Flag to use simplified flow
    
    # Classification
    intent: str
    items_to_check: list[str]
    
    # Retrieved context
    retrieved_chunks: list[dict]
    definitions_context: str
    
    # Search Results (with citations)
    exclusion_results: list[dict]
    inclusion_results: list[dict]
    financial_results: list[dict]
    user_limitations: list[dict]
    
    # Decision
    coverage_checks: list[dict]
    final_decision: str
    
    # Output
    response: str
    citations: list[str]
    reasoning_trace: list[str]  # For debugging/audit


# =============================================================================
# Coverage Agent Implementation
# =============================================================================

class CoverageAgent:
    """
    LangGraph-based agent for coverage determination.
    
    Key principle: ALWAYS check exclusions first (the guardrail).
    """
    
    def __init__(
        self,
        vectorizer,  # PolicyVectorizer
        llm,         # BaseLLM
    ):
        self.vectorizer = vectorizer
        self.llm = llm
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """
        Build the OPTIMIZED LangGraph workflow.
        
        Two Modes:
        1. WHOLE-DOC MODE (small policies <30 pages):
           Router → whole_doc_response (1 LLM call with full document)
           
        2. RAG MODE (large policies):
           Router → Retrieve → Exclusion → Reasoning → Response
        
        Optimizations:
        - Whole-doc mode skips chunking entirely for small policies
        - Retrieval includes definitions for context
        - Inclusion + Financial merged into single Reasoning node
        - Early exit if excluded
        """
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("router", self._router_node)
        workflow.add_node("whole_doc_response", self._whole_doc_response_node)  # NEW: Full doc mode
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("check_exclusions", self._check_exclusions_node)
        workflow.add_node("reasoning", self._reasoning_node)
        workflow.add_node("build_response", self._build_response_node)
        
        # Set entry point
        workflow.set_entry_point("router")
        
        # Router → Whole-Doc OR Retrieve based on policy size
        workflow.add_conditional_edges(
            "router",
            self._route_by_policy_size,
            {
                "whole_doc": "whole_doc_response",  # Small policy → 1 LLM call
                "rag_retrieve": "retrieve",          # Large policy → RAG flow
            }
        )
        
        # Whole-doc response is terminal
        workflow.add_edge("whole_doc_response", END)
        
        # Retrieve → Exclusion Check (for coverage) or Response (for other intents)
        workflow.add_conditional_edges(
            "retrieve",
            self._route_after_retrieve,
            {
                "check_exclusions": "check_exclusions",
                "direct_response": "build_response",
            }
        )
        
        # Exclusion check decides next step (GATEKEEPER)
        workflow.add_conditional_edges(
            "check_exclusions",
            self._route_after_exclusion_check,
            {
                "excluded": "build_response",    # STOP - item is excluded
                "not_excluded": "reasoning",     # Continue to merged reasoning
            }
        )
        
        # Reasoning → Response (single step, no more financial node)
        workflow.add_edge("reasoning", "build_response")
        
        # Response is the end
        workflow.add_edge("build_response", END)
        
        return workflow.compile()
    
    # =========================================================================
    # Node Implementations
    # =========================================================================
    
    async def _router_node(self, state: AgentState) -> AgentState:
        """
        Router Node: Classify intent and extract items to check.
        """
        state["reasoning_trace"] = state.get("reasoning_trace", [])
        state["reasoning_trace"].append(f"[ROUTER] Processing: {state['user_message'][:50]}...")
        
        # Use LLM to classify intent
        intent, items = await self._classify_intent(state["user_message"])
        
        state["intent"] = intent.value
        state["items_to_check"] = items
        state["reasoning_trace"].append(f"[ROUTER] Intent: {intent.value}, Items: {items}")
        
        return state
    
    async def _retrieve_node(self, state: AgentState) -> AgentState:
        """
        Retrieval Node: Fetch relevant chunks + ALWAYS include definitions.
        
        This ensures the LLM has proper context for policy-specific terms.
        """
        policy_id = state["policy_id"]
        state["reasoning_trace"].append(f"[RETRIEVE] Fetching context for policy {policy_id}...")
        
        # Initialize retrieval results
        state["retrieved_chunks"] = []
        state["definitions_context"] = ""
        
        if not policy_id:
            logger.warning("No policy_id - skipping retrieval")
            return state
        
        # 1. ALWAYS retrieve definitions section for context
        definitions_results = self.vectorizer.search(
            query="definitions terms defined in this policy means refers to",
            policy_id=policy_id,
            top_k=5,
            min_score=0.2,
        )
        
        definitions_text = []
        for r in definitions_results:
            chunk = r.chunk
            if chunk.chunk_type.value in ["definition", "policy_meta"] or "defin" in chunk.text.lower():
                definitions_text.append(chunk.text)
        
        if definitions_text:
            state["definitions_context"] = "\n---\n".join(definitions_text[:3])
            state["reasoning_trace"].append(f"[RETRIEVE] Found {len(definitions_text)} definition chunks")
        
        # 2. Retrieve chunks relevant to the user's query
        query_results = self.vectorizer.search(
            query=state["user_message"],
            policy_id=policy_id,
            top_k=8,
            min_score=0.2,
        )
        
        for r in query_results:
            state["retrieved_chunks"].append({
                "text": r.chunk.text,
                "score": r.score,
                "chunk_type": r.chunk.chunk_type.value,
                "page_number": r.chunk.page_number,
                "section_title": r.chunk.section_title,
            })
        
        state["reasoning_trace"].append(f"[RETRIEVE] Retrieved {len(query_results)} relevant chunks")
        
        return state
    
    async def _check_exclusions_node(self, state: AgentState) -> AgentState:
        """
        CRITICAL GUARDRAIL: Check exclusions FIRST using LLM evaluation.
        
        Uses semantic evaluation to detect exclusions regardless of phrasing,
        since different policies use different wording for the same concept.
        The LLM evaluates each retrieved chunk to determine if it explicitly
        excludes the item being checked.
        
        OPTIMIZATION: Multiple items are checked IN PARALLEL using asyncio.gather()
        for significant latency reduction when users ask about multiple items.
        """
        policy_id = state["policy_id"]
        items_count = len(state["items_to_check"])
        state["reasoning_trace"].append(
            f"[EXCLUSION_CHECK] Starting PARALLEL exclusion search for {items_count} item(s) (policy: {policy_id})..."
        )
        state["exclusion_results"] = []
        state["coverage_checks"] = []
        
        # CRITICAL: Ensure we only search within the specific policy
        if not policy_id:
            logger.warning("⚠️ Coverage Agent: No policy_id - cannot check exclusions!")
            return state
        
        logger.info(f"🔍 Coverage Agent: Parallel exclusion check for {items_count} items in policy_id={policy_id}")
        
        # PARALLEL PROCESSING: Check all items concurrently
        if items_count > 1:
            # Run all item checks in parallel
            tasks = [
                self._check_single_item_exclusion(item, policy_id)
                for item in state["items_to_check"]
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for item, result in zip(state["items_to_check"], results):
                if isinstance(result, Exception):
                    logger.error(f"Exclusion check failed for {item}: {result}")
                    state["reasoning_trace"].append(f"[EXCLUSION_CHECK] ⚠️ Error checking {item}: {str(result)[:50]}")
                    continue
                
                exclusion_hits, coverage_check, trace_msg = result
                state["exclusion_results"].extend(exclusion_hits)
                if coverage_check:
                    state["coverage_checks"].append(coverage_check)
                state["reasoning_trace"].append(trace_msg)
        else:
            # Single item - no need for parallelization overhead
            for item in state["items_to_check"]:
                exclusion_hits, coverage_check, trace_msg = await self._check_single_item_exclusion(item, policy_id)
                state["exclusion_results"].extend(exclusion_hits)
                if coverage_check:
                    state["coverage_checks"].append(coverage_check)
                state["reasoning_trace"].append(trace_msg)
        
        return state
    
    async def _check_single_item_exclusion(
        self, 
        item: str, 
        policy_id: str
    ) -> tuple[list[dict], Optional[dict], str]:
        """
        Check exclusion for a SINGLE item. Designed to be called in parallel.
        
        Returns:
            tuple of (exclusion_hits, coverage_check_dict, trace_message)
        """
        # SPECIAL CASE: User asking about ALL exclusions
        if item == "GENERAL_EXCLUSIONS":
            exclusion_query = "exclusion excluded not covered exception limitation restriction does not include"
            top_k = 15
        else:
            exclusion_query = f"what is not covered excluded exception limitation {item}"
            top_k = 10
        
        results = self.vectorizer.search(
            query=exclusion_query,
            policy_id=policy_id,
            top_k=top_k,
            min_score=0.15,
        )
        
        exclusion_hits = []
        item_excluded = False
        exclusion_text = None
        exclusion_citation = None
        
        # PARALLEL LLM evaluation of chunks for this item
        if item == "GENERAL_EXCLUSIONS":
            # For general query, check all chunks in parallel
            chunk_tasks = [
                self._llm_identify_exclusions_in_chunk(r.chunk.text)
                for r in results
            ]
            chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
            
            for r, chunk_result in zip(results, chunk_results):
                if isinstance(chunk_result, Exception):
                    continue
                has_exclusion, confidence, exclusion_summary = chunk_result
                if has_exclusion:
                    exclusion_hits.append({
                        "text": r.chunk.text,
                        "score": r.score,
                        "chunk_type": r.chunk.chunk_type.value,
                        "category": r.chunk.category,
                        "page_number": r.chunk.page_number,
                        "section_title": r.chunk.section_title,
                        "citation": r.chunk.citation,
                        "metadata": r.chunk.metadata,
                        "llm_confidence": confidence,
                        "llm_reason": exclusion_summary,
                    })
        else:
            # For specific item, check all chunks in parallel
            chunk_tasks = [
                self._llm_evaluate_exclusion(item, r.chunk.text, r.chunk.chunk_type.value)
                for r in results
            ]
            chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
            
            for r, chunk_result in zip(results, chunk_results):
                if isinstance(chunk_result, Exception):
                    continue
                is_exclusion, confidence, reason = chunk_result
                
                if is_exclusion:
                    exclusion_hits.append({
                        "text": r.chunk.text,
                        "score": r.score,
                        "chunk_type": r.chunk.chunk_type.value,
                        "category": r.chunk.category,
                        "page_number": r.chunk.page_number,
                        "section_title": r.chunk.section_title,
                        "citation": r.chunk.citation,
                        "metadata": r.chunk.metadata,
                        "llm_confidence": confidence,
                        "llm_reason": reason,
                    })
                    
                    # High confidence exclusion found
                    if confidence >= 0.8 and not item_excluded:
                        item_excluded = True
                        exclusion_text = r.chunk.text
                        exclusion_citation = r.chunk.citation
        
        # Build coverage check result
        coverage_check = None
        trace_msg = ""
        
        if item == "GENERAL_EXCLUSIONS":
            if exclusion_hits:
                exclusion_summaries = [hit.get("llm_reason", "") for hit in exclusion_hits if hit.get("llm_reason")]
                citations = [f"[Page {hit.get('page_number', '?')}] {hit.get('llm_reason', '')[:100]}..." for hit in exclusion_hits[:5]]
                coverage_check = {
                    "item": "Policy Exclusions",
                    "decision": "info",
                    "reason": f"Found {len(exclusion_hits)} exclusion clause(s) in the policy",
                    "exclusion_found": True,
                    "exclusion_text": "\n\n".join(exclusion_summaries[:5]),
                    "page_number": exclusion_hits[0].get("page_number") if exclusion_hits else None,
                    "section_title": exclusion_hits[0].get("section_title") if exclusion_hits else None,
                    "citations": citations,
                    "llm_reason": f"Found {len(exclusion_hits)} exclusion(s)",
                }
                trace_msg = f"[EXCLUSION_CHECK] Found {len(exclusion_hits)} exclusion clause(s) in policy"
            else:
                coverage_check = {
                    "item": "Policy Exclusions",
                    "decision": "unknown",
                    "reason": "No explicit exclusion clauses found in the policy",
                    "exclusion_found": False,
                    "citations": [],
                    "llm_reason": "",
                }
                trace_msg = f"[EXCLUSION_CHECK] No explicit exclusion clauses found (searched {len(results)} chunks)"
        elif item_excluded:
            citation = f"[{exclusion_citation}] " if exclusion_citation else ""
            coverage_check = {
                "item": item,
                "decision": CoverageDecision.NOT_COVERED.value,
                "reason": "Excluded per LLM analysis",
                "exclusion_found": True,
                "exclusion_text": exclusion_text,
                "page_number": exclusion_hits[0].get("page_number") if exclusion_hits else None,
                "section_title": exclusion_hits[0].get("section_title") if exclusion_hits else None,
                "citations": [f"{citation}{exclusion_text[:150]}..." if exclusion_text else ""],
                "llm_reason": exclusion_hits[0].get("llm_reason", "") if exclusion_hits else "",
            }
            trace_msg = f"[EXCLUSION_CHECK] ❌ {item} EXCLUDED {citation}"
        else:
            trace_msg = f"[EXCLUSION_CHECK] ✓ {item} not found in exclusions (checked {len(results)} chunks)"
        
        return exclusion_hits, coverage_check, trace_msg
    
    async def _llm_evaluate_exclusion(
        self,
        item: str,
        chunk_text: str,
        chunk_type: str,
    ) -> tuple[bool, float, str]:
        """
        Use LLM to semantically evaluate if a chunk excludes an item.
        
        Handles various phrasing patterns used by different insurers to
        express exclusions. Returns confidence score to handle edge cases.
        
        Returns:
            tuple of (is_exclusion: bool, confidence: float, reason: str)
        """
        from app.services.llm_service import LLMMessage
        
        prompt = f"""You are an insurance policy analyst. Analyze this policy text and determine if it EXCLUDES the item "{item}".

POLICY TEXT:
---
{chunk_text[:1500]}
---

TASK: Does this text EXPLICITLY state that "{item}" is NOT covered, excluded, or not insured?

IMPORTANT:
- Only return EXCLUDED if the item is EXPLICITLY mentioned as not covered
- Being near exclusion text is NOT enough - the item must BE the subject of exclusion
- Section headers followed by exclusions do NOT mean the section topic is excluded

Return your analysis as JSON:
{{
    "is_excluded": true/false,
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}

JSON Response:"""

        try:
            messages = [LLMMessage(role="user", content=prompt)]
            response = await self.llm.generate(messages)
            
            # Parse JSON response
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return (
                    result.get("is_excluded", False),
                    result.get("confidence", 0.0),
                    result.get("reason", ""),
                )
        except Exception as e:
            logger.warning(f"LLM exclusion evaluation failed: {e}")
        
        # Default: not excluded
        return (False, 0.0, "evaluation_failed")
    
    async def _llm_identify_exclusions_in_chunk(
        self,
        chunk_text: str,
    ) -> tuple[bool, float, str]:
        """
        Use LLM to identify what exclusions are present in a policy chunk.
        
        Used for general "list all exclusions" queries where no specific
        item is mentioned. Returns a summary of excluded items/scenarios.
        
        Returns:
            tuple of (has_exclusion: bool, confidence: float, exclusion_summary: str)
        """
        from app.services.llm_service import LLMMessage
        
        prompt = f"""You are an insurance policy analyst. Read this policy text and identify any EXCLUSIONS.

POLICY TEXT:
---
{chunk_text[:2000]}
---

TASK: Does this text contain any EXCLUSION clauses (things that are NOT covered)?

Return your analysis as JSON:
{{
    "has_exclusions": true/false,
    "confidence": 0.0-1.0,
    "exclusion_summary": "Brief summary of what is excluded (max 100 words). If no exclusions, say 'No exclusions found in this text.'"
}}

JSON Response:"""

        try:
            messages = [LLMMessage(role="user", content=prompt)]
            response = await self.llm.generate(messages, temperature=0.0)
            
            # Parse JSON response
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return (
                    result.get("has_exclusions", False),
                    result.get("confidence", 0.0),
                    result.get("exclusion_summary", "No exclusions identified"),
                )
        except Exception as e:
            logger.warning(f"LLM exclusion identification failed: {e}")
        
        # Default: no exclusions
        return (False, 0.0, "evaluation_failed")
    
    async def _check_inclusions_node(self, state: AgentState) -> AgentState:
        """
        Check for explicit coverage inclusions using LLM evaluation.
        Only runs if item was NOT excluded in the previous node.
        Uses semantic evaluation for accuracy across different policy formats.
        """
        state["reasoning_trace"].append("[INCLUSION_CHECK] Starting LLM-powered inclusion search...")
        state["inclusion_results"] = []
        
        # Only check items that weren't already excluded
        excluded_items = {
            c["item"] for c in state["coverage_checks"] 
            if c.get("exclusion_found")
        }
        
        items_to_check = [
            item for item in state["items_to_check"]
            if item not in excluded_items
        ]
        
        for item in items_to_check:
            # Search for inclusions with broad query
            inclusion_query = f"what is covered insured protected {item} we will pay"
            
            results = self.vectorizer.search(
                query=inclusion_query,
                policy_id=state["policy_id"],
                top_k=10,
                min_score=0.15,
            )
            
            inclusion_hits = []
            item_covered = False
            inclusion_text = None
            inclusion_citation = None
            
            for r in results:
                chunk = r.chunk
                
                # Ask LLM to evaluate this chunk
                is_inclusion, confidence, reason = await self._llm_evaluate_inclusion(
                    item=item,
                    chunk_text=chunk.text,
                    chunk_type=chunk.chunk_type.value,
                )
                
                if is_inclusion:
                    inclusion_hits.append({
                        "text": chunk.text,
                        "score": r.score,
                        "chunk_type": chunk.chunk_type.value,
                        "category": chunk.category,
                        "page_number": chunk.page_number,
                        "section_title": chunk.section_title,
                        "citation": chunk.citation,
                        "llm_confidence": confidence,
                        "llm_reason": reason,
                    })
                    
                    # High confidence inclusion found
                    if confidence >= 0.7 and not item_covered:
                        item_covered = True
                        inclusion_text = chunk.text
                        inclusion_citation = chunk.citation
                        state["reasoning_trace"].append(
                            f"[INCLUSION_CHECK] LLM found coverage (conf={confidence:.0%}): {reason[:50]}..."
                        )
            
            state["inclusion_results"].extend(inclusion_hits)
            
            # Update or create coverage check
            existing_check = next(
                (c for c in state["coverage_checks"] if c["item"] == item),
                None
            )
            
            citation = f"[{inclusion_citation}] " if inclusion_citation else ""
            
            if existing_check:
                existing_check["inclusion_found"] = item_covered
                existing_check["inclusion_text"] = inclusion_text
                if inclusion_hits:
                    existing_check["page_number"] = inclusion_hits[0].get("page_number")
                if item_covered and not existing_check.get("exclusion_found"):
                    existing_check["decision"] = CoverageDecision.COVERED.value
                    existing_check["reason"] = "Covered per LLM analysis"
                    existing_check["citations"].append(f"{citation}{inclusion_text[:150]}..." if inclusion_text else "")
                    existing_check["llm_reason"] = inclusion_hits[0].get("llm_reason", "") if inclusion_hits else ""
            else:
                state["coverage_checks"].append({
                    "item": item,
                    "decision": CoverageDecision.COVERED.value if item_covered else CoverageDecision.UNKNOWN.value,
                    "reason": "Covered per LLM analysis" if item_covered else "No explicit coverage found",
                    "exclusion_found": False,
                    "inclusion_found": item_covered,
                    "inclusion_text": inclusion_text,
                    "page_number": inclusion_hits[0].get("page_number") if inclusion_hits else None,
                    "citations": [f"{citation}{inclusion_text[:150]}..." if inclusion_text else ""] if item_covered else [],
                    "llm_reason": inclusion_hits[0].get("llm_reason", "") if inclusion_hits else "",
                })
            
            state["reasoning_trace"].append(
                f"[INCLUSION_CHECK] {'✅' if item_covered else '❓'} {item}: "
                f"{'Found coverage' if item_covered else 'No explicit coverage (checked ' + str(len(results)) + ' chunks)'}"
            )
        
        return state
    
    async def _llm_evaluate_inclusion(
        self,
        item: str,
        chunk_text: str,
        chunk_type: str,
    ) -> tuple[bool, float, str]:
        """
        Use LLM to semantically evaluate if a chunk provides coverage for an item.
        
        Returns:
            tuple of (is_covered: bool, confidence: float, reason: str)
        """
        from app.services.llm_service import LLMMessage
        
        prompt = f"""You are an insurance policy analyst. Analyze this policy text and determine if it provides COVERAGE for "{item}".

POLICY TEXT:
---
{chunk_text[:1500]}
---

TASK: Does this text EXPLICITLY state that "{item}" IS covered, insured, or protected?

Consider ALL phrasing variations including:
- "We will pay for..."
- "Coverage includes..."
- "We insure against..."
- "Protection for..."
- Declarations of coverage

IMPORTANT:
- Only return COVERED if the item is EXPLICITLY mentioned as covered
- Generic policy descriptions are NOT conclusive
- The item must BE the subject of coverage, not just mentioned

Return your analysis as JSON:
{{
    "is_covered": true/false,
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}

JSON Response:"""

        try:
            messages = [LLMMessage(role="user", content=prompt)]
            response = await self.llm.generate(messages)
            
            # Parse JSON response
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return (
                    result.get("is_covered", False),
                    result.get("confidence", 0.0),
                    result.get("reason", ""),
                )
        except Exception as e:
            logger.warning(f"LLM inclusion evaluation failed: {e}")
        
        # Default: not covered
        return (False, 0.0, "evaluation_failed")
    
    async def _reasoning_node(self, state: AgentState) -> AgentState:
        """
        MERGED Reasoning Node: Check inclusion AND extract financial terms in ONE LLM call.
        
        This reduces latency by combining what were previously 2 separate nodes.
        The LLM evaluates coverage AND extracts deductibles/limits simultaneously.
        """
        state["reasoning_trace"].append("[REASONING] Checking coverage + extracting financials (merged)...")
        state["inclusion_results"] = state.get("inclusion_results", [])
        state["financial_results"] = []
        
        # Get items not already excluded
        excluded_items = {
            c["item"] for c in state.get("coverage_checks", [])
            if c.get("exclusion_found")
        }
        items_to_check = [
            item for item in state["items_to_check"]
            if item not in excluded_items and item != "GENERAL_EXCLUSIONS"
        ]
        
        if not items_to_check:
            return state
        
        # Build context including definitions
        context_chunks = state.get("retrieved_chunks", [])[:5]
        definitions = state.get("definitions_context", "")
        
        context_text = ""
        if definitions:
            context_text += f"## POLICY DEFINITIONS:\n{definitions}\n\n"
        
        context_text += "## RELEVANT POLICY SECTIONS:\n"
        for i, chunk in enumerate(context_chunks, 1):
            context_text += f"[{i}] {chunk['text'][:500]}...\n\n"
        
        # MERGED LLM call: Check coverage AND extract financials
        from app.services.llm_service import LLMMessage
        
        items_str = ", ".join(items_to_check)
        prompt = f"""You are an insurance policy analyst. Analyze the policy context below.

POLICY CONTEXT:
{context_text[:4000]}

TASK: For each item in [{items_str}], determine:
1. Is it EXPLICITLY covered in this policy?
2. What are the relevant financial terms (deductible, limit, cap)?

Return your analysis as JSON:
{{
    "items": [
        {{
            "item": "item name",
            "is_covered": true/false,
            "confidence": 0.0-1.0,
            "coverage_reason": "brief explanation of coverage status",
            "deductible": "amount if found, null otherwise",
            "coverage_limit": "limit/cap if found, null otherwise",
            "relevant_excerpt": "key policy text supporting this"
        }}
    ]
}}

IMPORTANT:
- Only mark as covered if EXPLICITLY stated in the policy
- Include financial terms if mentioned for the item
- Be specific about which section/page supports your conclusion

JSON Response:"""

        try:
            messages = [LLMMessage(role="user", content=prompt)]
            response = await self.llm.generate(messages, temperature=0.0)
            
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if json_match:
                result = json.loads(json_match.group())
                
                for item_result in result.get("items", []):
                    item_name = item_result.get("item", "")
                    is_covered = item_result.get("is_covered", False)
                    confidence = item_result.get("confidence", 0.0)
                    
                    # Update or create coverage check
                    existing_check = next(
                        (c for c in state["coverage_checks"] if c["item"].lower() == item_name.lower()),
                        None
                    )
                    
                    if existing_check:
                        existing_check["inclusion_found"] = is_covered
                        existing_check["inclusion_text"] = item_result.get("relevant_excerpt", "")
                        if is_covered and not existing_check.get("exclusion_found"):
                            existing_check["decision"] = CoverageDecision.COVERED.value
                            existing_check["reason"] = item_result.get("coverage_reason", "Covered")
                        # Add financial info
                        if item_result.get("deductible"):
                            existing_check["deductible_info"] = item_result["deductible"]
                        if item_result.get("coverage_limit"):
                            existing_check["limit_info"] = item_result["coverage_limit"]
                    else:
                        state["coverage_checks"].append({
                            "item": item_name,
                            "decision": CoverageDecision.COVERED.value if is_covered else CoverageDecision.UNKNOWN.value,
                            "reason": item_result.get("coverage_reason", "No explicit coverage found"),
                            "exclusion_found": False,
                            "inclusion_found": is_covered,
                            "inclusion_text": item_result.get("relevant_excerpt", ""),
                            "deductible_info": item_result.get("deductible"),
                            "limit_info": item_result.get("coverage_limit"),
                            "citations": [],
                            "llm_reason": item_result.get("coverage_reason", ""),
                        })
                    
                    state["reasoning_trace"].append(
                        f"[REASONING] {'✅' if is_covered else '❓'} {item_name}: "
                        f"{item_result.get('coverage_reason', 'No info')[:50]}..."
                    )
                    
        except Exception as e:
            logger.warning(f"Merged reasoning failed: {e}")
            state["reasoning_trace"].append(f"[REASONING] Error: {str(e)[:50]}")
        
        return state
    
    async def _build_response_node(self, state: AgentState) -> AgentState:
        """
        Build the final response with citations and reasoning.
        
        Uses retrieved context including definitions for accurate response.
        """
        state["reasoning_trace"].append("[RESPONSE] Building final response...")
        
        # Compile context for LLM
        context_parts = []
        
        # Include definitions for context (always helpful)
        if state.get("definitions_context"):
            context_parts.append("## POLICY DEFINITIONS:")
            context_parts.append(state["definitions_context"][:1000])
        
        # Coverage decisions
        for check in state.get("coverage_checks", []):
            decision = check.get("decision", "unknown")
            emoji = {
                "covered": "✅",
                "not_covered": "❌", 
                "conditional": "⚠️",
                "unknown": "❓",
            }.get(decision, "❓")
            
            context_parts.append(
                f"{emoji} **{check['item']}**: {decision.upper()}\n"
                f"   Reason: {check.get('reason', 'N/A')}"
            )
            
            if check.get("exclusion_text"):
                context_parts.append(f"   📜 Exclusion: \"{check['exclusion_text'][:150]}...\"")
            if check.get("inclusion_text"):
                context_parts.append(f"   📜 Coverage: \"{check['inclusion_text'][:150]}...\"")
            if check.get("deductible_info"):
                context_parts.append(f"   💰 Deductible: {check['deductible_info']}")
            if check.get("limit_info"):
                context_parts.append(f"   📊 Limit: {check['limit_info']}")
        
        # Retrieved chunks (from new retrieve node)
        retrieved_chunks = state.get("retrieved_chunks", [])
        if retrieved_chunks:
            context_parts.append("\n## RELEVANT POLICY EXCERPTS:")
            for i, chunk in enumerate(retrieved_chunks[:5], 1):
                context_parts.append(f"{i}. [{chunk.get('chunk_type', 'text')}] {chunk['text'][:300]}...")
        
        # Fallback to old-style results if no retrieved chunks
        if not retrieved_chunks:
            all_results = (
                state.get("exclusion_results", [])[:3] +
                state.get("inclusion_results", [])[:3]
            )
            if all_results:
                context_parts.append("\n## RELEVANT POLICY EXCERPTS:")
                for i, r in enumerate(all_results[:5], 1):
                    context_parts.append(f"{i}. [{r.get('chunk_type', 'text')}] {r['text'][:300]}...")
        
        # Build prompt for final response
        context = "\n".join(context_parts)
        
        response = await self._generate_response(
            user_message=state["user_message"],
            intent=state.get("intent", "general_info"),
            context=context,
            coverage_checks=state.get("coverage_checks", []),
        )
        
        state["response"] = response
        state["citations"] = self._extract_citations(state)
        
        return state
    
    async def _whole_doc_response_node(self, state: AgentState) -> AgentState:
        """
        WHOLE-DOC MODE: Process entire policy in one LLM call.
        
        For small policies (<30 pages / ~50k chars), we skip RAG entirely:
        - No chunking → no missing context
        - No retrieval latency
        - Full document in Gemini's context window
        
        This eliminates the "Definitions Blind Spot" and cross-reference issues.
        """
        state["reasoning_trace"] = state.get("reasoning_trace", [])
        state["reasoning_trace"].append("[WHOLE-DOC] Using full document mode (small policy)")
        
        full_text = state.get("full_policy_text", "")
        user_message = state["user_message"]
        intent = state.get("intent", "general_info")
        items = state.get("items_to_check", [])
        
        # Truncate if somehow too long (shouldn't happen with proper threshold)
        MAX_CHARS = 80000  # ~20k tokens, safe for Gemini
        if len(full_text) > MAX_CHARS:
            full_text = full_text[:MAX_CHARS]
            state["reasoning_trace"].append(f"[WHOLE-DOC] Truncated to {MAX_CHARS} chars")
        
        # Build comprehensive prompt with full document
        from app.services.llm_service import LLMMessage
        
        items_str = ", ".join(items) if items else "the user's question"
        
        system_prompt = """You are an expert insurance policy analyst. You have access to the COMPLETE policy document below.

Your task is to answer the user's question accurately based on the policy.

CRITICAL RULES:
1. For EXCLUSION questions: List ALL explicit exclusions you find
2. For COVERAGE questions: First check if excluded, then confirm if covered
3. ALWAYS cite the relevant section/page when possible
4. If you cannot find a definitive answer, say so clearly
5. For financial questions (deductibles, limits), quote exact amounts

RESPONSE FORMAT:
- Start with a clear verdict (Covered ✅, Not Covered ❌, Conditional ⚠️, or Unknown ❓)
- Provide reasoning with specific policy citations
- Include relevant financial terms if applicable
- End with any caveats or recommendations"""

        user_prompt = f"""## COMPLETE POLICY DOCUMENT:

{full_text}

---

## USER QUESTION:
{user_message}

## ITEMS TO ANALYZE:
{items_str}

## INTENT:
{intent}

Please analyze the policy and provide a comprehensive answer."""

        try:
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]
            
            response = await self.llm.generate(messages, temperature=0.1)
            state["response"] = response.content
            state["reasoning_trace"].append("[WHOLE-DOC] Generated response with full document context")
            
            # Since we used the full doc, citations come from the response itself
            state["citations"] = ["Full policy document analyzed"]
            state["coverage_checks"] = []  # Let the response speak for itself
            
        except Exception as e:
            logger.error(f"Whole-doc response failed: {e}")
            state["response"] = f"I encountered an error analyzing the policy: {str(e)}"
            state["reasoning_trace"].append(f"[WHOLE-DOC] Error: {str(e)}")
        
        return state
    
    # =========================================================================
    # Routing Functions
    # =========================================================================
    
    def _route_by_intent(self, state: AgentState) -> str:
        """Route based on classified intent."""
        intent = state.get("intent", "general_info")
        
        if intent == QueryIntent.CHECK_COVERAGE.value:
            return "check_coverage"
        elif intent == QueryIntent.EXPLAIN_TERMS.value:
            return "explain_terms"
        elif intent == QueryIntent.GET_LIMITS.value:
            return "get_limits"
        else:
            return "general_info"
    
    def _route_after_exclusion_check(self, state: AgentState) -> str:
        """Route based on exclusion check results."""
        # If ALL items are excluded, stop here
        all_excluded = all(
            c.get("exclusion_found", False) 
            for c in state.get("coverage_checks", [])
        )
        
        if all_excluded and state.get("coverage_checks"):
            return "excluded"
        return "not_excluded"
    
    def _route_by_policy_size(self, state: AgentState) -> str:
        """
        Route based on policy size - Whole-Doc vs RAG.
        
        Small policies (<30 pages) use whole-doc mode for better accuracy.
        Large policies use the traditional RAG chunking approach.
        """
        if state.get("use_whole_doc_mode") and state.get("full_policy_text"):
            return "whole_doc"
        return "rag_retrieve"
    
    def _route_after_retrieve(self, state: AgentState) -> str:
        """
        Route after retrieval based on intent.
        
        - Coverage checks go through exclusion gate
        - Other intents go directly to response (using retrieved context)
        """
        intent = state.get("intent", "general_info")
        
        if intent == QueryIntent.CHECK_COVERAGE.value:
            return "check_exclusions"
        else:
            # Explain terms, get limits, general info - direct response with retrieved context
            return "direct_response"
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    async def _classify_intent(self, message: str) -> tuple[QueryIntent, list[str]]:
        """
        Classify the intent of a user message.
        Extract items/scenarios to check for coverage questions.
        """
        message_lower = message.lower()
        
        # CRITICAL: Questions about exclusions/coverage MUST go through the coverage check flow
        # This ensures we use RAG to find policy-specific exclusions
        coverage_keywords = [
            # Coverage questions
            "covered", "cover", "does my policy", "am i covered", "is my",
            # Exclusion questions - MUST route through exclusion check
            "exclusion", "excluded", "not covered", "what's not", "what isn't",
            "exception", "exempt", "limitation", "restricted", "banned",
            # Inclusion questions
            "included", "include", "what's covered", "what does my policy",
        ]
        
        if any(kw in message_lower for kw in coverage_keywords):
            intent = QueryIntent.CHECK_COVERAGE
        elif any(kw in message_lower for kw in ["what is", "what does", "define", "mean", "explain"]):
            intent = QueryIntent.EXPLAIN_TERMS
        elif any(kw in message_lower for kw in ["deductible", "limit", "cap", "how much", "payment"]):
            intent = QueryIntent.GET_LIMITS
        else:
            intent = QueryIntent.GENERAL_INFO
        
        # Extract items/scenarios to check
        items = []
        
        # Common insurance coverage items (auto, health, property)
        standard_items = [
            # Auto/mechanical
            "engine", "transmission", "brakes", "suspension", "battery",
            "collision", "comprehensive", "liability", "towing",
            # Health/life
            "medical", "hospitalization", "surgery", "prescription",
            "death benefit", "disability", "critical illness",
            # Property
            "theft", "vandalism", "fire", "flood", "earthquake",
            "property damage", "bodily injury",
        ]
        
        for item in standard_items:
            if item in message_lower:
                items.append(item)
        
        # Common exclusion scenarios across insurance types
        scenario_keywords = {
            "intentional damage": ["intentional", "deliberately", "on purpose"],
            "fraud": ["fraud", "misrepresentation", "false statement"],
            "pre-existing condition": ["pre-existing", "prior condition"],
            "self-inflicted": ["self-inflicted", "suicide", "self-harm"],
            "illegal activity": ["illegal", "criminal", "unlawful"],
            "war": ["war", "terrorism", "civil unrest"],
        }
        
        for scenario, keywords in scenario_keywords.items():
            for kw in keywords:
                if kw in message_lower:
                    items.append(scenario)
                    break
        
        # If no specific items found, extract key nouns from the question
        if not items:
            stop_words = {"am", "i", "is", "my", "the", "a", "an", "if", "to", "for", "in", "on", "it", 
                         "be", "do", "does", "will", "would", "can", "could", "what", "how", "when", 
                         "where", "why", "covered", "cover", "coverage", "policy", "insurance", "car"}
            words = [w for w in message_lower.split() if w not in stop_words and len(w) > 3 and w.isalpha()]
            items = words[:3]
        
        # SPECIAL CASE: User asking about ALL exclusions (e.g., "What are the exclusions?")
        # Use a generic search term to find exclusion-related content
        exclusion_query_patterns = [
            "what are the exclusion",  # Also matches "exclusions"
            "list exclusion",
            "all exclusion", 
            "the exclusion",
            "my exclusion",
            "show exclusion",
            "tell me the exclusion",
            "what exclusion",
        ]
        if any(kw in message_lower for kw in exclusion_query_patterns):
            # Replace unhelpful items with a broad exclusion search
            items = ["GENERAL_EXCLUSIONS"]  # Special marker for all-exclusions search
            logger.info(f"[ROUTER] Detected general exclusions query - using GENERAL_EXCLUSIONS marker")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_items = []
        for item in items:
            if item not in seen:
                seen.add(item)
                unique_items.append(item)
        
        return intent, unique_items
    
    async def _generate_response(
        self,
        user_message: str,
        intent: str,
        context: str,
        coverage_checks: list[dict],
    ) -> str:
        """Generate the final response using LLM."""
        from app.services.llm_service import LLMMessage
        
        system_prompt = """You are an insurance policy assistant. Your responses must be:
1. ACCURATE - Only state coverage if explicitly found in the policy
2. CITED - Reference specific policy excerpts
3. CAUTIOUS - If unsure, say "requires review" not "covered"

## Coverage Check Results:
{context}

## Response Guidelines:
- Start with a clear verdict (COVERED / NOT COVERED / CONDITIONAL / REQUIRES REVIEW)
- Explain the reasoning with specific policy references
- Include any relevant financial terms (deductibles, limits)
- If excluded, clearly state WHY it's excluded
"""
        
        messages = [
            LLMMessage(role="system", content=system_prompt.format(context=context)),
            LLMMessage(role="user", content=user_message),
        ]
        
        response = await self.llm.generate(messages)
        return response.content
    
    def _extract_citations(self, state: AgentState) -> list[str]:
        """Extract citation references from results."""
        citations = []
        
        for check in state.get("coverage_checks", []):
            if check.get("exclusion_text"):
                citations.append(f"Exclusion: {check['exclusion_text'][:100]}...")
            if check.get("inclusion_text"):
                citations.append(f"Coverage: {check['inclusion_text'][:100]}...")
        
        return citations[:5]  # Limit citations
    
    # =========================================================================
    # Public API
    # =========================================================================
    
    async def process(
        self,
        user_message: str,
        policy_id: str,
        user_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        full_policy_text: Optional[str] = None,
        use_whole_doc_mode: bool = False,
    ) -> dict:
        """
        Process a user query through the reasoning loop.
        
        Args:
            user_message: The user's question
            policy_id: Policy identifier for RAG filtering
            user_id: Optional user ID (for B2B context)
            agent_id: Optional agent ID
            full_policy_text: Full policy text for whole-doc mode
            use_whole_doc_mode: If True, skip RAG and use full document
        
        Returns:
            dict with response, decision, citations, and reasoning_trace
        """
        initial_state: AgentState = {
            "user_message": user_message,
            "policy_id": policy_id,
            "user_id": user_id,
            "agent_id": agent_id,
            # Whole-Doc Mode
            "full_policy_text": full_policy_text,
            "use_whole_doc_mode": use_whole_doc_mode and bool(full_policy_text),
            # Classification
            "intent": "",
            "items_to_check": [],
            # Retrieved context
            "retrieved_chunks": [],
            "definitions_context": "",
            # Search Results
            "exclusion_results": [],
            "inclusion_results": [],
            "financial_results": [],
            "user_limitations": [],
            # Decision
            "coverage_checks": [],
            "final_decision": "",
            # Output
            "response": "",
            "citations": [],
            "reasoning_trace": [],
        }
        
        # Run the graph
        final_state = await self.graph.ainvoke(initial_state)
        
        return {
            "response": final_state.get("response", ""),
            "coverage_checks": final_state.get("coverage_checks", []),
            "citations": final_state.get("citations", []),
            "reasoning_trace": final_state.get("reasoning_trace", []),
            "intent": final_state.get("intent", ""),
            "used_whole_doc_mode": initial_state["use_whole_doc_mode"],
        }


# =============================================================================
# Factory Function
# =============================================================================

_coverage_agent: Optional[CoverageAgent] = None


def get_coverage_agent() -> CoverageAgent:
    """Get or create the global coverage agent instance."""
    global _coverage_agent
    
    if _coverage_agent is None:
        from app.services.agent_service import get_agent_service
        from app.services.llm_service import get_llm, LLMProvider
        from app.core.config import settings
        
        agent_service = get_agent_service()
        
        provider_map = {
            "mock": LLMProvider.MOCK,
            "openai": LLMProvider.OPENAI,
            "anthropic": LLMProvider.ANTHROPIC,
            "google": LLMProvider.GOOGLE,
        }
        provider = provider_map.get(settings.LLM_PROVIDER.lower(), LLMProvider.MOCK)
        llm = get_llm(provider)
        
        _coverage_agent = CoverageAgent(
            vectorizer=agent_service.vectorizer,
            llm=llm,
        )
        
        logger.info("CoverageAgent initialized with LangGraph reasoning loop")
    
    return _coverage_agent

