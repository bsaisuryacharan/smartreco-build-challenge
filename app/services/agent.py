import logging
import os
from collections import Counter
from typing import TypedDict

from langgraph.graph import StateGraph, END
from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# Configure LangSmith tracing via environment variables
os.environ.setdefault("LANGCHAIN_TRACING_V2", settings.LANGCHAIN_TRACING_V2)
os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGCHAIN_PROJECT)
if settings.LANGCHAIN_API_KEY:
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGCHAIN_API_KEY)

mesh_client = OpenAI(
    base_url="https://api.meshapi.ai/v1",
    api_key=settings.MESH_API_KEY,
)
MODEL = "openai/gpt-4o-mini"


class AgentState(TypedDict):
    user_id: int
    recent_events: list
    interests_query: str
    retrieved_docs: list
    quality_ok: bool
    retries: int
    narrative: str
    recommended_product_ids: list


# ── Node 1: analyze user behavior → build search query ────────────────────────

def analyze_behavior(state: AgentState) -> AgentState:
    events = state["recent_events"]

    categories = [e.get("category", "") for e in events if e.get("category")]
    searches = [
        e["metadata_"].get("query", "")
        for e in events
        if e.get("event_type") == "search" and e.get("metadata_")
    ]
    titles = [
        e["metadata_"].get("title", "")
        for e in events
        if e.get("product_id") and e.get("metadata_")
    ]

    # Weight categories by frequency, pick top 3; de-duplicate while preserving order
    top_cats = [cat for cat, _ in Counter(categories).most_common(3)]
    parts = list(dict.fromkeys(filter(None, top_cats + searches[:3] + titles[:3])))
    query = " ".join(parts[:8]) if parts else ""

    logger.debug("analyze_behavior query: %r", query)
    return {**state, "interests_query": query}


# ── Node 2: retrieve from ChromaDB ────────────────────────────────────────────

def retrieve_products(state: AgentState) -> AgentState:
    from app.services.vector_store import search_products, get_vector_store

    query = state["interests_query"]
    if not query:
        # No behavioral signals yet — pull the first N products by insertion order
        col = get_vector_store()
        count = col.count()
        if count == 0:
            docs = []
        else:
            raw = col.get(limit=min(10, count), include=["metadatas"])
            ids = raw.get("ids", [])
            metas = raw.get("metadatas", [])
            docs = [
                {"vector_id": vid, "distance": 0.5, **meta}
                for vid, meta in zip(ids, metas)
            ]
    else:
        docs = search_products(query, n_results=10)

    logger.debug("retrieve_products got %d docs", len(docs))
    return {**state, "retrieved_docs": docs}


# ── Node 3: evaluate retrieval quality ────────────────────────────────────────

def evaluate_quality(state: AgentState) -> AgentState:
    docs = state["retrieved_docs"]
    # cosine distance < 0.6 means the embedding is meaningfully related
    relevant = [d for d in docs if d.get("distance", 1.0) < 0.6]
    quality_ok = len(relevant) >= 3 or state["retries"] >= 2
    return {**state, "quality_ok": quality_ok}


# ── Node 4: refine query when quality is poor ──────────────────────────────────

def refine_query(state: AgentState) -> AgentState:
    prompt = (
        f"A learner is interested in: '{state['interests_query']}'. "
        "List 5 closely related educational topics as a short comma-separated phrase."
    )
    try:
        resp = mesh_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
        )
        broader = resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("refine_query LLM call failed: %s", exc)
        broader = state["interests_query"]

    return {**state, "interests_query": broader, "retries": state["retries"] + 1}


# ── Node 5: generate personalized narrative + ranked product IDs ───────────────

def generate_recommendation(state: AgentState) -> AgentState:
    docs = state["retrieved_docs"]
    if not docs:
        return {
            **state,
            "narrative": "Start exploring our catalog and we'll personalize recommendations just for you!",
            "recommended_product_ids": [],
        }

    # Re-rank: boost products whose category aligns with user's top interests
    event_categories = [e.get("category", "") for e in state["recent_events"] if e.get("category")]
    cat_counts = Counter(event_categories)
    total = max(sum(cat_counts.values()), 1)

    for doc in docs:
        cat_weight = cat_counts.get(doc.get("category", ""), 0) / total
        similarity = 1.0 - min(doc.get("distance", 1.0), 1.0)
        doc["final_score"] = similarity * (1.0 + cat_weight)

    top_docs = sorted(docs, key=lambda d: d["final_score"], reverse=True)[:5]
    product_ids = [int(d["product_id"]) for d in top_docs]

    product_lines = "\n".join(
        f"- {d['title']} (Category: {d['category']}, ID: {int(d['product_id'])})"
        for d in top_docs
    )
    searches = [
        e["metadata_"].get("query", "")
        for e in state["recent_events"]
        if e.get("event_type") == "search" and e.get("metadata_")
    ]
    interest_summary = state["interests_query"] or "general learning"

    system_prompt = (
        "You are a warm, encouraging learning advisor. "
        "Write a short 3-4 sentence personalized message to motivate a learner based on their interests. "
        "Be specific to their topics, use a friendly tone, and end with a call-to-action. "
        "Do NOT list courses in the narrative — just write the motivating story."
    )
    user_prompt = (
        f"Learner's interest signals: {interest_summary}\n"
        f"Recent searches: {', '.join(filter(None, searches)) or 'none'}\n\n"
        f"Top recommended courses:\n{product_lines}\n\n"
        "Write the personalized narrative."
    )

    try:
        resp = mesh_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=300,
        )
        narrative = resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("generate_recommendation LLM call failed: %s", exc)
        narrative = f"We've picked courses that match your interests in {interest_summary}. Check them out below!"

    return {**state, "narrative": narrative, "recommended_product_ids": product_ids}


# ── Routing ────────────────────────────────────────────────────────────────────

def _quality_router(state: AgentState) -> str:
    return "generate" if state["quality_ok"] else "refine"


# ── Graph assembly ─────────────────────────────────────────────────────────────

def _build_agent():
    g = StateGraph(AgentState)
    g.add_node("analyze_behavior", analyze_behavior)
    g.add_node("retrieve_products", retrieve_products)
    g.add_node("evaluate_quality", evaluate_quality)
    g.add_node("refine_query", refine_query)
    g.add_node("generate_recommendation", generate_recommendation)

    g.set_entry_point("analyze_behavior")
    g.add_edge("analyze_behavior", "retrieve_products")
    g.add_edge("retrieve_products", "evaluate_quality")
    g.add_conditional_edges(
        "evaluate_quality",
        _quality_router,
        {"generate": "generate_recommendation", "refine": "refine_query"},
    )
    g.add_edge("refine_query", "retrieve_products")
    g.add_edge("generate_recommendation", END)

    return g.compile()


_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


def run_agent(user_id: int, recent_events: list) -> dict:
    """Run the recommendation agent and return {narrative, product_ids}."""
    agent = _get_agent()
    initial: AgentState = {
        "user_id": user_id,
        "recent_events": recent_events,
        "interests_query": "",
        "retrieved_docs": [],
        "quality_ok": False,
        "retries": 0,
        "narrative": "",
        "recommended_product_ids": [],
    }
    result = agent.invoke(initial)
    return {
        "narrative": result["narrative"],
        "product_ids": result["recommended_product_ids"],
    }
