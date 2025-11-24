#!/usr/bin/env python3
"""Merge multiple per-run benchmark JSON files into a single set of
benchmarks compatible with this project's `generate-report.py` parser.

Behavior:
- Scans the input directory for JSON files, sorts them by name.
- Loads the first benchmark object from each file and collects them.
- Builds a combined `profile` (streams, measured_rates, measured_concurrencies,
  strategy_types) and writes an output JSON containing one benchmark
  entry per input file — each benchmark's `args.profile` is set to the
  combined profile while keeping the original `strategy` and
  `strategy_index` for that file.

Usage:
  python tools/compile_benchmark_files.py -i multiple_files/vllm-x2 -o input/benchmarks-vllm-x2-merged.json
  python tools/compile_benchmark_files.py -i multiple_files/llm-d-intelligent-inference-x2 -o input/benchmarks-llmd-x2-merged.json
"""

import argparse
import json
import os
from glob import glob
from typing import Any, Dict, List, Optional


def load_first_benchmark(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Warning: failed to parse {path}: {e}")
        return None

    if isinstance(data, dict) and 'benchmarks' in data and isinstance(data['benchmarks'], list) and data['benchmarks']:
        return data['benchmarks'][0]
    if isinstance(data, dict) and 'type_' in data:
        return data
    if isinstance(data, list) and data:
        return data[0]
    return None


def merge_benchmark_files(input_dir: str) -> Dict[str, Any]:
    files = sorted([p for p in glob(os.path.join(input_dir, '*')) if os.path.isfile(p)])
    benchmarks: List[Dict[str, Any]] = []
    for fp in files:
        b = load_first_benchmark(fp)
        if b is None:
            print(f"Skipping (no benchmark found): {fp}")
            continue
        b = dict(b)
        b['__source_file'] = os.path.basename(fp)
        benchmarks.append(b)

    if not benchmarks:
        raise SystemExit(f"No benchmark entries found in {input_dir}")

    # Collect sweep-level arrays across files
    measured_rates: List[float] = []
    measured_concurrencies: List[float] = []
    streams: List[Any] = []
    strategy_types: List[Any] = []

    for b in benchmarks:
        b_args = b.get('args', {})
        b_profile = b_args.get('profile', {})

        mr = b_profile.get('measured_rates')
        if isinstance(mr, list):
            measured_rates.extend(mr)
        elif mr is not None:
            measured_rates.append(mr)

        mc = b_profile.get('measured_concurrencies')
        if isinstance(mc, list):
            measured_concurrencies.extend(mc)
        elif mc is not None:
            measured_concurrencies.append(mc)

        s = b_profile.get('streams')
        if s is None:
            s = b_args.get('strategy', {}).get('streams')
        if isinstance(s, list):
            streams.extend(s)
        elif s is not None:
            streams.append(s)

        st = b_profile.get('strategy_types')
        if isinstance(st, list):
            strategy_types.extend(st)
        elif st is not None:
            strategy_types.append(st)

    # Deduplicate while preserving order
    def uniq(seq: List[Any]) -> List[Any]:
        seen = set()
        out: List[Any] = []
        for x in seq:
            if isinstance(x, (float, int, str)):
                key = x
            else:
                key = json.dumps(x, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            out.append(x)
        return out

    measured_rates_u = uniq(measured_rates)
    measured_concurrencies_u = uniq(measured_concurrencies)
    streams_u = uniq(streams)
    strategy_types_u = uniq(strategy_types)

    # Build the combined profile (sweep) without strategy_indexes
    combined_profile: Dict[str, Any] = {}
    combined_profile['type_'] = 'concurrent'
    combined_profile['completed_strategies'] = len(benchmarks)
    if measured_rates_u:
        combined_profile['measured_rates'] = measured_rates_u
    if measured_concurrencies_u:
        combined_profile['measured_concurrencies'] = measured_concurrencies_u
    if streams_u:
        try:
            combined_profile['streams'] = sorted(streams_u)
        except Exception:
            combined_profile['streams'] = streams_u
    if strategy_types_u:
        combined_profile['strategy_types'] = strategy_types_u

    # Produce one benchmark object per input file, each carrying the combined profile
    out_benchmarks: List[Dict[str, Any]] = []
    for b in benchmarks:
        b_copy = dict(b)
        b_args = b_copy.setdefault('args', {})
        b_args['profile'] = dict(combined_profile)
        out_benchmarks.append(b_copy)

    for b in out_benchmarks:
        b['__combined_from'] = os.path.basename(input_dir.rstrip('/'))

    return {'benchmarks': out_benchmarks}


def main() -> None:
    parser = argparse.ArgumentParser(description='Merge benchmark JSON files into a combined set')
    parser.add_argument('--input-dir', '-i', required=True, help='Directory containing JSON benchmark files')
    parser.add_argument('--output', '-o', required=True, help='Output JSON file path')

    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    combined = merge_benchmark_files(args.input_dir)

    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"Wrote combined benchmark file: {args.output}")


if __name__ == '__main__':
    main()
