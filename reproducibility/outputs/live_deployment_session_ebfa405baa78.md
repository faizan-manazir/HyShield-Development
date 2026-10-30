# Live deployment evidence: Cowrie-to-HyShield SIEM sessions

**Evidence date:** 2026-10-30  
**Repository branch:** `snapshot/current-project`  
**Evidence directory:** [`reproducibility/screenshots/`](../screenshots/)

This note describes the eight screenshots committed with the reproducibility artifacts and distinguishes the two SIEM sessions visible in the dashboard evidence.

## Session A — Session Investigation

**Screenshot:** [06 — SIEM Session Investigation](../screenshots/06_SIEM_Session_Investigation.png)  
**Session ID:** `ebfa405baa78`

The HyShield SIEM Session Investigation page displayed:

- Source IP: `127.0.0.1` (controlled localhost test; not external attacker traffic)
- Protocol: SSH
- Session status: Closed
- Duration: 58 seconds
- Risk level: Medium
- Threat score: 20/100
- Captured commands: `clear`, `whoami`, `pwd`, `ls /`, `cat /etc/os-release`
- Timeline included connection, SSH fingerprint, successful root login, terminal size, locale, and command activity.

The dashboard timeline showed the connection at `15:47:03 UTC`, successful root login at `15:47:05 UTC`, and subsequent command activity through `15:47:41 UTC`. The page displayed the session as closed at `15:48:01 UTC`.

## Session B — Live Activity

**Screenshot:** [07 — SIEM Live Activity](../screenshots/07_SIEM_Live_Activity.png)  
**Session ID:** `ea51497b7804`

The Recent Telemetry view displayed a separate localhost session:

- Source IP: `127.0.0.1`
- Event stream timestamps: approximately `16:17:22–16:18:27 UTC`
- Observed command inputs: `clear`, `whoami`, `pwd`, `ls`, `ls /`
- Session-closed event reported a connection duration of 71.4 seconds.
- The visible event list included `cowrie.command.input`, `cowrie.log.closed`, and `cowrie.session.closed` records.

This is a separate session from `ebfa405baa78`. Its duration and events must not be attributed to Session A.

## Event Explorer — Session A

**Screenshot:** [08 — SIEM Event Explorer](../screenshots/08_SIEM_Event_Details.png)

The Event Explorer search field was filtered to `ebfa405baa78`. The displayed results included UTC timestamps, event types/IDs, source IP `127.0.0.1`, session ID, observed command activity, and ATT&CK technique tags `T1078` and `T1082`. Visible event IDs included `cowrie.command.input`, `cowrie.log.closed`, and `cowrie.session.closed`.

**Scope note:** Screenshot 08 shows the filtered event list. It does not show an expanded individual event payload. The filename is retained for the screenshot sequence, but the image should be described as an Event Explorer filtered-results view, not as proof that a full payload was inspected.

## Supporting deployment screenshots

The other committed screenshots provide the setup and telemetry context:

- [01 — Cowrie service running](../screenshots/01_Cowrie_Service_Running.png)
- [02 — SSH honeypot interaction](../screenshots/02_SSH_Honeypot_Interaction.png)
- [03 — Docker container running](../screenshots/03_Docker_Container_Running.png)
- [04 — Docker command execution](../screenshots/04_Docker_Command_Execution.png)
- [05 — Cowrie telemetry logs](../screenshots/05_Cowrie_Telemetry_Logs.png)

## Cowrie and Docker observations for Session A

The Cowrie JSON log inspected during the Session A investigation contained the same session ID with:

- Start: `2026-10-30T15:47:03Z`
- End: `2026-10-30T15:48:01Z`
- Source IP: `127.0.0.1`
- Destination port: `2222`
- Sensor: `Hyshield-dev`
- TTY log SHA-256: `d17202b79d7d40aac84658b701da32ba8352f42be396f19cb7524a908d5766cd`

The inspected `docker_executor.py` configured the execution container as `fake-ubuntu` and invoked commands through `sudo -n /usr/bin/docker exec -i fake-ubuntu bash -c ...`. The container was observed running, and the SSH terminal returned Ubuntu 22.04.5 environment information. The configuration and separate container/terminal screenshots support the execution-stage description; a terminal screenshot alone would not independently prove the backend.

## SIEM ingestion verification notes

The SIEM SQLite database at `python-siem/data/hyshield.db` contained 317 rows in `raw_events` when checked. Before the SIEM was started for the Session A check, session `ebfa405baa78` was not found in the `sessions` or `raw_events` tables. After the SIEM dashboard was started, the Session Investigation page displayed that session. A post-start database query confirming the corresponding raw/session rows was not captured, so this report treats dashboard display as the observed SIEM evidence and does not claim a separately verified database-row match.

## Interpretation and limitations

Both dashboard sessions shown here use `127.0.0.1`, identifying controlled localhost traffic rather than a remote attacker. The dashboard's risk score, ATT&CK tags, and timeline are application-generated outputs; the screenshots do not independently validate the scoring logic or prove malicious intent. The screenshots document observed deployment behavior and displayed telemetry. They do not establish event completeness, source authenticity, database reconciliation, Docker escape resistance, external network exposure, production-scale operation, or legal admissibility.

The 317-row database count is a point-in-time observation from the earlier check, not a count attributed to either screenshot session. No post-start SQL query was captured to independently reconcile the displayed Session A record with the database.

## Evidence status

- [x] Eight screenshot files committed under `reproducibility/screenshots/`.
- [x] Session A investigation screenshot documented (`ebfa405baa78`).
- [x] Separate Session B live-activity screenshot documented (`ea51497b7804`).
- [x] Event Explorer filtered-results screenshot documented for Session A.
- [x] Cowrie JSON session record and command events inspected for Session A.
- [x] DockerExecutor configuration and running `fake-ubuntu` container inspected.
- [ ] Post-start SQLite query for Session A captured.
- [ ] Expanded individual event payload screenshot captured (current screenshot 08 is the filtered event list).
