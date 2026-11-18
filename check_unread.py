import json

rows = [json.loads(l) for l in open("results/openai/solving.jsonl", encoding="utf-8")]
for r in rows:
    if r["method"] == "cot" and r["puzzle_id"] in ("easy-2", "hard-2", "hard-5"):
        text = r["transcript"][0]["content"]
        print("=" * 30, r["puzzle_id"], f"(reply length: {len(text)} characters)")
        print(text[-700:])