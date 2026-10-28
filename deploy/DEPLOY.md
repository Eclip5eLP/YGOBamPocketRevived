# Yu-Gi-Oh! BAM Pocket Revival Server Deployment Guide

This guide details how to deploy the revival server to `~/Documents/PythonBots/YGOBamPocketRevival/` on Linux behind a Cloudflare Tunnel for the public hostname `ygo.eclip5e.com`.

---

## 1. Remote Server Layout

The revival server and asset tree live under:
```text
~/Documents/PythonBots/YGOBamPocketRevival/
├── deploy/
│   ├── run.sh
│   └── ygo-revival.service
├── input/
│   └── data/
│       └── data/
│           └── air.com.konami.ygo/
│               └── com.konami.ygo/
│                   └── Local Store/
│                       ├── Data/
│                       │   └── JSONSave_A.sav
│                       ├── asset/
│                       │   ├── anim/
│                       │   ├── cards/
│                       │   ├── common/
│                       │   ├── font/
│                       │   ├── misc/
│                       │   ├── module/
│                       │   ├── transition/
│                       │   └── world/
│                       └── versionning.xml
├── server/
│   ├── amf3.py
│   └── server.py
└── work/
    ├── package_cache/
    └── server_requests.log
```

> [!NOTE]
> The path segment `"Local Store"` contains a space. Always wrap paths containing `"Local Store"` in quotes in shell scripts and commands.

---

## 2. Input File Inventory

The Python server (`server/server.py`) only reads the following files from `input/`:
1. `"Local Store/versionning.xml"` – Root XML asset manifest requested at startup (`/external_asset/android/versionning.xml`).
2. `"Local Store/Data/JSONSave_A.sav"` – Player save data returned during `GetPlayerSaveRequest`.
3. `"Local Store/asset/**"` – Asset directories for all 26 external packages (`series1`, `series2`, `anim`, `arena`, etc.).

No other databases, logs, or binaries from the original APK/backup are accessed by the server.

---

## 3. Transferring Files to Linux

### Option A: Rsync from Windows (PowerShell / Git Bash / WSL)
Set `REMOTE_USER` and `REMOTE_HOST` to your Linux box:
```bash
REMOTE="user@your-linux-ip"
DEST="~/Documents/PythonBots/YGOBamPocketRevival"

# 1. Create remote directories
ssh "${REMOTE}" "mkdir -p ${DEST}/server ${DEST}/deploy ${DEST}/work/package_cache \"${DEST}/input/data/data/air.com.konami.ygo/com.konami.ygo/Local Store/Data\""

# 2. Transfer server code and deployment scripts
scp -r server/amf3.py server/server.py "${REMOTE}:${DEST}/server/"
scp deploy/run.sh deploy/ygo-revival.service "${REMOTE}:${DEST}/deploy/"
ssh "${REMOTE}" "chmod +x ${DEST}/deploy/run.sh"

# 3. Transfer only the required Local Store assets
rsync -avz "input/data/data/air.com.konami.ygo/com.konami.ygo/Local Store/versionning.xml" \
    "${REMOTE}:${DEST}/input/data/data/air.com.konami.ygo/com.konami.ygo/Local Store/"

rsync -avz "input/data/data/air.com.konami.ygo/com.konami.ygo/Local Store/Data/JSONSave_A.sav" \
    "${REMOTE}:${DEST}/input/data/data/air.com.konami.ygo/com.konami.ygo/Local Store/Data/"

rsync -avz "input/data/data/air.com.konami.ygo/com.konami.ygo/Local Store/asset" \
    "${REMOTE}:${DEST}/input/data/data/air.com.konami.ygo/com.konami.ygo/Local Store/"
```

### Option B: Extract from Backup Archive on Linux
If the full backup archive (e.g. `ygo_backup.tar.gz`) is already on the Linux server:
```bash
TARGET_DIR="$HOME/Documents/PythonBots/YGOBamPocketRevival/input"
mkdir -p "$TARGET_DIR"

# Extract only the needed files from the backup archive:
tar -xzf ygo_backup.tar.gz \
    "data/data/air.com.konami.ygo/com.konami.ygo/Local Store/versionning.xml" \
    "data/data/air.com.konami.ygo/com.konami.ygo/Local Store/Data/JSONSave_A.sav" \
    "data/data/air.com.konami.ygo/com.konami.ygo/Local Store/asset" \
    -C "$TARGET_DIR"
```

---

## 4. Prebuilding Packages & Running the Server

On the Linux server, navigate to the project directory:
```bash
cd ~/Documents/PythonBots/YGOBamPocketRevival

# 1. Prebuild all 26 package zips into work/package_cache/
python3 server/server.py --prebuild

# 2. Run manually using run.sh
./deploy/run.sh
```

### Systemd User Unit (Auto-start on boot)
To install and start the background service without root:
```bash
mkdir -p ~/.config/systemd/user
cp deploy/ygo-revival.service ~/.config/systemd/user/

# Reload systemd user daemon and start service
systemctl --user daemon-reload
systemctl --user enable --now ygo-revival.service

# Check status and logs
systemctl --user status ygo-revival.service
journalctl --user -u ygo-revival.service -f

# Allow user service to run without active SSH session
loginctl enable-linger "$USER"
```

---

## 5. Cloudflare Tunnel Configuration Checklist

The mobile Adobe AIR client builds plain HTTP URLs (`"http://" + host + path`) and connects to port 80 (`EngineServerCom.as:255-256`).

### Cloudflare Dashboard Settings
In the Cloudflare Dashboard for the zone containing `ygo.eclip5e.com`:

1. **Cloudflare Tunnel Routing**:
   - In Zero Trust Dashboard -> Networks -> Tunnels:
   - Public Hostname: `ygo.eclip5e.com`
   - Service Type: `HTTP`
   - URL: `localhost:8087` (or `127.0.0.1:8087`)

2. **Disable "Always Use HTTPS"** (CRITICAL):
   - Go to **Rules** -> **Configuration Rules** (or **Page Rules**).
   - Create a rule for Hostname equals `ygo.eclip5e.com`:
     - Setting: **Automatic HTTPS Rewrites** -> `Off`
     - Setting: **Always Use HTTPS** -> `Off`
   - *Why*: The client does not support HTTPS/TLS on port 80; receiving a `301 Moved Permanently` or `302 Found` redirect causes connection failure.

3. **Security / Bot Settings**:
   - In **Security** -> **Settings**:
     - Ensure **Browser Integrity Check** is `Off` for `ygo.eclip5e.com` (can be disabled via Configuration Rules).
   - In **Security** -> **Bots**:
     - Ensure **Bot Fight Mode** does not block non-browser requests from the Android client. Create a WAF Skip rule if challenges occur:
       - URI Path starts with `/facebook/` or `/external_asset/` -> Skip Bot Management / Challenges.

---

## 6. Verification Commands

### Local Verification (on the Linux server itself)
```bash
# 0. Root Health Check (expect HTTP 200 "Yu-Gi-Oh! BAM Pocket Revival Server OK")
curl -i http://localhost:8087/

# 1. Flash Cross-Domain Policy
curl -i http://localhost:8087/crossdomain.xml

# 2. Asset Manifest
curl -i http://localhost:8087/external_asset/android/versionning.xml

# 3. AMF Gateway probe (expect HTTP 400 Empty POST body)
curl -i -X POST http://localhost:8087/facebook/proxy.html
```

> [!TIP]
> Ensure the server is bound to `0.0.0.0` (all interfaces) or `127.0.0.1`. If bound to a specific LAN IP (e.g. `192.168.178.127`), requests to `localhost` / `127.0.0.1` will be rejected by the OS with `curl: (7) Failed to connect`.

### Public Endpoint Verification (via Cloudflare Tunnel)
Test your public endpoint using curl from an external machine:

```bash
# 1. Test Cross-Domain Security Policy (expect HTTP 200 and XML content, NOT 301 or 403)
curl -i http://ygo.eclip5e.com/crossdomain.xml

# 2. Test Asset Manifest (expect HTTP 200 and XML versionning document)
curl -i http://ygo.eclip5e.com/external_asset/android/versionning.xml

# 3. Test AMF Gateway (expect HTTP 400 Empty POST body, confirming server answered)
curl -i -X POST http://ygo.eclip5e.com/facebook/proxy.html

# 4. Test Asset Version Validator Probe (expect HTTP 200 "versionvalidator_ok")
curl -i http://ygo.eclip5e.com/external_asset/android/1.11.1/versionvalidator

# 5. Run automated live check script
python tests/live_check.py --base http://ygo.eclip5e.com
```
