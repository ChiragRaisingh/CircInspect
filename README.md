# CircInspect
[![Ubuntu 22.04](https://img.shields.io/badge/Verified%20on-Ubuntu%2022.04-darkorange?logo=ubuntu)](https://ubuntu.com/)
[![Fedora 38](https://img.shields.io/badge/Verified%20on-Fedora%2038-blue?logo=fedora)](https://fedoraproject.org/)

The [Quantum Software and Algorithms Research Lab](https://glassnotes.github.io/qsar.html) at UBC introduces [CircInspect](https://circinspect.ece.ubc.ca/), the first visual tool for debugging quantum programs in PennyLane.

CircInspect offers adaptive visualization of quantum circuits, enabling you to explore your quantum programs at varying levels of abstraction. You can zoom into subroutines, trace program outputs, and set breakpoints to isolate the source of a bug.

## How to get started with CircInspect

CircInspect visualizes the structure of your circuit and updates it dynamically as you type, providing immediate feedback and deeper insight into how code translates into quantum circuits, and also includes an integrated debugger for monitoring structural and behavioural changes at breakpoints.

We are researching how quantum developers debug their programs and CircInspect is a part of that effort. If you’re building algorithms with PennyLane, please give it a try and send us your feedback.


With the debugger, you can isolate and examine individual quantum circuit components while monitoring changes in program structure and output at breakpoints. To set a breakpoint, click on the line number. You can then click “Start Debugger” and use the buttons to step through your code.

<img width="1918" height="926" alt="image" src="https://github.com/user-attachments/assets/8fee62e4-3cd3-4aa8-be69-05b62f2cb7db" />


You can selectively observe inputs to subroutines and main circuit output by using the tree structure of commands under the circuit visualization. Click on the full screen button and click on one of the nodes to create a pop up with additional information. To see the output of the qnode, click on the top-most node of the command tree structure to see the output in the side panel popup, alternatively, you can hover over the same top-most node. 
<img width="1918" height="926" alt="image" src="https://github.com/user-attachments/assets/9ac50b88-1d7e-44d8-a4ad-239c2a9799af" />
<img width="1918" height="926" alt="image" src="https://github.com/user-attachments/assets/3ecee8f1-63cb-4ef2-9e5f-e8fe59fca10b" />


When using mid-circuit measurements, you can choose a postselect value for each mid-circuit measurement while the deugger is inactive. This will allow you to simulate the effect of postselection on the output of the circuit. To do so, click the fullscreen button on the command tree structure and click on the mid-circuit measurement node you want to apply a postselection value to. 
<img width="1918" height="926" alt="PostSelectionDemo" src="https://github.com/user-attachments/assets/8f191fe4-fca4-474d-8ce1-84bf0eecead7" />




CircInspect will dynamically update the quantum circuit visualization as the code is modified, even while a debugging session isn't active.
<img width="1918" height="926" alt="LiveDemo" src="https://github.com/user-attachments/assets/1971edea-e77c-42aa-a750-d331c0857815" />





## Installation

CircInspect is [freely available online](https://circinspect.ece.ubc.ca/). The instructions below are for local installation.

CircInspect is developed with React for the front-end, while the back-end is powered by Python, Flask and Docker. Some UI elements and code editor setup were inspired by the blog "[How to Build a Code Editor with React that Compiles and Executes in 40+ Languages](https://www.freecodecamp.org/news/how-to-build-react-based-code-editor/)", written by [Manu Arora](https://manuarora.in/).  MongoDB is used to track how users interact with the application, specifically to monitor which features they use and how often they engage with different parts of CircInspect.

To install the backend server requirements, go into `CircInspect` directory (project root) and run
```
poetry install
```

To install the frontend server, install Node.js, go into `CircInspect/client` directory and run
```
npm i
```

To install the database, follow the instructions in the [MongoDB website](https://www.mongodb.com/docs/manual/administration/install-community/).
To install docker, follow the instructions in the [Docker website](https://docs.docker.com/engine/install/).

Once docker is installed, build the docker image by navigating to the `CircInspect` directory (project root) and run 
```
docker build -t circinspect-sandbox -f server/sandbox/Dockerfile .
```

## Usage
To run the development servers:
1. If MongoDB is not running, run below command on your terminal to start MongoDB:
```
sudo systemctl start mongod
```
2. To check that MongoDB is running, run
```
sudo systemctl status mongod
```
3. Open two terminals terminal windows

4. On the first one, go into `CircInspect` directory (project root) and run
```
poetry run flask --app server.container_manager run --debug
```
5. On the second one, go into `CircInspect/client` directory and run
```
npm start
```

## Configurations
To enable authentication, change the `noAuth` flag in client/src/App.js to `false` and change the `NOAUTH` flag on server/app.py to `False`.

## Development and Testing 
Follow the instructions in [tests/README.md](tests/README.md) to run automated tests.
Follow the instructions in [performance_tests/README.md](performance_tests/README.md) to run performance tests that characterize the runtime of CircInspect.

## How to Contribute to CircInspect
CircInsepct is available open source under the Apache 2.0 License. Contributions are welcome. Please follow the instructions in the following link to contribute: [How to contribute?](https://github.com/QSAR-UBC/CircInspect-dev/blob/main/.github/CONTRIBUTING.md)

## Reference
The primary developers of CircInspect are Mushahid Khan
([@mushahidkhan835](https://github.com/mushahidkhan835)), Chirag Raisingh ([@ChiragRaisingh](https://github.com/ChiragRaisingh)) and Cihan Bosnali ([@CihanBosnali](https://github.com/CihanBosnali)).

The authors acknowledge funding from the NSERC CREATE in Quantum Computing
Program (grant number 543245), NSERC Alliance Quantum, UBC 4YF, and
UBC WLIURA programs. Thanks to Prashant Nair, QSAR Lab members, and the PennyLane team at Xanadu
for testing and providing feedback on CircInspect.

If you use CircInspect as part of your workflow, we would appreciate if you cite it using the BibTeX below.
```
@INPROCEEDINGS{10821435,
  author={Khan, Mushahid and Nair, Prashant J. and Di Matteo, Olivia},
  booktitle={2024 IEEE International Conference on Quantum Computing and Engineering (QCE)}, 
  title={CircInspect: Integrating Visual Circuit Analysis, Abstraction, and Real-Time Development in Quantum Debugging}, 
  year={2024},
  volume={01},
  number={},
  pages={1000-1006},
  doi={10.1109/QCE60285.2024.00119}}

```

