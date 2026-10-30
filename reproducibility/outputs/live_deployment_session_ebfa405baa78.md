# Live deployment evidence: Cowrie-to-HyShield SIEM session

**Evidence date:** 2026-10-30  
**Repository branch:** `snapshot/current-project`  
**Session ID:** `ebfa405baa78`

## Observed session

The HyShield SIEM Session Investigation page displayed the session `ebfa405baa78` with:

- Source IP: `127.0.0.1` (controlled localhost test; not external attacker traffic)
- Protocol: SSH
- Session status: Closed
- Duration: 58 seconds
- Risk level: Medium
- Threat score: 20/100
- Captured commands: `clear`, `whoami`, `pwd`, `ls /`, `cat /etc/os-release`
- Timeline included connection, SSH fingerprint, successful root login, terminal size, locale, and command activity.

The dashboard screenshot was supplied in the ChatGPT conversation on 2026-10-30. It showed the Session Investigation page and the details above. The screenshot image itself is not included in this commit; retain the original conversation attachment or add the locally saved screenshot as `screenshots/06_SIEM_Session_Investigation.png` when available.

## Related Cowrie evidence observed during the same investigation

The Cowrie JSON log contained the same session ID with:

- Start: `2026-10-30T15:47:03Z`
- End: `2026-10-30T15:48:01Z`
- Source IP: `127.0.0.1`
- Destination port: `2222`
- Sensor: `Hyshield-dev`
- TTY log SHA-256: `d17202b79d7d40aac84658b701da32ba8352f42be396f19cb7524a908d5766cd`

The corresponding terminal interaction included `whoami`, `pwd`, `ls /`, and `cat /etc/os-release`.

## Docker execution evidence observed

The inspected `docker_executor.py` configured the execution container as `fake-ubuntu` and invoked commands through `sudo -n /usr/bin/docker exec -i fake-ubuntu bash -c ...`. The container was observed running, and the SSH terminal returned Ubuntu 22.04.5 environment information. This code/configuration evidence, together with the terminal output, supports the Docker execution stage; the terminal screenshot alone does not independently prove the execution backend.

## SIEM ingestion verification notes

The SIEM SQLite database at `python-siem/data/hyshield.db` contained 317 rows in `raw_events` when checked. Before the SIEM was started for this check, session `ebfa405baa78` was not found in the `sessions` or `raw_events` tables. After the SIEM dashboard was started, the Session Investigation page displayed that session. A post-start database query confirming the corresponding raw/session rows was not captured in the conversation, so this report treats dashboard display as the observed SIEM evidence and does not claim a separately verified database-row match.

## Interpretation and limitations

This is a controlled local deployment demonstration. `127.0.0.1` identifies localhost traffic, not a remote attacker. The dashboard's displayed risk score and timeline are application output for this session; they are not an independent security validation. The evidence demonstrates the observed session investigation view and captured command activity, but does not by itself establish Docker escape resistance, external network exposure, or a production-scale deployment.

## Evidence status

- [x] Dashboard session investigation page observed in supplied screenshot.
- [x] Cowrie JSON session record and command events inspected in the terminal.
- [x] DockerExecutor configuration and running `fake-ubuntu` container inspected.
- [x] SSH terminal command execution observed.
- [ ] Original screenshot image committed to this directory.
- [ ] Post-start SQLite query for this session captured.
- [ ] Separate Cowrie, Docker, and terminal screenshots committed as image files.
