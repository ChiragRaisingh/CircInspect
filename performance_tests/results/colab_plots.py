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
Paste this whole file into a single Google Colab cell (or run it as a
Jupyter notebook cell) to visualize every performance_tests CSV at once.

It expects CSVs with the schema `<resource_value>,total_time,processing_time,
execution_time` -- the format written by every vis_circuit/debug_circuit
based script in performance_tests/ (test_depth.py, test_num_qubits.py,
test_subroutine_calls.py, test_nestedness.py, test_lines_of_code.py,
test_breakpoint_distance.py, test_gate_migration.py,
test_midcircuit_measurements.py, test_gate_migration_midcircuit.py).

In Colab, running this cell will pop up a file-upload dialog -- select all
the *_results_*.csv files you want to look at (multi-select is fine). In a
local Jupyter notebook (no google.colab available), it instead globs for
*_results_*.csv in the current directory.

For each CSV it draws two charts (same design as performance_tests/plot_results.py):
  - a scaling line chart: mean total/processing/execution time vs. resource
    level, with std-dev error bars across reruns.
  - a stacked bar chart: one bar per resource level, split into mean
    execution time, mean processing time, and remaining "other overhead"
    (network round-trip + outer server layer not captured by either
    in-sandbox timer).
"""
import csv
import glob
import os
import statistics
from collections import defaultdict

import matplotlib.pyplot as plt

# --- Get the CSVs into the runtime --------------------------------------
try:
    from google.colab import files
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

if IN_COLAB:
    print("Select all the *_results_*.csv files you want to visualize:")
    uploaded = files.upload()
    csv_paths = list(uploaded.keys())
else:
    csv_paths = sorted(glob.glob("*_results_*.csv"))

print(f"\nFound {len(csv_paths)} CSV(s):")
for p in csv_paths:
    print(" -", p)

# --- Fixed categorical colors (matches performance_tests/plot_results.py) ---
COLOR_EXECUTION = "#2a78d6"   # blue
COLOR_PROCESSING = "#eb6834"  # orange
COLOR_OVERHEAD = "#898781"    # muted gray -- not a chosen category, just leftover time
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

    Returns (resource_column_name, {resource_value: {"total": [...], "processing": [...], "execution": [...]}}).
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


def plot_scaling(resource_name, grouped, title_suffix=""):
    levels = list(grouped.keys())
    total_mean, total_std = zip(*(_mean_std(grouped[lv]["total"]) for lv in levels))
    proc_mean, proc_std = zip(*(_mean_std(grouped[lv]["processing"]) for lv in levels))
    exec_mean, exec_std = zip(*(_mean_std(grouped[lv]["execution"]) for lv in levels))

    fig, ax = plt.subplots(figsize=(8, 5), dpi=120)
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
    ax.set_title(f"Scaling vs. {resource_name}{title_suffix}", color=COLOR_TEXT, fontsize=13)
    ax.legend(frameon=False, labelcolor=COLOR_TEXT)
    fig.tight_layout()
    plt.show()


def plot_breakdown(resource_name, grouped, title_suffix=""):
    levels = list(grouped.keys())
    proc_mean = [_mean_std(grouped[lv]["processing"])[0] for lv in levels]
    exec_mean = [_mean_std(grouped[lv]["execution"])[0] for lv in levels]
    total_mean = [_mean_std(grouped[lv]["total"])[0] for lv in levels]
    overhead_mean = [
        max(0.0, t - p - e) for t, p, e in zip(total_mean, proc_mean, exec_mean)
    ]

    fig, ax = plt.subplots(figsize=(max(8, len(levels) * 0.4), 5), dpi=120)
    fig.patch.set_facecolor(SURFACE)
    _style_axes(ax)

    x = range(len(levels))
    ax.bar(x, exec_mean, color=COLOR_EXECUTION, edgecolor=SURFACE, linewidth=1, label="Execution time (PennyLane)")
    ax.bar(x, proc_mean, bottom=exec_mean, color=COLOR_PROCESSING, edgecolor=SURFACE, linewidth=1, label="Processing time (CircInspect)")
    bottom_overhead = [e + p for e, p in zip(exec_mean, proc_mean)]
    ax.bar(x, overhead_mean, bottom=bottom_overhead, color=COLOR_OVERHEAD, edgecolor=SURFACE, linewidth=1, label="Other overhead (network/server)")

    ax.set_xticks(list(x))
    ax.set_xticklabels(
        [str(int(lv)) if float(lv).is_integer() else str(lv) for lv in levels],
        rotation=45, ha="right", color=COLOR_MUTED,
    )
    ax.set_xlabel(resource_name, color=COLOR_TEXT)
    ax.set_ylabel("Time (s)", color=COLOR_TEXT)
    ax.set_title(f"Total time breakdown vs. {resource_name}{title_suffix}", color=COLOR_TEXT, fontsize=13)
    ax.legend(frameon=False, labelcolor=COLOR_TEXT, loc="upper left")
    fig.tight_layout()
    plt.show()


# --- Run for every CSV ----------------------------------------------------
for path in csv_paths:
    name = os.path.basename(path)
    resource_name, grouped = load_grouped(path)
    if not grouped:
        print(f"Skipping {name}: no data rows")
        continue
    print(f"\n=== {name} ({len(grouped)} levels, resource = {resource_name}) ===")
    plot_scaling(resource_name, grouped, title_suffix=f"  [{name}]")
    plot_breakdown(resource_name, grouped, title_suffix=f"  [{name}]")
