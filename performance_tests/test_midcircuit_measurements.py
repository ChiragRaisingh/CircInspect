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
An experiment to characterize how execution/processing time is affected by
the number of mid-circuit measurements (each paired with a conditional
gate) in the user code. Isolates the cost of CircInspect's mid-circuit
measurement linking (link_mid_circuit_measurements) as a function of count.
"""
import time
from helpers import vis_circuit

RERUNS_PER_CASE = 10
MIN_MEASUREMENTS = 2
# CircInspect's internal replay (server/helpers/command_tree_helpers.py's
# get_fcn_output_from_tree) always rebuilds the qnode without an explicit
# mcm_method, so it falls back to PennyLane's deferred-measurement
# simulation regardless of what the source circuit requests: one ancilla
# wire per qp.measure(), i.e. state-vector cost O(2**(2+num_measurements)).
# That's the very overhead this benchmark is measuring, but it also means
# the range has to stay well clear of the point where it blows up memory
# (confirmed OOM at 40; already 5-9s per call and starting to fail by 16) -
# 12 keeps it fast and comfortably inside CircInspect's current limits.
MAX_MEASUREMENTS = 13
STEP = 2


def test_generator(num_measurements):
    code = """
import pennylane as qp
dev = qp.device("default.qubit", wires=2)
@qp.qnode(dev, mcm_method="tree-traversal")
def circuit():"""
    for i in range(num_measurements):
        code += """
    m""" + str(i) + """ = qp.measure(0)
    qp.cond(m""" + str(i) + """, qp.X)(wires=1)
    qp.Hadamard(wires=0)"""
    code += """
    return qp.probs(wires=[0, 1])
circuit()
"""
    return code


with open("midcircuit_measurements_results_" + str(time.time()) + ".csv", "w") as results_file:
    results_file.write("num_mid_measurements,total_time,processing_time,execution_time\n")
    for num_measurements in range(MIN_MEASUREMENTS, MAX_MEASUREMENTS, STEP):
        print("Starting run, num_mid_measurements:", num_measurements)
        for i in range(RERUNS_PER_CASE):
            result = vis_circuit(test_generator(num_measurements))
            if result is not None:
                results_file.write(
                    f"{num_measurements},{result['total']},{result['processing']},{result['execution']}\n"
                )
