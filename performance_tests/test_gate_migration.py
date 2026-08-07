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
An experiment to characterize how execution/processing time changes as
gates move from being inline inside a qnode to living in individual
single-gate helper functions called from the qnode. The total gate count
stays fixed at TOTAL_GATES; only the split between "inline" and "via a
one-gate helper function" changes.
"""
import time
from helpers import vis_circuit

RERUNS_PER_CASE = 10
TOTAL_GATES = 200
STEP = 10


def test_generator(gates_outside, total_gates=TOTAL_GATES):
    gates_inside = total_gates - gates_outside
    code = """
import pennylane as qp
dev = qp.device("default.qubit", wires=1)
"""
    for i in range(gates_outside):
        code += """
def helper_gate_""" + str(i) + """():
    qp.Hadamard(wires=0)
"""
    code += """
@qp.qnode(dev)
def circuit():"""
    for _ in range(gates_inside):
        code += """
    qp.Hadamard(wires=0)"""
    for i in range(gates_outside):
        code += """
    helper_gate_""" + str(i) + """()"""
    code += """
    return qp.probs()
circuit()
"""
    return code


with open("gate_migration_results_" + str(time.time()) + ".csv", "w") as results_file:
    results_file.write("gates_outside,total_time,processing_time,execution_time\n")
    for gates_outside in range(0, TOTAL_GATES + 1, STEP):
        print("Starting run, gates_outside:", gates_outside)
        for i in range(RERUNS_PER_CASE):
            result = vis_circuit(test_generator(gates_outside))
            if result is not None:
                results_file.write(
                    f"{gates_outside},{result['total']},{result['processing']},{result['execution']}\n"
                )
