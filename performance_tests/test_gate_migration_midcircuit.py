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
An experiment combining the gate-migration and mid-circuit measurement
benchmarks: the "unit" being moved from inline-in-the-qnode to an
individual outside helper function is a mid-circuit measurement paired
with a conditional gate (rather than a bare gate, as in
test_gate_migration.py). The total number of units stays fixed at
TOTAL_UNITS; only the inside/outside split changes.
"""
import time
from helpers import vis_circuit

# See test_midcircuit_measurements.py: CircInspect's internal replay always
# rebuilds the qnode without mcm_method, so it falls back to deferred-
# measurement simulation (one ancilla wire per qp.measure()) regardless of
# the source circuit's own mcm_method -- state-vector cost O(2**(2+units)).
# TOTAL_UNITS has to stay well inside that limit (12 is fast; 16+ starts
# failing, 40 OOMs) since every level in this sweep uses the same total
# unit count, just split differently between inline and helper functions.
RERUNS_PER_CASE = 10
TOTAL_UNITS = 12
STEP = 2


def test_generator(units_outside, total_units=TOTAL_UNITS):
    units_inside = total_units - units_outside
    code = """
import pennylane as qp
dev = qp.device("default.qubit", wires=2)
"""
    for i in range(units_outside):
        code += """
def helper_unit_""" + str(i) + """():
    m = qp.measure(0)
    qp.cond(m, qp.X)(wires=1)
"""
    code += """
@qp.qnode(dev, mcm_method="tree-traversal")
def circuit():"""
    for i in range(units_inside):
        code += """
    m_in_""" + str(i) + """ = qp.measure(0)
    qp.cond(m_in_""" + str(i) + """, qp.X)(wires=1)"""
    for i in range(units_outside):
        code += """
    helper_unit_""" + str(i) + """()"""
    code += """
    return qp.probs(wires=[0, 1])
circuit()
"""
    return code


with open("gate_migration_midcircuit_results_" + str(time.time()) + ".csv", "w") as results_file:
    results_file.write("units_outside,total_time,processing_time,execution_time\n")
    for units_outside in range(0, TOTAL_UNITS + 1, STEP):
        print("Starting run, units_outside:", units_outside)
        for i in range(RERUNS_PER_CASE):
            result = vis_circuit(test_generator(units_outside))
            if result is not None:
                results_file.write(
                    f"{units_outside},{result['total']},{result['processing']},{result['execution']}\n"
                )
