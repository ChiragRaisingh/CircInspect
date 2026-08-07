# Copyright 2026 UBC Quantum Software and Algorithms Research Lab

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Shared plotting utility for performance_tests CSVs.

Every benchmark script in this suite writes a CSV with the schema
`<resource_value>,total_time,processing_time,execution_time` (one row per
rerun at a given resource level, e.g. depth, num_qubits, gates_outside,
...). This script groups those rows by resource level and produces two
PNGs next to the input CSV:

  <name>_scaling.png   line chart of mean total/processing/execution time
                        vs. resource level, with std-dev error bars.
  <name>_breakdown.png stacked bar chart, one bar per resource level,
                        split into mean execution time, mean processing
                        time, and the remaining "other overhead" (network
                        round-trip + outer server layer, i.e. total minus
                        the two in-sandbox timers).

Usage:
    python3 plot_results.py <results.csv> [<results2.csv> ...] [--outdir DIR]
"""
import argparse
import csv
import os
import re
import statistics
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Fixed categorical slots (see dataviz skill palette): slot 1 blue for
# execution, slot 2 orange for processing. "Other overhead" isn't a real
# category the user chose to add gates to — it's leftover network/outer
# server time — so it stays muted gray rather than taking a third
# categorical hue.
COLOR_EXECUTION = "#2a78d6"
COLOR_PROCESSING = "#eb6834"
COLOR_OVERHEAD = "#898781"
COLOR_GRID = "#e1e0d9"
COLOR_AXIS = "#c3c2b7"
COLOR_TEXT = "#0b0b0b"
COLOR_MUTED = "#52514e"
SURFACE = "#fcfcfb"


def _style_axes(ax):
    ax.set_facecolor(SURFACE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLOR_AXIS)
    ax.spines["bottom"].set_color(COLOR_AXIS)
    ax.tick_params(colors=COLOR_MUTED)
    ax.yaxis.grid(True, color=COLOR_GRID, linewidth=1)
    ax.set_axisbelow(True)


def load_grouped(csv_path):
    """Group a benchmark CSV's rows by resource level.

    Args:
        csv_path (str): path to a `<resource>,total_time,processing_time,
            execution_time` CSV produced by one of the performance_tests
            scripts.

    Returns:
        tuple(str, dict[float, dict[str, list[float]]]): the resource
        column's header name, and a mapping of resource value -> lists of
        total/processing/execution samples across reruns.
    """
    grouped = defaultdict(lambda: {"total": [], "processing": [], "execution": []})
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        resource_name = header[0]
        for row in reader:
            if not row:
                continue
            resource_value = float(row[0])
            grouped[resource_value]["total"].append(float(row[1]))
            grouped[resource_value]["processing"].append(float(row[2]))
            grouped[resource_value]["execution"].append(float(row[3]))
    return resource_name, dict(sorted(grouped.items()))


def _mean_std(values):
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return mean, std


def plot_scaling(csv_path, resource_name, grouped, out_path):
    """Line chart: resource level vs. mean total/processing/execution time."""
    levels = list(grouped.keys())
    total_mean, total_std = zip(*(_mean_std(grouped[lv]["total"]) for lv in levels))
    proc_mean, proc_std = zip(*(_mean_std(grouped[lv]["processing"]) for lv in levels))
    exec_mean, exec_std = zip(*(_mean_std(grouped[lv]["execution"]) for lv in levels))

    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style_axes(ax)

    ax.errorbar(
        levels, total_mean, yerr=total_std, label="Total time", color=COLOR_OVERHEAD,
        linestyle="--", linewidth=2, marker="o", markersize=5, capsize=3,
    )
    ax.errorbar(
        levels, proc_mean, yerr=proc_std, label="Processing time (CircInspect)",
        color=COLOR_PROCESSING, linewidth=2, marker="o", markersize=5, capsize=3,
    )
    ax.errorbar(
        levels, exec_mean, yerr=exec_std, label="Execution time (PennyLane)",
        color=COLOR_EXECUTION, linewidth=2, marker="o", markersize=5, capsize=3,
    )

    ax.set_xlabel(resource_name, color=COLOR_TEXT)
    ax.set_ylabel("Time (s)", color=COLOR_TEXT)
    ax.set_title(f"Scaling vs. {resource_name}", color=COLOR_TEXT, fontsize=13)
    ax.legend(frameon=False, labelcolor=COLOR_TEXT)
    fig.tight_layout()
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)


def plot_breakdown(csv_path, resource_name, grouped, out_path):
    """Stacked bar chart: one bar per resource level, split into mean
    execution / processing / other-overhead time."""
    levels = list(grouped.keys())
    proc_mean = [_mean_std(grouped[lv]["processing"])[0] for lv in levels]
    exec_mean = [_mean_std(grouped[lv]["execution"])[0] for lv in levels]
    total_mean = [_mean_std(grouped[lv]["total"])[0] for lv in levels]
    overhead_mean = [
        max(0.0, t - p - e) for t, p, e in zip(total_mean, proc_mean, exec_mean)
    ]

    fig, ax = plt.subplots(figsize=(max(8, len(levels) * 0.4), 5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style_axes(ax)

    x = range(len(levels))
    ax.bar(x, exec_mean, color=COLOR_EXECUTION, edgecolor=SURFACE, linewidth=1, label="Execution time (PennyLane)")
    ax.bar(x, proc_mean, bottom=exec_mean, color=COLOR_PROCESSING, edgecolor=SURFACE, linewidth=1, label="Processing time (CircInspect)")
    bottom_overhead = [e + p for e, p in zip(exec_mean, proc_mean)]
    ax.bar(x, overhead_mean, bottom=bottom_overhead, color=COLOR_OVERHEAD, edgecolor=SURFACE, linewidth=1, label="Other overhead (network/server)")

    ax.set_xticks(list(x))
    ax.set_xticklabels([str(int(lv)) if float(lv).is_integer() else str(lv) for lv in levels], rotation=45, ha="right", color=COLOR_MUTED)
    ax.set_xlabel(resource_name, color=COLOR_TEXT)
    ax.set_ylabel("Time (s)", color=COLOR_TEXT)
    ax.set_title(f"Total time breakdown vs. {resource_name}", color=COLOR_TEXT, fontsize=13)
    ax.legend(frameon=False, labelcolor=COLOR_TEXT, loc="upper left")
    fig.tight_layout()
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)


def clean_base_name(csv_path):
    """Derive a human-readable base name from a benchmark CSV path by
    stripping the trailing `_results_<timestamp>` suffix the test scripts
    append (e.g. `depth_results_1786054401.2994149.csv` -> `depth`)."""
    stem = os.path.splitext(os.path.basename(csv_path))[0]
    return re.sub(r"_results_\d+(?:\.\d+)?$", "", stem)


def plot_csv(csv_path, out_dir=None):
    resource_name, grouped = load_grouped(csv_path)
    if not grouped:
        print(f"No data rows found in {csv_path}, skipping.")
        return
    base = clean_base_name(csv_path)
    target_dir = out_dir or os.path.dirname(csv_path) or "."
    os.makedirs(target_dir, exist_ok=True)
    scaling_path = os.path.join(target_dir, f"{base}_scaling.png")
    breakdown_path = os.path.join(target_dir, f"{base}_breakdown.png")
    plot_scaling(csv_path, resource_name, grouped, scaling_path)
    plot_breakdown(csv_path, resource_name, grouped, breakdown_path)
    print(f"Wrote {scaling_path} and {breakdown_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot performance_tests benchmark CSVs.")
    parser.add_argument("csvs", nargs="+", help="Benchmark CSV file(s) to plot.")
    parser.add_argument(
        "--outdir", default=None,
        help="Directory to write PNGs into (default: next to each input CSV).",
    )
    args = parser.parse_args()
    for path in args.csvs:
        plot_csv(path, out_dir=args.outdir)
