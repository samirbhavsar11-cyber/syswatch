import os, subprocess, threading, time, json, psutil, platform, socket, concurrent.futures, urllib.request, urllib.error
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response
from collections import deque

app = Flask(__name__)
APP_NAME = "SysWatch"
APP_VERSION = "1.0.0"

log_buffer = deque(maxlen=500)
log_lock = threading.Lock()
services = {}
ip_targets = {}

def log(level, message, service=None):
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "level": level, "message": message, "service": service or "syswatch"}
    with log_lock:
        log_buffer.append(entry)

def get_system_stats():
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except:
        local_ip = "127.0.0.1"
    return {
        "cpu": cpu,
        "memory": {"percent": mem.percent, "used": round(mem.used/(1024**3),2), "total": round(mem.total/(1024**3),2)},
        "disk": {"percent": disk.percent, "used": round(disk.used/(1024**3),2), "total": round(disk.total/(1024**3),2)},
        "network": {"sent": round(net.bytes_sent/(1024**2),2), "recv": round(net.bytes_recv/(1024**2),2)},
        "platform": platform.system(), "hostname": socket.gethostname(), "ip": local_ip,
        "uptime": round(time.time() - psutil.boot_time(), 0)
    }

def get_running_processes():
    procs = []
    for proc in psutil.process_iter(['pid','name','cpu_percent','memory_percent','status']):
        try:
            i = proc.info
            if i['cpu_percent'] is not None:
                procs.append({"pid":i['pid'],"name":i['name'],"cpu":round(i['cpu_percent'],1),"mem":round(i['memory_percent'],1),"status":i['status']})
        except: pass
    procs.sort(key=lambda x: x['cpu'], reverse=True)
    return procs[:15]

def get_open_ports():
    ports, seen = [], set()
    for conn in psutil.net_connections(kind='inet'):
        if conn.status == 'LISTEN' and conn.laddr.port not in seen:
            seen.add(conn.laddr.port)
            try: pname = psutil.Process(conn.pid).name() if conn.pid else "unknown"
            except: pname = "unknown"
            ports.append({"port": conn.laddr.port, "host": conn.laddr.ip, "pid": conn.pid, "process": pname})
    return sorted(ports, key=lambda x: x['port'])

def probe_ip(target):
    ip, port, label = target["ip"], target.get("port"), target.get("label", target["ip"])
    result = {"ip":ip,"label":label,"port":port,"ping":False,"ping_ms":None,"port_open":None,"http_status":None,"http_ok":False,"checked_at":datetime.now().strftime("%H:%M:%S"),"error":None}
    try:
        param = "-n" if platform.system().lower() == "windows" else "-c"
        t0 = time.time()
        r = subprocess.run(["ping", param, "1", "-W", "1", ip], capture_output=True, timeout=3)
        ms = round((time.time()-t0)*1000, 1)
        result["ping"] = r.returncode == 0
        result["ping_ms"] = ms if r.returncode == 0 else None
    except Exception as e:
        result["error"] = str(e)
    if port:
        try:
            s = socket.socket(); s.settimeout(2)
            result["port_open"] = s.connect_ex((ip, int(port))) == 0; s.close()
        except: result["port_open"] = False
        try:
            req = urllib.request.Request(f"http://{ip}:{port}", headers={"User-Agent":"SysWatch/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                result["http_status"] = resp.status; result["http_ok"] = 200 <= resp.status < 400
        except urllib.error.HTTPError as e: result["http_status"] = e.code
        except: pass
    log("INFO" if result["ping"] else "WARN", f"[IPWatch] {label} ({ip}) → {'UP' if result['ping'] else 'DOWN'}" + (f" {result['ping_ms']}ms" if result['ping_ms'] else ""), "ipwatch")
    return result

def probe_all(targets):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(probe_ip, t): t for t in targets}
        for f in concurrent.futures.as_completed(futures):
            try: results.append(f.result())
            except Exception as e:
                t = futures[f]; results.append({"ip":t["ip"],"label":t.get("label",t["ip"]),"ping":False,"error":str(e)})
    return results

def background_monitor():
    while True:
        try:
            cpu = psutil.cpu_percent(interval=1); mem = psutil.virtual_memory().percent
            if cpu > 80: log("WARN", f"High CPU: {cpu}%")
            if mem > 85: log("WARN", f"High Memory: {mem}%")
            if int(time.time()) % 30 == 0: log("INFO", f"Heartbeat — CPU {cpu}% | MEM {mem}%")
        except Exception as e: log("ERROR", str(e))
        time.sleep(5)

threading.Thread(target=background_monitor, daemon=True).start()
log("INFO", f"{APP_NAME} v{APP_VERSION} started")
log("INFO", f"Platform: {platform.system()} {platform.release()}")

@app.route("/") 
def index(): return render_template("index.html")
@app.route("/api/stats") 
def api_stats(): return jsonify(get_system_stats())
@app.route("/api/processes") 
def api_processes(): return jsonify(get_running_processes())
@app.route("/api/ports") 
def api_ports(): return jsonify(get_open_ports())
@app.route("/api/logs") 
def api_logs():
    with log_lock: return jsonify(list(log_buffer))

@app.route("/api/logs/stream")
def api_logs_stream():
    def stream():
        last = 0
        while True:
            with log_lock: current = list(log_buffer)
            if len(current) > last:
                for e in current[last:]: yield f"data: {json.dumps(e)}\n\n"
                last = len(current)
            time.sleep(0.5)
    return Response(stream(), mimetype="text/event-stream")

@app.route("/api/services") 
def api_services(): return jsonify(list(services.values()))

@app.route("/api/services/add", methods=["POST"])
def api_add_service():
    d = request.json; name = d.get("name","").strip()
    if not name: return jsonify({"error":"Name required"}), 400
    port = d.get("port",""); sid = name.lower().replace(" ","-")
    services[sid] = {"id":sid,"name":name,"port":port,"url":d.get("url",f"http://localhost:{port}"),"description":d.get("description",""),"status":"running","added":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    log("INFO", f"Service: {name}:{port}", name); return jsonify({"ok":True,"service":services[sid]})

@app.route("/api/services/<sid>/remove", methods=["DELETE"])
def api_remove_service(sid):
    if sid in services: del services[sid]; return jsonify({"ok":True})
    return jsonify({"error":"Not found"}), 404

@app.route("/api/services/<sid>/toggle", methods=["POST"])
def api_toggle_service(sid):
    if sid in services:
        services[sid]["status"] = "stopped" if services[sid]["status"]=="running" else "running"
        log("INFO", f"{services[sid]['name']} → {services[sid]['status']}", services[sid]['name'])
        return jsonify({"ok":True,"status":services[sid]["status"]})
    return jsonify({"error":"Not found"}), 404

@app.route("/api/ipwatch") 
def api_ipwatch_list(): return jsonify(list(ip_targets.values()))

@app.route("/api/ipwatch/add", methods=["POST"])
def api_ipwatch_add():
    d = request.json; ip = d.get("ip","").strip()
    if not ip: return jsonify({"error":"IP required"}), 400
    port = d.get("port","").strip(); label = d.get("label",ip).strip()
    tid = ip.replace(".","_") + (f"_{port}" if port else "")
    ip_targets[tid] = {"id":tid,"ip":ip,"label":label,"port":port or None,"added":datetime.now().strftime("%H:%M:%S")}
    log("INFO", f"IPWatch: {label} ({ip})", "ipwatch"); return jsonify({"ok":True,"target":ip_targets[tid]})

@app.route("/api/ipwatch/<tid>/remove", methods=["DELETE"])
def api_ipwatch_remove(tid):
    if tid in ip_targets: del ip_targets[tid]; return jsonify({"ok":True})
    return jsonify({"error":"Not found"}), 404

@app.route("/api/ipwatch/probe", methods=["POST"])
def api_ipwatch_probe():
    d = request.json or {}; raw = d.get("targets")
    targets = [{"ip":t["ip"].strip(),"label":t.get("label",t["ip"]),"port":t.get("port")} for t in raw if t.get("ip")] if raw else list(ip_targets.values())
    if not targets: return jsonify({"error":"No targets"}), 400
    log("INFO", f"Probing {len(targets)} IPs...", "ipwatch")
    results = probe_all(targets)
    online = sum(1 for r in results if r.get("ping"))
    return jsonify({"results":results,"total":len(results),"online":online,"offline":len(results)-online})

@app.route("/api/run", methods=["POST"])
def api_run():
    cmd = (request.json or {}).get("command","").strip()
    if not cmd: return jsonify({"error":"No command"}), 400
    for b in ["rm -rf /","mkfs","dd if=",":(){:|:&}"]:
        if b in cmd: log("ERROR",f"Blocked: {cmd}"); return jsonify({"error":"Blocked"}), 403
    log("INFO", f"$ {cmd}")
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return jsonify({"output": r.stdout or r.stderr or "(no output)", "returncode": r.returncode})
    except subprocess.TimeoutExpired: return jsonify({"error":"Timeout"}), 408
    except Exception as e: return jsonify({"error":str(e)}), 500

if __name__ == "__main__":
    print(f"\n  ▄████████▄  ▄█   ▄█▄    ▄████████  ▄█     █▄     ▄████████     ███      ▄████████  ▄█    █▄")
    print(f"  ███    ███ ███ ▄███▀   ███    ███ ███     ███   ███    ███ ▀█████████▄ ███    ███ ███    ███")
    print(f"  ███    █▀  ███▐██▀     ███    █▀  ███     ███   ███    ███    ▀███▀▀██ ███    █▀  ███    ███")
    print(f"  ███        ▄█████▀     ███        ███     ███   ███    ███     ███   ▀ ███        ███    ███")
    print(f"  ███       ▀▀█████▄   ▀███████████ ███     ███ ▀███████████     ███   ▀███████████ ███    ███")
    print(f"  ███    █▄   ███▐██▄           ███ ███     ███   ███    ███     ███            ███ ███    ███")
    print(f"  ███    ███ ███ ▀███▄    ▄█    ███ ███ ▄█▄ ███   ███    ███     ███      ▄█    ███ ███    ███")
    print(f"  ████████▀  ███   ▀█▀  ▄████████▀   ▀███▀███▀   ███    █▀     ▄████▀  ▄████████▀   ▀██████▀")
    print(f"\n  SysWatch v{APP_VERSION} — Cyber Security Dashboard → http://localhost:5000\n")
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)