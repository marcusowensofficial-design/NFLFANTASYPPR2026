import json

with open("data/nextgen_micro_metrics_2026.json", "r", encoding="utf-8") as f:
    ng = json.load(f)

print("Keys:", list(ng.keys()))
cov = ng.get("coverage_shells", {})
print("Coverage shells count:", len(cov))
if cov:
    sample_team = list(cov.keys())[0]
    print(f"Sample team {sample_team}:", cov[sample_team])
