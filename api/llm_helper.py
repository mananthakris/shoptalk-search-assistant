import os, json
from typing import Any, Dict, List, Optional

# LangChain (model-agnostic)
from langchain_openai import ChatOpenAI  # swap for another LC chat backend if you like
from langchain_core.prompts import ChatPromptTemplate

# --- configuration helpers ---
_PARSE_MODEL = os.getenv("PARSE_MODEL", "gpt-4o-mini")
_NLG_MODEL   = os.getenv("NLG_MODEL",   "gpt-4o-mini")

# Build a generic LC chat model factory so you can swap vendors later.
def _chat_model(model_name: str):
    # If you later switch to vLLM/OpenRouter/etc., just change this single line
    return ChatOpenAI(
        model=model_name,
        temperature=0.0,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )

# --------- PARSER ---------

# No hardcoded category mapping - let vector search and flexible filtering handle it

# We ask the LLM to return STRICT JSON with only these keys. No synonyms/canon logic here.
_PARSER_SYS = """You extract shopping filters from a single user query.
Return STRICT JSON (a single object), no prose, with EXACT keys:
- "category": string or null (main product type, use natural terms that users would say)
- "color": string or null (only if color is the PRIMARY focus, not just mentioned)
- "brand": string or null
- "gender": string or null
- "price_max": number or null
- "must_have": array of strings (can be empty) - key descriptive terms that must be present
- "exclude": array of strings (can be empty)
- "rewrite": string (a concise rewrite of the query preserving intent)
Rules:
- Output MUST be valid JSON. No markdown, no explanations.
- If unsure about a field, use null (or [] for arrays).
- For category: use natural, user-friendly terms (e.g., "phone case", "shoes", "jewelry", "furniture")
- For color: only extract if color is the main focus (e.g., "red dress" -> color="red", but "red running shoes" -> color=null, must_have=["red"])
- For must_have: include descriptive terms like colors, styles, materials when they're not the primary filter
- The system will handle category matching flexibly, so use terms that make sense to users
"""

_PARSER_USER = """Query: {query}"""

_parser_prompt = ChatPromptTemplate.from_messages(
    [("system", _PARSER_SYS), ("user", _PARSER_USER)]
)

def _coerce_parsed(obj: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    """Keep only expected keys and coerce types; no synonym logic."""
    out = {
        "category":  obj.get("category"),
        "color":     obj.get("color"),
        "brand":     obj.get("brand"),
        "gender":    obj.get("gender"),
        "price_max": obj.get("price_max"),
        "must_have": obj.get("must_have") if isinstance(obj.get("must_have"), list) else [],
        "exclude":   obj.get("exclude") if isinstance(obj.get("exclude"), list) else [],
        "rewrite":   obj.get("rewrite") or user_text,
    }
    # Coerce price_max to float if it's a string number
    pm = out["price_max"]
    if isinstance(pm, str):
        try:
            out["price_max"] = float(pm)
        except Exception:
            out["price_max"] = None
    elif not (isinstance(pm, (int, float)) or pm is None):
        out["price_max"] = None
    return out

async def llm_parse_query(user_text: str) -> Dict[str, Any]:
    llm = _chat_model(_PARSE_MODEL)
    msg = _parser_prompt.invoke({"query": user_text})
    resp = await llm.ainvoke(msg.to_messages())
    raw = resp.content if hasattr(resp, "content") else str(resp)

    # Strict JSON parse; if it fails, return a minimal dict 
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Parser returned non-object JSON")
        return _coerce_parsed(data, user_text)
    except Exception:
        return {
            "category": None,
            "color": None,
            "brand": None,
            "gender": None,
            "price_max": None,
            "must_have": [],
            "exclude": [],
            "rewrite": user_text,
            "_warning": "parse_failed_json"
        }

# --------- NLG ---------

_NLG_SYS = """You are a shopping assistant. Write a brief answer using ONLY the provided products.
Mention 2-3 items max. Keep it concise - 1-2 sentences per item."""

_NLG_USER = """User query: {orig_query}
Parsed filters: {filters_json}

Candidates (array of objects with title, url, optional price/category):
{candidates_json}"""

_nlg_prompt = ChatPromptTemplate.from_messages(
    [("system", _NLG_SYS), ("user", _NLG_USER)]
)

async def llm_nlg_answer(orig_query: str, filters: Dict[str, Any], metas: List[Dict[str, Any]]) -> str:
    # Trim and sanitize metas for the LLM (limit to 5 items for faster processing)
    items = []
    for m in metas[:5]:
        items.append({
            "title":    (m.get("title") or "")[:200],
            "url":      (m.get("url") or "")[:500],
            "price":    m.get("price", None),
            "category": m.get("category", None),
        })
    llm = _chat_model(_NLG_MODEL)
    msg = _nlg_prompt.invoke({
        "orig_query": orig_query,
        "filters_json": json.dumps(filters, ensure_ascii=False),
        "candidates_json": json.dumps(items, ensure_ascii=False)
    })
    resp = await llm.ainvoke(msg.to_messages())
    text = resp.content if hasattr(resp, "content") else str(resp)
    return (text or "").strip() or "Here are a few options based on your query."
