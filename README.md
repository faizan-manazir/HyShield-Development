# HyShield — Setup and Operations Guide

HyShield is a development integration built around Cowrie, with a Docker-backed Linux command executor and an optional Groq-powered output-refinement layer. This repository also contains the upstream Cowrie SSH/Telnet honeypot code.

> **Use responsibly:** deploy only on systems and networks you own or are explicitly authorized to operate. Keep the honeypot isolated from production assets. Do not expose the Docker socket or privileged container controls to untrusted users.

## Contents

- [Architecture](#architecture)
- [Requirements](#requirements)
- [1. Clone the project](#1-clone-the-project)
- [2. Create the Python environment](#2-create-the-python-environment)
- [3. Configure the Groq key](#3-configure-the-groq-key)
- [4. Prepare the Docker command container](#4-prepare-the-docker-command-container)
- [5. Configure Cowrie](#5-configure-cowrie)
- [6. Start the services](#6-start-the-services)
- [7. Test the setup](#7-test-the-setup)
- [Stopping services](#stopping-services)
- [Configuration reference](#configuration-reference)
- [Troubleshooting](#troubleshooting)
- [Security and Git workflow](#security-and-git-workflow)

## Architecture

The main custom components are:

| Component | Purpose |
|---|---|
| `bridge_server.py` | TCP bridge listening on `127.0.0.1:5050`; dispatches command requests to the executor and optionally refines non-empty output. |
| `docker_executor.py` | Executes commands inside the Docker container named `fake-ubuntu`, tracks a per-session working directory/history, and filters selected output. |
| `sanitizer.py` | Applies output substitutions and the current process-list transformation. |
| `ai_refiner.py` | Uses the Groq Python SDK for selected commands; reads `GROQ_API_KEY` from the environment and returns original output if the AI call fails. |
| `etc/cowrie.cfg` | Cowrie's local configuration. The `[llm]` section is separate from the Groq client used by `ai_refiner.py`. |
| `start_bridge.sh`, `start.sh` | Convenience scripts from the development environment. They contain absolute paths and may need adapting to your installation. |

The bridge and Cowrie's built-in LLM client are **separate integrations**. Changing `[llm] model` in `etc/cowrie.cfg` does not change the model in `ai_refiner.py`.

## Requirements

- Ubuntu Linux (the current development scripts use Ubuntu paths; other distributions may require adjustments).
- Python 3.10 or newer.
- Git.
- Docker Engine and permission to run Docker commands.
- A Groq API key if AI refinement is enabled.
- Network access for package installation and Groq API calls.
- Optional: `netcat-openbsd` for the `start_bridge.sh` port check.

## 1. Clone the project

The current development snapshot is on `snapshot/current-project`. Clone that branch explicitly:

```bash
git clone --branch snapshot/current-project --single-branch https://github.com/faizan-manazir/HyShield-Development.git
cd HyShield-Development
```

If you already cloned the repository, check your branch:

```bash
git branch --show-current
git status --short
```

Do not use `main` as the development branch unless the project maintainers intentionally change that workflow.

## 2. Create the Python environment

From the repository root:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git docker.io
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip wheel
pip install -r requirements.txt
pip install groq
```

The base `requirements.txt` contains Cowrie dependencies; the custom Groq client also needs the `groq` package. Install it explicitly unless it is added to the project's dependency manifest later.

Check that the Python imports work:

```bash
python -m py_compile ai_refiner.py bridge_server.py docker_executor.py sanitizer.py
python -c 'import groq; print("Groq SDK import OK")'
```

Cowrie is run from the repository source tree. Set its source path in the terminal where you start it:

```bash
export PYTHONPATH="$PWD/src"
```

## 3. Configure the Groq key

Create a private local environment file. Do not put the key in `ai_refiner.py`, `etc/cowrie.cfg`, README files, shell commands saved in history, or Git commits.

```bash
mkdir -p "$HOME/.config/hyshield"
chmod 700 "$HOME/.config/hyshield"
nano "$HOME/.config/hyshield/groq.env"
```

Add this line to the file, replacing the placeholder with your own key:

```bash
export GROQ_API_KEY="YOUR_GROQ_API_KEY"
```

Save the file, then restrict its permissions and load it into each terminal that launches the bridge:

```bash
chmod 600 "$HOME/.config/hyshield/groq.env"
source "$HOME/.config/hyshield/groq.env"
```

Verify that the variable exists without printing the secret:

```bash
if [ -n "$GROQ_API_KEY" ]; then echo "GROQ_API_KEY is set"; else echo "GROQ_API_KEY is missing"; fi
```

Test authentication and list the models available to the key:

```bash
python - <<'PY'
import os
from groq import Groq

key = os.getenv("GROQ_API_KEY", "").strip()
if not key:
    raise SystemExit("GROQ_API_KEY is not set")
models = Groq(api_key=key).models.list()
print("Groq authentication successful. Available models:")
for model in models.data:
    print(model.id)
PY
```

The model ID configured in `ai_refiner.py` must match a model returned for your account. The current snapshot uses `openai/gpt-oss-20b`. If the model is unavailable to your account, choose one from the returned list and update the model ID in `ai_refiner.py`.

The environment variable is inherited by child processes only. Load the private env file in the same terminal before starting `bridge_server.py`. For system services, configure a protected environment file in the service manager rather than relying on interactive shell startup files.

## 4. Prepare the Docker command container

The executor expects an **already-created, running container named `fake-ubuntu`**. The repository's `docker/Dockerfile` builds the Cowrie application image; it does not create this separate `fake-ubuntu` command container.

For a basic development container:

```bash
docker pull ubuntu:22.04
docker run -dit --name fake-ubuntu --hostname web-prod-01 ubuntu:22.04 bash
docker exec -it fake-ubuntu bash
```

Inside the container, install the command-line tools you need for your tests, for example:

```bash
apt-get update
apt-get install -y bash coreutils procps util-linux iproute2 iputils-ping curl wget grep sed gawk findutils
exit
```

Confirm the container exists and is running:

```bash
docker ps --filter name=fake-ubuntu
docker exec fake-ubuntu uname -a
```

**Docker permission note:** `docker_executor.py` currently invokes `sudo -n /usr/bin/docker`. That requires the current user to be able to run that command non-interactively. Test it with:

```bash
sudo -n /usr/bin/docker ps
```

If this fails, configure Docker access deliberately for your environment and adjust `docker_executor.py` if you intend to use `docker` without `sudo -n`. Membership in the `docker` group grants root-equivalent control over the host; do not grant it casually.

The executor uses a fixed container name, `fake-ubuntu`, and a 10-second command timeout. If you rename the container, update `CONTAINER` in `docker_executor.py`.

## 5. Configure Cowrie

Review `etc/cowrie.cfg` and `etc/userdb.txt` locally before starting Cowrie.

- `etc/cowrie.cfg` controls Cowrie settings, including hostname, backend, ports, logs, and optional built-in LLM settings.
- `etc/userdb.txt` controls honeypot login credentials.
- `var/` contains runtime data, logs, session recordings, and state.

The `[llm]` key and model in `etc/cowrie.cfg` are for Cowrie's built-in LLM implementation. The custom bridge's `ai_refiner.py` uses `GROQ_API_KEY` and its own model setting. Keep the built-in LLM disabled or configure it separately according to your intended Cowrie backend; do not assume the two settings are automatically shared.

The checked-in config is a template/snapshot. Put local secrets only in ignored local configuration or environment files. Confirm that no actual credentials, private host keys, or sensitive session data are staged before committing.

## 6. Start the services

Use **separate terminals**. The commands below avoid the absolute paths embedded in the development helper scripts.

### Terminal A — Docker container

```bash
docker start fake-ubuntu
```

### Terminal B — bridge server

```bash
cd /path/to/HyShield-Development
source venv/bin/activate
source "$HOME/.config/hyshield/groq.env"
python3 bridge_server.py
```

Expected startup message:

```text
[+] Bridge server listening on 127.0.0.1:5050
```

Keep this terminal running. If port 5050 is already occupied, find the process before starting another bridge instance.

### Terminal C — Cowrie

```bash
cd /path/to/HyShield-Development
source venv/bin/activate
export PYTHONPATH="$PWD/src"
twistd -n cowrie
```

Cowrie normally listens on its configured SSH/Telnet ports. Check the active `[ssh]` and `[telnet]` settings in `etc/cowrie.cfg`; do not assume a port if the configuration has been customized.

The provided `start.sh` and `start_bridge.sh` are convenience scripts from one development machine. They hard-code `/home/faizan/cowrie` and use `cowrie-env`, so they will not work unchanged if your checkout path or virtual-environment name differs. Review them before use.

## 7. Test the setup

With the bridge running, verify the local listener:

```bash
ss -ltnp | grep ':5050'
```

Verify the container separately:

```bash
docker ps --filter name=fake-ubuntu
docker exec fake-ubuntu bash -lc 'echo HELLO; uname -a; cat /proc/version'
```

Then connect to Cowrie on the SSH port configured in `etc/cowrie.cfg` and test basic commands such as:

```text
echo HELLO
whoami
hostname
uname -a
cat /proc/version
```

A direct `docker exec` test confirms that the container can execute the command; a successful Groq API test confirms API authentication. Test both layers independently if output is missing.

## Stopping services

- In a foreground terminal, press **Ctrl+C** to stop the process.
- To find the bridge PID:

  ```bash
  pgrep -af bridge_server.py
  ```

- Stop a specific bridge PID:

  ```bash
  kill <PID>
  ```

- If it does not exit, verify the PID and then use `kill -9 <PID>` as a last resort.
- Stop the test container when finished:

  ```bash
  docker stop fake-ubuntu
  ```

## Configuration reference

| Setting | Location | Notes |
|---|---|---|
| Groq key for the custom refinement client | Environment variable `GROQ_API_KEY` | Required only when a selected command invokes AI refinement. |
| Custom refinement model | `ai_refiner.py` | Must be available to the key; current value is `openai/gpt-oss-20b`. |
| Bridge bind address and port | `bridge_server.py` | Defaults to `127.0.0.1:5050`; keep it local unless you intentionally secure and redesign access. |
| Docker container name | `docker_executor.py` | Defaults to `fake-ubuntu`. |
| Cowrie settings | `etc/cowrie.cfg` | Separate from the custom bridge's environment-based Groq client. |
| Login database | `etc/userdb.txt` | Treat as local configuration. |
| Logs and runtime state | `var/` | May contain sensitive attacker activity and should be protected. |

## Troubleshooting

### `KeyError: 'GROQ_API_KEY'`

The environment variable is not available to the process that starts the bridge. In that same terminal, run:

```bash
source "$HOME/.config/hyshield/groq.env"
test -n "$GROQ_API_KEY" && echo "key loaded" || echo "key missing"
python3 bridge_server.py
```

Do not print the variable value in logs or paste it into issue reports.

### Groq returns `401 Invalid API Key`

Create or verify a valid key in the Groq Console. Confirm that the private env file contains the new key and reload it in the bridge terminal. Do not put the key into source code or commit it.

### Groq returns `model_not_found` or an access error

List the models available to the key using the test in [Configure the Groq key](#3-configure-the-groq-key), then select a model that appears in that list. Model availability can change over time.

### `sudo: a password is required` or Docker permission denied

The executor uses `sudo -n /usr/bin/docker`, which cannot prompt for a password. Check `sudo -n /usr/bin/docker ps` and configure host permissions appropriately. Do not solve this by exposing the Docker socket to untrusted users.

### Bridge cannot bind to port 5050

Check for an existing process with `pgrep -af bridge_server.py` and inspect the listener with `ss -ltnp | grep ':5050'`. Stop only the process you have identified.

### Commands return no output

Test the exact command directly inside `fake-ubuntu` with `docker exec`. Then inspect the bridge terminal for exceptions. The AI layer should return the original command output if refinement fails; if it does not, inspect the current `ai_refiner.py` and bridge logs.

### Cowrie command or import fails

Run from the repository root, activate the intended virtual environment, set `PYTHONPATH="$PWD/src"`, and check `python3 -m py_compile ai_refiner.py bridge_server.py docker_executor.py sanitizer.py`.

## Security and Git workflow

- Never commit Groq API keys, `active_password.txt`, local secrets, private SSH host keys, or unreviewed session logs.
- Keep `GROQ_API_KEY` in a protected local environment file and use `chmod 600`.
- Rotate any API key that was exposed in a public repository or commit.
- Treat the Docker command container and the host as separate trust boundaries. Do not expose bridge port 5050 publicly; it binds to loopback by default.
- Protect `var/` because logs and session recordings can contain sensitive data.
- Keep development work on `snapshot/current-project` unless a maintainer explicitly directs otherwise.

## Upstream Cowrie documentation

HyShield builds on Cowrie. For general Cowrie configuration and operation, consult the [Cowrie documentation](https://docs.cowrie.org/en/latest/).
