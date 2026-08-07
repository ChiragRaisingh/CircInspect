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

import socket
import time
import json
import requests
import subprocess
import string
import threading
import random
import pennylane as qp
import importlib
import importlib.metadata
from flask import Flask, request, jsonify, Response
from server import helpers
from pymongo import MongoClient


_session_ports = {}  # session_id -> host port for the sandbox HTTP server
_session_last_active = {}  # session_id -> last activity timestamp (time.time())

# How long to wait for the sandbox Flask server to become ready after container start
_HEALTH_CHECK_TIMEOUT = 10.0  # seconds
_HEALTH_CHECK_INTERVAL = 0.05  # seconds

_INACTIVITY_TIMEOUT = 3600  # seconds (1 hour)
_REAPER_INTERVAL = 60  # seconds between reaper checks


def _reaper_loop():
    """Background thread that stops containers idle for longer than _INACTIVITY_TIMEOUT."""
    while True:
        time.sleep(_REAPER_INTERVAL)
        now = time.time()
        expired = [
            sid
            for sid, last in list(_session_last_active.items())
            if now - last >= _INACTIVITY_TIMEOUT
        ]
        for sid in expired:
            stop_container(sid)


_reaper_thread = threading.Thread(target=_reaper_loop, daemon=True)
_reaper_thread.start()

NOAUTH = True

def create_app(test_config={}):

    db_client = MongoClient("localhost", 27017)
    db = db_client.circinspect
    db_sessions = db.sessions
    db_users = db.users
    db_bugs = db.bugs
    
    app = Flask(__name__, instance_relative_config=True)

    def find_user_by_token(token):
        """Find the database entry for user with the token.

        Args:
            token: the token user received for authentication

        Returns:
            If auth is on:
             1. Returns user data that is associated with the token
                if the data is present in the database.
             2. If no user is associated with the token, "None" is returned.
            If auth is off, a default object is returned that will
            allow authentication on other functions to always pass.
        """
        if NOAUTH:
            return {"email_address": "NOAUTH"}
        if type(token) is not str:
            return None
        user = db_users.find_one({"token": token})
        if type(user) is not dict:
            return None
        if user.get("expires", 0) < time.time():
            return None
        return user

    @app.route("/visualizeCircuit", methods=["POST"])
    def visualize_on_exec_server():
        """Send the user code to the execution server after
        the restricted code checks pass.

        Returns:
            The response sent back by the execution server
            is returned to user as a response.
        """
        if request.data == b"":
            body = request.form
        else:
            body = json.loads(request.data.decode("utf-8"))
        if body:
            if (find_user_by_token(body.get("token", None)) is None) and not test_config.get(
                "TESTMODE", False
            ):
                return Response(status=401)
            data = {
                "api_call": "/visualizeCircuit",
                "timestamp": body["timestamp"],
                "code": body["data"],
            }
            if body["policy_accepted"]:
                db_sessions.update_one(
                    {"session_id": body.get("session_id", "default")},  # filter
                    {"$push": {"actions": data}},  # update
                )

            code_received = body["data"]
            postselect_overrides = body.get("postselect_overrides", {})
            port = body.get("port")
            # initial check for malicious code
            restricted_code = helpers.check_for_restricted_code(code_received)
            if restricted_code != "":
                return jsonify({"error": restricted_code})

            exec_start = time.time()

            # send code to exec server to get the trace
            if not _is_healthy(port):
                return jsonify({
                    "error": [
                        "Sandbox is not responding. Please restart the sandbox and try again.",
                        "line unknown",
                    ]
                })
            try:
                response = requests.post(
                    f"http://127.0.0.1:{port}/execute",
                    json={
                        "code": code_received,
                        "postselect_overrides": postselect_overrides or {},
                    },
                    timeout=30,
                )
                exec_time = time.time() - exec_start
                if response.status_code != 200:
                    return jsonify({
                        "error": [
                            f"Sandbox HTTP error {response.status_code}: {response.text}",
                            "line unknown",
                        ]
                    })
                result = response.json()
                result["exec_time"] = exec_time
                session_id = body.get("session_id")
                if session_id:
                    _session_last_active[session_id] = time.time()

            except requests.exceptions.Timeout:
                return jsonify({
                    "error": ["Sandbox execution timed out.", "line unknown"]
                })
            except Exception as e:
                return jsonify({"error": [str(e), "line unknown"]})


            if response.status_code == 400:
                return jsonify({"error": ["Please run a quantum circuit", "line unknown"]})
            
            return jsonify(result), 200


    @app.route("/debugOutput", methods=["POST"])
    def debug_output():
        """Pass the debug endpoint information to the container manager
        to fetch the output and circuit image.

        Returns:
            JSON for frontend to render circuit output and image.
        """
        if request.data == b"":
            body = request.form
        else:
            body = json.loads(request.data.decode("utf-8"))
        if body:
            if (find_user_by_token(body.get("token", None)) is None) and not test_config.get(
                "TESTMODE", False
            ):
                return Response(status=401)
            
            port = body.get("port")
            node_ids = body.get("node_ids", [])
            transform_root_idx = body.get("transform_root_idx")
            postselect_overrides = body.get("postselect_overrides", {})

            if not _is_healthy(port):
                return jsonify({
                    "error": "Sandbox is not responding. Please restart the sandbox and try again."
                })

            sandbox_url = f"http://127.0.0.1:{port}/debugOutput"
            try:
                response = requests.post(sandbox_url, json={
                    "node_ids": node_ids,
                    "transform_root_idx": transform_root_idx,
                    "postselect_overrides": postselect_overrides
                    }, timeout=30)
                
                if response.status_code == 200:
                    session_id = body.get("session_id")
                    if session_id:
                        _session_last_active[session_id] = time.time()
                    return jsonify(response.json()), 200
                else:
                    return jsonify({"error": f"Error {response.status_code}: {response.text}"})
            except Exception as e:
                return jsonify({"error": str(e)})
        return Response(status=400)


    @app.route("/dc/sessionEnter", methods=["POST"])
    def collect_session_enter():
        """Handle data collection request sent when the user enters the
            application or accepts the data collection policy, and start
            a sandbox container for the session.
            If a session entry is not recorded, no data will be recorded
            from that session. This request does not affect user's
            interaction with the app.

        Returns:
            JSON response with sandbox port, or appropriate error status.
        """
        if request.data == b"":
            body = request.form
        else:
            body = json.loads(request.data.decode("utf-8"))
        if not body:
            return Response(status=400)

        user = find_user_by_token(body.get("token", None))
        if user is None:
            return Response(status=401)
        
        if not body["session_id"].startswith("TEST"):
            data = {
                "session_id": body["session_id"],
                "session_start_timestamp": body["timestamp"],
                "user_ip": request.remote_addr,
                "user_token": body["token"],
                "user_email": user["email_address"],
                "actions": [{"api_call": "/dc/sessionEnter", "timestamp": body["timestamp"]}],
            }
            if body["policy_accepted"]:
                db_sessions.insert_one(data)
                db_users.update_one(
                    {"token": body["token"]},
                    {"$push": {"sessions": body["session_id"]}},
                )

        session_id = body.get("session_id") or "default"
        try:
            port = start_container(session_id)
            return jsonify({"port": port}), 200
        except Exception as e:
            print(f"Failed to start sandbox for session {session_id}: {e}")
            return jsonify({"error": str(e)})


    @app.route("/dc/sessionExit", methods=["POST"])
    def collectSessionExit():
        """Handle data collection request that is sent when the user exits,
            and stop the sandbox container for the session.
            This request does not affect user's interaction with the app.
            Data is recorded only if user accepted the data collection policy.

        Returns:
            Empty REST response with appropriate status code.
        """
        if request.data == b"":
            body = request.form
        else:
            body = json.loads(request.data.decode("utf-8"))
        if not body:
            return Response(status=400)

        if find_user_by_token(body.get("token", None)) is None:
            return Response(status=401)
        
        if not body["session_id"].startswith("TEST"):
            data = {"api_call": "/dc/sessionExit", "timestamp": body["timestamp"]}
            if body["policy_accepted"]:
                db_sessions.update_one(
                    {"session_id": body["session_id"]},  # filter
                    {"$push": {"actions": data}},  # update
            )

        session_id = body.get("session_id") or "default"
        try:
            stop_container(session_id)
        except Exception as e:
            print(f"Failed to stop sandbox for session {session_id}: {e}")

        return Response(status=204)


    @app.route("/auth/send", methods=["POST"])
    def send_login_user():
        """Send email to the user including the link for them to login
            to CircInspect after checking that the email is in the allowlist.
            The link includes a token generated by this function.
            Save the new user information and token to the database.

        Returns:
            REST Response with status code 204 if email is sent, 401 if error.
        """
        if request.data == b"":
            body = request.form
        else:
            body = json.loads(request.data.decode("utf-8"))
        if body:
            email_address = body["email"]
            if "@" not in email_address:
                return Response(status=401)

            if not check_allowlist(email_address):
                return Response(status=401)

            # generate random token
            token = "".join(random.choices(string.ascii_letters + string.digits, k=9))

            # save token to database for use in verify_user()
            user = db_users.find_one({"email_address": email_address})
            if user is None:
                # first login
                db.users.insert_one(
                    {
                        "email_address": email_address,
                        "token": token,
                        "activated": int(time.time()),
                        "expires": int(time.time()) + 86400,  # 24h
                        "past_tokens": [],
                        "sessions": [],
                    }
                )
            else:
                activated = user.get("activated", None)
                if activated is not None:
                    if time.time() - activated < 5:
                        # user is spamming send button, do not generate token
                        return Response(status=204)
                    past_token = {
                        "token": user.get("token", ""),
                        "activated": user.get("activated", 0),
                        "expires": user.get("expires", 0),
                        "deactivated": min(user.get("expires", 0), int(time.time())),
                    }
                    db_users.update_one(
                        {"email_address": email_address},  # filter
                        {"$push": {"past_tokens": past_token}},  # update
                    )
                db_users.update_one(
                    {"email_address": email_address},
                    {
                        "$set": {
                            "token": token,
                            "activated": int(time.time()),
                            "expires": int(time.time()) + 86400,
                        }
                    },
                )

            # Because we do not use a mail client at the moment:
            print("Use link http://localhost:3000?" + token + " for " + email_address)
            return Response(status=204)


    @app.route("/auth/verify", methods=["POST"])
    def verify_user():
        """If auth is enabled, use the token sent by frontend
            to verify that the user has access to the application.

        Returns:
            JSON for frontend to use to render GUI.
        """
        if request.data == b"":
            body = request.form
        else:
            body = json.loads(request.data.decode("utf-8"))
        if body:
            user = find_user_by_token(body.get("token", None))
            if user is None:
                return Response(status=401)
            return jsonify({"email": user["email_address"], "pennylane": qp.__version__})


    @app.route("/library_version")
    def version():
        return jsonify(
            {
                "pennylane": safe_version("pennylane"),
                "numpy": safe_version("numpy"),
                "autograd": safe_version("autograd"),
                "jax": safe_version("jax"),
                "torch": safe_version("torch"),
                "tensorflow": safe_version("tensorflow"),
            }
        )


    @app.route("/bugreport", methods=["POST"])
    def bugreport():
        """Handle user sending a bug report via the in-app form

        Returns:
            Empty REST response with appropriate status code.
        """
        if request.data == b"":
            body = request.form
        else:
            body = json.loads(request.data.decode("utf-8"))
        if body:
            if find_user_by_token(body.get("token", None)) is None:
                return Response(status=401)
            data = {
                "api_call": "/bugreport",
                "timestamp": body["timestamp"],
                "description": body["description"],
                "user_email": body["user_email"],
            }
            if body["policy_accepted"]:
                db_sessions.update_one(
                    {"session_id": body["session_id"]},  # filter
                    {"$push": {"actions": data}},  # update
                )
            db_bugs.insert_one(
                {
                    "token": body["token"],
                    "session_id": body["session_id"],
                    "timestamp": body["timestamp"],
                    "email": body["user_email"],
                    "description": body["description"],
                }
            )
        return Response(status=204)

    return app


def start_container(session_id):
    """Starts a new Docker sandbox container for the given session.
    Allocates a dynamic port, spawns a container, and waits for it to become healthy.

    Args:
        session_id (str): The session identifier.

    Raises:
        RuntimeError: If the docker run command fails.
        TimeoutError: If the sandbox does not pass health checks in time.
    """
    stop_container(session_id)

    port = _find_free_port()

    container_name = f"circinspect-sandbox-{session_id}"
    result = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            container_name,
            "--network",
            "bridge",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "4g",
            "--cpus",
            "2",
            "-p",
            f"127.0.0.1:{port}:8080",
            "circinspect-sandbox",
        ],
        capture_output=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"docker run failed: {result.stderr.decode().strip()}")

    try:
        # Wait until the Flask server is accepting connections.
        _wait_for_ready(port)
    except TimeoutError:
        # Container failed to become ready, stop it and clear the port
        # so the next call can attempt a fresh start.
        subprocess.run(["docker", "stop", container_name], capture_output=True)
        raise

    # Only record the port after the server is confirmed healthy.
    _session_ports[session_id] = port
    _session_last_active[session_id] = time.time()

    return port


def stop_container(session_id):
    """Stops and removes the running sandbox container for the session.

    Args:
        session_id (str): The session identifier.
    """
    container_name = f"circinspect-sandbox-{session_id}"
    subprocess.run(["docker", "stop", "--time", "1", container_name], capture_output=True)
    _session_ports.pop(session_id, None)
    _session_last_active.pop(session_id, None)


def _find_free_port():
    """Ask the OS for a free localhost port by binding to port 0.

    Returns:
        int: A free system port number on localhost.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_ready(port):
    """Poll GET /health until the sandbox server responds or we time out.

    Args:
        port (int): The local port where the sandbox is exposed.

    Raises:
        TimeoutError: If the server fails to respond within the configured timeout.
    """
    deadline = time.time() + _HEALTH_CHECK_TIMEOUT
    url = f"http://127.0.0.1:{port}/health"
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200:
                return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(_HEALTH_CHECK_INTERVAL)
    raise TimeoutError(
        f"Sandbox container did not become ready within " f"{_HEALTH_CHECK_TIMEOUT}s on port {port}"
    )


def _is_healthy(port):
    """Checks if the sandbox Flask server on the given port responds to /health.

    Args:
        port (int): The local port to check.

    Returns:
        bool: True if the server returns a 200 OK status, False otherwise.
    """
    try:
        r = requests.get(f"http://127.0.0.1:{port}/health", timeout=1)
        return r.status_code == 200
    except Exception:
        return False

def check_allowlist(email_address):
        """Check that the email address is allowed to login using allowlist

        Args:
            email_address (string): user's email address

        Returns:
            Boolean: True if email address is in the list or from a domain in
            the list, False otherwise.
        """

        allowEmail = False
        with open("allowlist.txt") as file:
            for line in file:
                if "@" in line:
                    if line.split("\n")[0] == email_address:
                        allowEmail = True
                        break
                else:
                    allow_domain = line.split("\n")[0].split(".")
                    email_domain = email_address.split("@")[1].split(".")
                    if len(email_domain) < len(allow_domain):
                        continue
                    correct = True
                    for i in range(len(allow_domain)):
                        if email_domain[-1 - i] != allow_domain[-1 - i]:
                            correct = False
                            break
                    if correct:
                        allowEmail = True
                        break
        return allowEmail


def safe_version(pkg):
    try:
        return importlib.metadata.version(pkg)
    except Exception:
        return "unavailable"