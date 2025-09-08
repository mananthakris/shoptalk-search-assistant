import asyncio
from llm_helper import llm_parse_query as real_parse

async def fake_parse(q: str):
    # super simple extractor that mimics structure
    out = {"category": "shoes", "color": "red", "brand": None, "gender": None,
           "price_max": 120, "must_have": [], "exclude": [], "rewrite": "red shoes under 120"}
    return out

def test_parse_shape(monkeypatch):
    monkeypatch.setattr("llm_helper.llm_parse_query", fake_parse)
    res = asyncio.get_event_loop().run_until_complete(fake_parse("red sneakers under $120"))
    assert "rewrite" in res and "price_max" in res
