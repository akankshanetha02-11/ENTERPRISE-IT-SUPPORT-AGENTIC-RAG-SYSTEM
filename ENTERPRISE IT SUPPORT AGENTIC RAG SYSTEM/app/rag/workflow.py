
import logging
from typing import Literal, Any

from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, START, END

from app.core.config import get_settings
from app.rag.state import AgentState
from app.rag.vectorstore import get_retriever


logger = logging.getLogger(__name__)
settings = get_settings()

_llm = None
_web_search = None


# --------------------------------------------------
# 1. OpenRouter LLM
# --------------------------------------------------

def llm():

    global _llm

    if _llm is None:

        if not settings.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is missing in .env"
            )

        _llm = ChatOpenAI(
            model=settings.openrouter_model,
            temperature=0,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )

        logger.info(
            "OpenRouter LLM initialized: %s",
            settings.openrouter_model
        )

    return _llm


# --------------------------------------------------
# 2. Convert model response to text
# --------------------------------------------------

def get_response_text(response: Any) -> str:

    if response is None:
        return ""

    content = getattr(response, "content", response)

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):

        parts = []

        for item in content:

            if isinstance(item, dict):
                text = item.get("text", "")

                if text:
                    parts.append(str(text))

            else:
                parts.append(str(item))

        return " ".join(parts).strip()

    return str(content).strip()


# --------------------------------------------------
# 3. Tavily Web Search
# --------------------------------------------------

def web_search_tool():

    global _web_search

    if _web_search is None:

        if not settings.tavily_api_key:
            raise RuntimeError(
                "TAVILY_API_KEY is missing in .env"
            )

        _web_search = TavilySearch(
            tavily_api_key=settings.tavily_api_key,
            max_results=5,
            topic="general",
            include_answer=True,
            include_raw_content=False,
        )

        logger.info("Tavily search initialized")

    return _web_search


# --------------------------------------------------
# 4. Trace Helper
# --------------------------------------------------

def add_trace(state: AgentState, message: str):

    return [
        *state.get("trace", []),
        message
    ]


# --------------------------------------------------
# 5. Question Router
# --------------------------------------------------

def route_question(state: AgentState):

    question = state["question"]

    prompt = f"""
You are a router for an enterprise IT support assistant.

Choose KB for questions about:
- Company IT policies
- VPN
- Password reset
- MFA
- Laptop setup
- Software access
- Security
- Email
- Devices
- Troubleshooting
- Technology support

Choose DIRECT only for:
- Greetings
- Thanks
- Simple casual conversation

Question: {question}

Return exactly one word:
KB
or
DIRECT

Do not explain your answer.
"""

    try:

        response = llm().invoke(prompt)

        result = get_response_text(response).upper()

        logger.info("Router response: %s", result)

        if "DIRECT" in result:
            route = "direct"
        elif "KB" in result:
            route = "kb"
        else:
            route = "kb"

    except Exception:

        logger.exception("Question routing failed")

        route = "kb"

    return {
        "source_used": route,
        "trace": add_trace(
            state,
            f"Router → {route.upper()}"
        )
    }


def route_after_router(
    state: AgentState
) -> Literal["retrieve_kb", "direct_answer"]:

    if state.get("source_used") == "kb":
        return "retrieve_kb"

    return "direct_answer"


# --------------------------------------------------
# 6. Private Knowledge Base Retrieval
# --------------------------------------------------

def retrieve_kb(state: AgentState):

    query = state.get(
        "current_query",
        state["question"]
    )

    docs = get_retriever().invoke(query)

    logger.info(
        "Retrieved %s KB chunks",
        len(docs)
    )

    return {
        "kb_docs": docs,
        "trace": add_trace(
            state,
            f"Private KB retrieval → {len(docs)} chunks"
        )
    }


# --------------------------------------------------
# 7. Grade Private KB Evidence
# --------------------------------------------------

def grade_kb(state: AgentState):

    docs = state.get("kb_docs", [])

    if not docs:

        return {
            "kb_grade": "weak",
            "trace": add_trace(
                state,
                "KB evidence grade → WEAK (no documents)"
            )
        }

    context = "\n\n".join(
        f"Source: {doc.metadata.get('source', 'unknown')}\n"
        f"{doc.page_content}"
        for doc in docs
    )

    prompt = f"""
You are an evidence evaluator for enterprise IT support.

Question:
{state['question']}

Private knowledge base evidence:
{context}

Decide whether the evidence directly and sufficiently
answers the question.

Return exactly one word:
GOOD
or
WEAK

Do not explain.
"""

    try:

        response = llm().invoke(prompt)

        result = get_response_text(response).upper()

        logger.info(
            "KB grading response: %s",
            result
        )

        grade = (
            "good"
            if result.startswith("GOOD")
            else "weak"
        )

    except Exception:

        logger.exception("KB grading failed")

        grade = "weak"

    return {
        "kb_grade": grade,
        "trace": add_trace(
            state,
            f"KB evidence grade → {grade.upper()}"
        )
    }


def after_kb(
    state: AgentState
) -> Literal["generate_from_kb", "search_web"]:

    if state.get("kb_grade") == "good":
        return "generate_from_kb"

    return "search_web"


# --------------------------------------------------
# 8. External Web Search
# --------------------------------------------------

def search_web(state: AgentState):

    query = state.get(
        "current_query",
        state["question"]
    )

    result = web_search_tool().invoke({
        "query": query
    })

    lines = []
    citations = []

    if isinstance(result, dict):

        answer = result.get("answer")

        if answer:
            lines.append(
                "Search answer: " + str(answer)
            )

        for item in result.get("results", []):

            title = item.get("title", "")
            url = item.get("url", "")
            content = item.get("content", "")

            lines.append(
                f"Title: {title}\n"
                f"URL: {url}\n"
                f"Content: {content}"
            )

            if url:
                citations.append({
                    "title": title or url,
                    "url": url,
                    "type": "web"
                })

    elif isinstance(result, list):

        for item in result:

            if isinstance(item, dict):

                title = item.get("title", "")
                url = item.get("url", "")
                content = item.get("content", "")

                lines.append(
                    f"Title: {title}\n"
                    f"URL: {url}\n"
                    f"Content: {content}"
                )

                if url:
                    citations.append({
                        "title": title or url,
                        "url": url,
                        "type": "web"
                    })

            else:
                lines.append(str(item))

    else:
        lines.append(str(result))

    web_text = "\n\n".join(lines)

    return {
        "web_results": web_text,
        "citations": citations,
        "source_used": "web",
        "trace": add_trace(
            state,
            "Web fallback → Tavily search"
        )
    }


# --------------------------------------------------
# 9. Grade Web Evidence
# --------------------------------------------------

def grade_web(state: AgentState):

    web_results = state.get("web_results", "")

    if not web_results.strip():

        return {
            "web_grade": "weak",
            "trace": add_trace(
                state,
                "Web evidence grade → WEAK (no results)"
            )
        }

    prompt = f"""
You are an evidence evaluator.

Question:
{state['question']}

External web evidence:
{web_results}

Decide whether the evidence is directly relevant
and sufficient to answer the question.

Return exactly one word:
GOOD
or
WEAK

Do not explain.
"""

    try:

        response = llm().invoke(prompt)

        result = get_response_text(response).upper()

        logger.info(
            "Web grading response: %s",
            result
        )

        grade = (
            "good"
            if result.startswith("GOOD")
            else "weak"
        )

    except Exception:

        logger.exception("Web grading failed")

        grade = "weak"

    return {
        "web_grade": grade,
        "trace": add_trace(
            state,
            f"Web evidence grade → {grade.upper()}"
        )
    }


def after_web(
    state: AgentState
) -> Literal[
    "generate_from_web",
    "rewrite_query",
    "insufficient"
]:

    if state.get("web_grade") == "good":
        return "generate_from_web"

    if state.get("retry_count", 0) < settings.max_retries:
        return "rewrite_query"

    return "insufficient"


# --------------------------------------------------
# 10. Rewrite Query
# --------------------------------------------------

def rewrite_query(state: AgentState):

    prompt = f"""
Rewrite this IT support question for better retrieval.

Preserve the original meaning.
Add useful technical keywords.
Do not answer the question.

Return only the rewritten query.

Question:
{state['question']}
"""

    response = llm().invoke(prompt)

    rewritten = get_response_text(response)

    if not rewritten:
        rewritten = state["question"]

    return {
        "current_query": rewritten,
        "retry_count": state.get("retry_count", 0) + 1,
        "trace": add_trace(
            state,
            f"Query rewrite → {rewritten}"
        )
    }


# --------------------------------------------------
# 11. Generate Answer From Private KB
# --------------------------------------------------

def generate_from_kb(state: AgentState):

    docs = state.get("kb_docs", [])

    context = "\n\n".join(
        f"[Source: {doc.metadata.get('source', 'unknown')}]\n"
        f"{doc.page_content}"
        for doc in docs
    )

    prompt = f"""
You are an enterprise IT support assistant.

Answer ONLY using the private company knowledge base.

Instructions:
- Give clear and actionable steps.
- Do not invent company policies.
- If information is missing, say so.
- Mention that the answer is based on the private
  company knowledge base.

Question:
{state['question']}

Private knowledge base:
{context}
"""

    response = llm().invoke(prompt)

    answer = get_response_text(response)

    citations = []
    seen = set()

    for doc in docs:

        source = doc.metadata.get(
            "source",
            "Private KB"
        )

        if source not in seen:

            seen.add(source)

            citations.append({
                "title": source.split("/")[-1],
                "url": "",
                "type": "private_kb"
            })

    return {
        "answer": answer,
        "source_used": "private_kb",
        "citations": citations,
        "trace": add_trace(
            state,
            "Answer generation → PRIVATE KB"
        )
    }


# --------------------------------------------------
# 12. Generate Answer From Web
# --------------------------------------------------

def generate_from_web(state: AgentState):

    prompt = f"""
You are an enterprise IT support assistant.

The private company knowledge base was insufficient.

Answer ONLY using the external web evidence below.

Instructions:
- Clearly mention that information comes from external
  web sources.
- It may need IT team validation before changing
  company-managed systems.
- Do not invent facts.

Question:
{state['question']}

Web evidence:
{state['web_results']}
"""

    response = llm().invoke(prompt)

    answer = get_response_text(response)

    return {
        "answer": answer,
        "source_used": "web_search",
        "trace": add_trace(
            state,
            "Answer generation → WEB SEARCH"
        )
    }


# --------------------------------------------------
# 13. Direct Answer
# --------------------------------------------------

def direct_answer(state: AgentState):

    response = llm().invoke(
        f"""
Respond briefly and naturally to this message:

{state['question']}
"""
    )

    answer = get_response_text(response)

    return {
        "answer": answer,
        "source_used": "direct",
        "trace": add_trace(
            state,
            "Direct response → no retrieval"
        )
    }


# --------------------------------------------------
# 14. Insufficient Evidence
# --------------------------------------------------

def insufficient(state: AgentState):

    return {
        "answer": (
            "I couldn't find enough reliable evidence in "
            "the company knowledge base or external search "
            "to answer confidently. Please contact the IT "
            "help desk or provide more details."
        ),
        "source_used": "insufficient_evidence",
        "trace": add_trace(
            state,
            "Stopped → insufficient reliable evidence"
        )
    }


# --------------------------------------------------
# 15. Build LangGraph Workflow
# --------------------------------------------------

def build_graph():

    graph = StateGraph(AgentState)

    nodes = {
        "route_question": route_question,
        "retrieve_kb": retrieve_kb,
        "grade_kb": grade_kb,
        "search_web": search_web,
        "grade_web": grade_web,
        "rewrite_query": rewrite_query,
        "generate_from_kb": generate_from_kb,
        "generate_from_web": generate_from_web,
        "direct_answer": direct_answer,
        "insufficient": insufficient,
    }

    for name, function in nodes.items():
        graph.add_node(name, function)

    graph.add_edge(START, "route_question")

    graph.add_conditional_edges(
        "route_question",
        route_after_router,
        {
            "retrieve_kb": "retrieve_kb",
            "direct_answer": "direct_answer"
        }
    )

    graph.add_edge("retrieve_kb", "grade_kb")

    graph.add_conditional_edges(
        "grade_kb",
        after_kb,
        {
            "generate_from_kb": "generate_from_kb",
            "search_web": "search_web"
        }
    )

    graph.add_edge("search_web", "grade_web")

    graph.add_conditional_edges(
        "grade_web",
        after_web,
        {
            "generate_from_web": "generate_from_web",
            "rewrite_query": "rewrite_query",
            "insufficient": "insufficient"
        }
    )

    graph.add_edge("rewrite_query", "retrieve_kb")

    graph.add_edge("generate_from_kb", END)
    graph.add_edge("generate_from_web", END)
    graph.add_edge("direct_answer", END)
    graph.add_edge("insufficient", END)

    return graph.compile()


# Compile workflow
agent_graph = build_graph()


# --------------------------------------------------
# 16. Main Ask Function
# --------------------------------------------------

def ask(question: str):

    initial_state: AgentState = {
        "question": question,
        "current_query": question,
        "kb_docs": [],
        "web_results": "",
        "kb_grade": "",
        "web_grade": "",
        "answer": "",
        "source_used": "",
        "retry_count": 0,
        "trace": [],
        "citations": [],
    }

    return agent_graph.invoke(initial_state)

