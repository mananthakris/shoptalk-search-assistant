# llm_helper.py
import os, json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv
load_dotenv()
# ---------- config ----------
LLM_MODEL_PARSE = os.getenv("PARSE_MODEL", "gpt-4o-mini")
LLM_MODEL_NLG   = os.getenv("NLG_MODEL", "gpt-4o-mini")

# You can point to OpenAI or a self-hosted OpenAI-compatible endpoint (vLLM)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")

def _make_llm(model: str, temperature: float = 0.0):
    # LangChain will route to OpenAI-compatible APIs using base_url+api_key
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
    )

# ---------- Structured schema for parsing ----------
class ParsedQuery(BaseModel):
    category: Optional[str] = Field(default=None)
    color: Optional[str] = Field(default=None)
    brand: Optional[str] = Field(default=None)
    gender: Optional[str] = Field(default=None)
    price_max: Optional[float] = Field(default=None)
    must_have: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)
    rewrite: Optional[str] = Field(default=None)

_parse_system = (
    "You are a shopping query parser. "
    "Extract constraints and rewrite the query. "
    "Return STRICT JSON that matches this schema."
)

_parse_user_tmpl = """\
User query: "{q}"

Guidelines:
- If no value for a field, use null (or [] for arrays).
- price_max must be numeric (e.g., 120).
- Normalize color synonyms (e.g., maroon -> red).
- 'rewrite' should be a short, search-friendly version of the query.
"""

_parse_prompt = ChatPromptTemplate.from_messages(
    [("system", _parse_system), ("user", _parse_user_tmpl)]
)
_parse_parser = JsonOutputParser(pydantic_object=ParsedQuery)

# ---------- Public: parse before search ----------
async def llm_parse_query(user_query: str) -> Dict[str, Any]:
    llm = _make_llm(LLM_MODEL_PARSE, temperature=0.0)
    chain = _parse_prompt | llm | _parse_parser
    try:
        result: ParsedQuery = await chain.ainvoke({"q": user_query})
        return result.dict()
    except Exception as e:
        # very small fallback: return empty constraints with rewrite=user_query
        return {
            "category": None, "color": None, "brand": None, "gender": None,
            "price_max": None, "must_have": [], "exclude": [], "rewrite": user_query,
            "_warning": f"parse_fallback: {e}"
        }

# ---------- NLG (post-search) ----------
_nlg_system = (
    "You are a concise shopping assistant. "
    "You will receive a user query, parsed filters, and candidate products. "
    "Only mention facts present in the candidates. Do NOT invent price, color, or availability. "
    "Return a short recommendation with at most 3–6 items; include titles and URLs."
)

_nlg_user_tmpl = """\
User query: {q}
Parsed filters: {filters}
Candidates (JSON list of objects with title, brand, price, color, url, id):
{candidates}
"""

_nlg_prompt = ChatPromptTemplate.from_messages(
    [("system", _nlg_system), ("user", _nlg_user_tmpl)]
)

async def llm_nlg_answer(user_query: str, parsed_filters: Dict[str, Any], candidates: List[Dict[str, Any]]) -> str:
    # Trim candidate payload to just what NLG needs
    safe_fields = ("title","brand","price","color","url","id")
    slim = [{k: v for k, v in (c or {}).items() if k in safe_fields} for c in candidates[:6]]

    llm = _make_llm(LLM_MODEL_NLG, temperature=0.2)
    chain = _nlg_prompt | llm
    resp = await chain.ainvoke({
        "q": user_query,
        "filters": json.dumps(parsed_filters, ensure_ascii=False),
        "candidates": json.dumps(slim, ensure_ascii=False)
    })
    return resp.content.strip()
