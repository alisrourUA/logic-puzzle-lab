"""Check that your API key works before running experiments:  python check_key.py"""
import os

from puzzlelab import config
from puzzlelab.llm import OpenAIClient

if __name__ == "__main__":
    c = OpenAIClient()
    custom = bool(os.getenv("OPENAI_BASE_URL"))
    models = sorted(m.id for m in c.client.models.list() if custom or "gpt" in m.id)
    print(f"provider: {os.getenv('OPENAI_BASE_URL') or 'OpenAI'}")
    print("models this key can use:", ", ".join(models) or "(none)")
    print(f"configured model: {config.MODEL}  ->  {'OK' if config.MODEL in models else 'NOT in the list!'}")
    r = c.chat([{"role": "user", "content": "Reply with the word: ready"}], temperature=0, max_tokens=5)
    print("test call reply:", r.text, f"({r.prompt_tokens}+{r.completion_tokens} tokens)")
    print("Key works. Next: python run_generation.py")