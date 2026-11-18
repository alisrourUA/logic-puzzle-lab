import json

for line in open("results/openai/generation.jsonl", encoding="utf-8"):
    r = json.loads(line)
    print("=" * 80)
    print(r["experiment"], "shots", r["shots"], "T", r["temperature"], r["difficulty"])
    for a in r["attempts"]:
        print(f"  round {a['round']}: {a['status']}")
        print("     ", a["feedback"][:300])
print("=" * 80)
print("LAST RAW REPLY OF RUN 2:")
rows = [json.loads(l) for l in open("results/openai/generation.jsonl", encoding="utf-8")]
bad = [r for r in rows if r["final_status"] == "format_error"]
if bad:
    print(bad[0]["final_raw"][:2500])