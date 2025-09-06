import os
from dotenv import load_dotenv

def test_env_loads():
    load_dotenv()
    # Not asserting secrets, just that module can read without crashing
    assert isinstance(os.getenv("OPENAI_BASE_URL", ""), str)
