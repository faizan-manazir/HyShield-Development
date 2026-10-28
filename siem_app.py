from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
import datetime

app = Flask(__name__)
# Enable CORS so the frontend dashboard can access the API
CORS(app)

# --- Configuration ---
COWRIE_LOG_PATH = os.path.expanduser("~/cowrie/var/log/cowrie/cowrie.json")

# --- Helper Functions ---
def parse_cowrie_logs():
    """Parses Cowrie's JSON Lines log file."""
    attacks = []
    
    # Return dummy data if the log file doesn't exist yet to keep the UI active
    if not os.path.exists(COWRIE_LOG_PATH):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        return [
            {"timestamp": f"{today} 14:32:01", "ip": "192.168.1.105", "type": "Login Attempt", "details": "User: root | Pass: 123456", "status": "Access Denied"},
            {"timestamp": f"{today} 14:35:12", "ip": "45.33.22.11", "type": "Command Executed", "details": "cat /etc/passwd", "status": "Executed"},
            {"timestamp": f"{yesterday} 09:12:44", "ip": "8.8.8.8", "type": "Login Attempt", "details": "User: admin | Pass: admin", "status": "Shell Opened"}
        ]

    with open(COWRIE_LOG_PATH, 'r') as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                ts = event.get("timestamp", "").replace("T", " ")[:19]
                ip = event.get("src_ip", "Unknown")
                
                if event.get("eventid") in ["cowrie.login.failed", "cowrie.login.success"]:
                    attacks.append({
                        "timestamp": ts,
                        "ip": ip,
                        "type": "Login Attempt",
                        "details": f"User: {event.get('username')} | Pass: {event.get('password')}",
                        "status": "Shell Opened" if "success" in event.get("eventid") else "Access Denied"
                    })
                elif event.get("eventid") == "cowrie.command.input":
                    attacks.append({
                        "timestamp": ts,
                        "ip": ip,
                        "type": "Command Executed",
                        "details": event.get("input"),
                        "status": "Executed"
                    })
            except json.JSONDecodeError:
                continue
    return attacks

# --- API Endpoints ---
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "Online",
        "service": "AI-Driven Honeypot SIEM API",
        "endpoints": ["/api/stats", "/api/live", "/api/history"]
    })

@app.route('/api/stats', methods=['GET'])
def get_summary_stats():
    """Returns general threat statistics."""
    logs = parse_cowrie_logs()
    unique_ips = set(log.get("ip") for log in logs if log.get("ip") != "Unknown")
    login_attempts = [log for log in logs if log.get("type") == "Login Attempt"]
    commands = [log for log in logs if log.get("type") == "Command Executed"]
    
    return jsonify({
        "total_ssh_attempts": len(login_attempts),
        "unique_threat_ips": len(unique_ips),
        "active_executions": len(commands)
    })

@app.route('/api/live', methods=['GET'])
def get_live_feed():
    """Returns the most recent 10 events for the Live Feed."""
    logs = parse_cowrie_logs()
    logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify(logs[:10])

@app.route('/api/history', methods=['GET'])
def get_history():
    """Returns historical logs with dynamic filtering."""
    logs = parse_cowrie_logs()
    
    # Grab query parameters from the URL
    filter_type = request.args.get('type')
    filter_status = request.args.get('status')
    filter_date = request.args.get('date') # Expected format: YYYY-MM-DD

    # Apply filters if they exist
    if filter_type and filter_type != "All":
        logs = [log for log in logs if log.get("type") == filter_type]
    
    if filter_status and filter_status != "All":
        logs = [log for log in logs if log.get("status") == filter_status]
        
    if filter_date:
        logs = [log for log in logs if log.get("timestamp", "").startswith(filter_date)]

    logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    # Return up to 500 records for the history table to prevent browser lag
    return jsonify(logs[:500])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
