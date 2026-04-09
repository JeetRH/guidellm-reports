import json
from collections import defaultdict
from pathlib import Path

path = Path("input/llama-100-300.json")
data = json.loads(path.read_text())

# concurrency -> list of TTFT means
ttft_by_concurrency = defaultdict(list)

for bench in data["benchmarks"]:
    strategy = bench["config"]["strategy"]

    # In your file this is effectively 1 and 5
    concurrency = strategy.get("max_concurrency", strategy.get("worker_count"))

    # Use successful TTFT mean (in ms)
    ttft_mean = bench["metrics"]["time_to_first_token_ms"]["successful"]["mean"]
    ttft_by_concurrency[concurrency].append(ttft_mean)

# Final average TTFT at each concurrency
avg_ttft = {
    c: sum(vals) / len(vals)
    for c, vals in ttft_by_concurrency.items()
}

for c in sorted(avg_ttft):
    print(f"Concurrency {c}: {avg_ttft[c]:.3f} ms")