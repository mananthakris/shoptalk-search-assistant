
import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="ShopTalk Search", layout="wide")
st.title("ShopTalk — Vector Search")

q = st.text_input("What are you looking for?", value="red men's running shoes under $100")
k = st.slider("Top K", 1, 20, 10)

if st.button("Search") and q.strip():
    with st.spinner("Searching..."):
        r = requests.get(f"{API_URL}/search", params={"q": q, "k": k}, timeout=60)
        r.raise_for_status()
        data = r.json()

    st.subheader("Results")
    for hit in data["results"]:
        with st.container():
            st.markdown(f"**{hit.get('title') or '(no title)'}**  \nScore: {hit['score']:.3f}")
            if hit.get("price") is not None:
                st.write(f"Price: ${hit['price']:.2f}")
            if hit.get("url"):
                st.write(hit["url"])
            st.caption(f"ID: {hit['id']}")
