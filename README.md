# 🛡️ SysWatch — Cybersecurity Dashboard

A self-hosted local deploy & hosting dashboard with real-time monitoring, multi-IP checker, port scanner, and terminal. Built with Python Flask + HTML/CSS/JS.
<img width="1167" height="811" alt="image" src="https://github.com/user-attachments/assets/354acd0c-ea5b-4280-a620-00e5af76c442" />

---

## Features

| Page | Description |
|------|-------------|
| 📊 **Overview** | Live CPU, RAM, Disk, Network gauges + hostname, IP, uptime |
| 📋 **Live Logs** | Real-time SSE log stream — filter by INFO / WARN / ERROR |
| ⚙️ **Processes** | Top 15 processes by CPU — auto-refreshes every 10s |
| 🔌 **Open Ports** | All listening ports on this machine — click to copy |
| ⚡ **Services** | Register, start/stop, remove local/cloud services |
| 🌐 **IP Checker** | Monitor multiple remote IPs — ping, port scan, geolocation, HTTP status |
| 💻 **Terminal** | Run shell commands directly from the browser |

---

## IP Checker — How It Works

Add any IP address or hostname to monitor it:

- ✅ **Ping check** — Is the host alive?
- 🔍 **Port scan** — Scans 13 common ports (SSH, HTTP, MySQL, Redis, etc.)
- 🌍 **Geolocation** — Country, city, ISP via ip-api.com
- 🌐 **HTTP/HTTPS check** — Is the web server responding?
- ⚡ **Check All** — Bulk ping all registered hosts at once

---

## Quick Start

```bash
# 1. Install dependencies
pip3 install -r requirements.txt

# 2. Start SysWatch
python3 app.py

# 3. Open in browser
http://localhost:5000
```

Or use the launch script:
```bash
chmod +x start.sh && ./start.sh
```

---

## Project Structure

```
syswatch/
├── app.py              # Flask backend + all API routes
├── requirements.txt    # flask, psutil
├── start.sh            # One-click launch script
├── README.md
├── .env.example        # Environment variable template
├── CONTRIBUTING.md
├── LICENSE             # MIT
└── templates/
    └── index.html      # Full dashboard UI (single file)
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats` | System stats (CPU, mem, disk, net) |
| GET | `/api/processes` | Top 15 processes |
| GET | `/api/ports` | Open listening ports |
| GET | `/api/logs` | All logs |
| GET | `/api/logs/stream` | SSE live log stream |
| GET/POST | `/api/services` | Service registry |
| POST | `/api/ip/add` | Add remote host |
| GET | `/api/ip/list` | List all remote hosts |
| GET | `/api/ip/<id>/check` | Full scan (ping + ports + geo) |
| GET | `/api/ip/check-all` | Bulk ping all hosts |
| DELETE | `/api/ip/<id>/remove` | Remove host |
| POST | `/api/run` | Run shell command |

---

## Requirements

- Python 3.8+
- `flask`, `psutil`

---

## Security Note

Do **not** expose SysWatch to the public internet without adding authentication. The terminal executes real shell commands on your machine.

---

## License

MIT © SysWatch
