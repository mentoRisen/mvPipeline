# Deployment Plan (Hetzner Ubuntu) for flow.mentoverse.eu

This runbook deploys mvPipeline to a single Hetzner VPS as a **long-running development environment**: the stack keeps running after you disconnect SSH or Cursor, and the **Vue UI is served by Vite** (hot reload) behind Nginx, not from a rebuilt `dist/` on every edit.

Includes:

- Nginx as TLS terminator and reverse proxy (Vite dev server + API + static output)
- **Vite dev server** on `127.0.0.1:3000` as a **systemd service** (`mvpipeline-frontend-dev`) so the frontend survives logout and reboot
- FastAPI backend as a systemd service
- Tenant worker as a systemd service (one worker instance)
- MySQL on the same VPS
- TLS certificate from Let's Encrypt
- Non-root SSH user for Cursor-based live editing

Written for Ubuntu 24.04 LTS and domain `flow.mentoverse.eu`.

Code under `/opt/mvPipeline` stays owned by `deployer`. You edit in place; **backend** changes need an API/worker restart; **frontend** changes are picked up by Vite without `npm run build` or rsync.

## 1) Target Topology

- Public URL: `https://flow.mentoverse.eu`
- **Frontend:** Vite (`npm run dev`) on `127.0.0.1:3000`, proxied by Nginx with WebSocket upgrade for HMR
- **API:** Uvicorn on `127.0.0.1:8000`, proxied at `/api/`
- **Worker:** `python -m app.worker` (all active tenants; optional `WORKER_TENANT_ID` to scope one)
- **Database:** local MySQL (`mvpipeline` database)
- **Generated files:** repo `output/` served by Nginx under `/output/`

Optional later: you can still run `npm run build` and serve static files from `/var/www/.../frontend-dist/` if you want a production-like preview; the default path below is **dev server only**.

## 2) Preflight Inputs (fill these first)

- VPS public IPv4
- Domain A record: `flow.mentoverse.eu -> <your-vps-ip>`
- Deploy/development user on server (recommended): `deployer`
- Repo path (this guide uses): `/opt/mvPipeline`
- Optional worker filter: `WORKER_TENANT_ID=<uuid>` if you want a single-tenant process; omit for all active tenants
- Secrets and tokens:
  - `AUTH_SECRET_KEY`
  - `OPENAI_API_KEY` (if needed)
  - tenant-level Instagram credentials (in DB tenant config)

## 3) Base Server Setup

SSH as root once:

```bash
apt update && apt upgrade -y
apt install -y git curl unzip build-essential python3 python3-venv python3-pip nodejs npm nginx mysql-server certbot python3-certbot-nginx
adduser --disabled-password --gecos "" deployer
usermod -aG sudo deployer
```

Install your SSH public key for the non-root user:

```bash
mkdir -p /home/deployer/.ssh
chmod 700 /home/deployer/.ssh
cat >> /home/deployer/.ssh/authorized_keys <<'EOF'
ssh-ed25519 <your-public-key> <your-comment>
EOF
chmod 600 /home/deployer/.ssh/authorized_keys
chown -R deployer:deployer /home/deployer/.ssh
```

Optional hardening:

```bash
ufw allow OpenSSH
ufw allow "Nginx Full"
ufw enable
```

After verifying non-root SSH works, disable root SSH login:

```bash
sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl reload sshd
```

## 4) MySQL Provisioning

Log into MySQL shell and create app database/user:

```bash
mysql -u root
```

```sql
CREATE DATABASE IF NOT EXISTS mvpipeline CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'mvpipeline'@'localhost' IDENTIFIED BY 'replace-with-strong-password';
GRANT ALL PRIVILEGES ON mvpipeline.* TO 'mvpipeline'@'localhost';
FLUSH PRIVILEGES;
```

## 5) Application Checkout and Environment

Switch to deploy user:

```bash
sudo -iu deployer
```

### 5.1) Configure Git SSH Access (private repo + commits)

Create a dedicated SSH key for Git operations on the VPS (separate from your personal laptop key):

```bash
ssh-keygen -t ed25519 -C "deployer@flow.mentoverse.eu" -f /home/deployer/.ssh/id_ed25519_github
chmod 700 /home/deployer/.ssh
chmod 600 /home/deployer/.ssh/id_ed25519_github
chmod 644 /home/deployer/.ssh/id_ed25519_github.pub
```

Configure SSH for GitHub:

```bash
cat > /home/deployer/.ssh/config <<'EOF'
Host github.com
  HostName github.com
  User git
  IdentityFile /home/deployer/.ssh/id_ed25519_github
  IdentitiesOnly yes
EOF
chmod 600 /home/deployer/.ssh/config
```

Print the public key and add it in GitHub:

```bash
cat /home/deployer/.ssh/id_ed25519_github.pub
```

In GitHub, add this key as either:

- **Deploy key (read-only)** if the server only needs pull access, or
- **Machine user/user SSH key (read-write)** if you will commit and push from the VPS.

Test access:

```bash
ssh -T git@github.com
```

Set commit identity for `deployer`:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Clone and prepare:

```bash
sudo mkdir -p /opt/mvPipeline
sudo chown -R deployer:deployer /opt/mvPipeline
git clone git@github.com:mentoRisen/mvPipeline.git /opt/mvPipeline
cd /opt/mvPipeline
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cd /opt/mvPipeline/frontend
npm install
```

`/opt/mvPipeline` remains owned by `deployer`, so Cursor can SSH as `deployer` and edit code directly without root.

Create backend env file:

```bash
cat > /opt/mvPipeline/.env <<'EOF'
DATABASE_URL=mysql+pymysql://mvpipeline:replace-with-strong-password@localhost:3306/mvpipeline
AUTH_SECRET_KEY=replace-with-long-random-secret
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=300
OPENAI_API_KEY=replace-if-used
SCHEDULER_TIMEZONE=UTC
WORKER_CHECK_INTERVAL_SECONDS=30
SCHEDULER_CHECK_INTERVAL_SECONDS=300
EOF
```

Frontend env for **this VPS** (browser talks to Nginx; use relative `/api/v1` so the same origin works through the proxy):

```bash
cat > /opt/mvPipeline/frontend/.env.development <<'EOF'
VITE_API_URL=/api/v1
EOF
```

Keep `.env.production` if you ever run a static build (`VITE_API_URL=/api/v1`); it is not required for daily dev.

## 6) Runtime Paths

Ensure output/log paths exist:

```bash
mkdir -p /opt/mvPipeline/output /opt/mvPipeline/logs
```

No rsync step is required for routine UI work; Nginx forwards the site to Vite.

## 7) systemd Services

### 7.1) API

```bash
sudo tee /etc/systemd/system/mvpipeline-api.service >/dev/null <<'EOF'
[Unit]
Description=mvPipeline FastAPI API
After=network.target mysql.service
Wants=mysql.service

[Service]
User=deployer
Group=deployer
WorkingDirectory=/opt/mvPipeline
EnvironmentFile=/opt/mvPipeline/.env
ExecStart=/opt/mvPipeline/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
Restart=always
RestartSec=5

UMask=0022

[Install]
WantedBy=multi-user.target
EOF
```

### 7.2) Worker (all active tenants)

```bash
sudo tee /etc/systemd/system/mvpipeline-worker.service >/dev/null <<'EOF'
[Unit]
Description=mvPipeline Worker (jobs + scheduler)
After=network.target mysql.service mvpipeline-api.service
Wants=mysql.service

[Service]
User=deployer
Group=deployer
WorkingDirectory=/opt/mvPipeline
EnvironmentFile=/opt/mvPipeline/.env
ExecStart=/opt/mvPipeline/venv/bin/python -m app.worker
Restart=always
RestartSec=5
UMask=0022

[Install]
WantedBy=multi-user.target
EOF
```

Optional: add `Environment=WORKER_TENANT_ID=<uuid>` under `[Service]` to limit this unit to one tenant.

### 7.3) Frontend (Vite dev server, persistent)

`VITE_DEV_PUBLIC_HOST` and `VITE_DEV_HMR_CLIENT_PORT` make HMR work over **wss** when users load `https://flow.mentoverse.eu`. Vite still listens only on localhost; Nginx terminates TLS.

```bash
sudo tee /etc/systemd/system/mvpipeline-frontend-dev.service >/dev/null <<'EOF'
[Unit]
Description=mvPipeline Vite dev server (frontend)
After=network.target mvpipeline-api.service

[Service]
Type=simple
User=deployer
Group=deployer
WorkingDirectory=/opt/mvPipeline/frontend
Environment=NODE_ENV=development
Environment=VITE_DEV_PUBLIC_HOST=flow.mentoverse.eu
Environment=VITE_DEV_HMR_CLIENT_PORT=443
ExecStart=/opt/mvPipeline/frontend/node_modules/.bin/vite
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Use the Vite binary as `ExecStart` so systemd tracks the real Node process (cleaner restarts than `npm run dev`).

Enable and start API and worker first, then the frontend:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mvpipeline-api.service
sudo systemctl enable --now mvpipeline-worker.service
sudo systemctl enable --now mvpipeline-frontend-dev.service
sudo systemctl status mvpipeline-api.service --no-pager
sudo systemctl status mvpipeline-worker.service --no-pager
sudo systemctl status mvpipeline-frontend-dev.service --no-pager
```

After `npm install` or `package.json` / lockfile changes (so `node_modules/.bin/vite` exists), restart the frontend service:

```bash
sudo systemctl restart mvpipeline-frontend-dev.service
```

## 8) Nginx Configuration

WebSocket upgrade map (HTTP context; load once):

```bash
sudo tee /etc/nginx/conf.d/websocket-upgrade.map.conf >/dev/null <<'EOF'
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}
EOF
```

Site config: proxy `/` to Vite, `/api/` to the API, `/output/` to disk.

```bash
sudo tee /etc/nginx/sites-available/flow.mentoverse.eu >/dev/null <<'EOF'
server {
    listen 80;
    server_name flow.mentoverse.eu;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /output/ {
        alias /opt/mvPipeline/output/;
        autoindex off;
    }
}
EOF
```

Enable and validate:

```bash
sudo ln -sf /etc/nginx/sites-available/flow.mentoverse.eu /etc/nginx/sites-enabled/flow.mentoverse.eu
sudo nginx -t
sudo systemctl reload nginx
```

If Certbot modified this file, ensure the **`location /`** block still proxies to `127.0.0.1:3000` with the WebSocket headers above after TLS setup.

## 9) TLS (Let's Encrypt)

```bash
sudo certbot --nginx -d flow.mentoverse.eu
sudo systemctl status certbot.timer --no-pager
```

Re-check Nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## 10) First-Time App Bootstrap

Create first user:

```bash
cd /opt/mvPipeline
source venv/bin/activate
python scripts/create_user.py --username admin --email you@example.com
```

Check API health:

```bash
curl -sS https://flow.mentoverse.eu/health
```

## 11) Verify End-to-End

- Open `https://flow.mentoverse.eu/login`
- Sign in with bootstrap user
- Confirm task list loads
- Edit a visible string in `frontend/src`, save, confirm the browser updates without a full reload (HMR)
- Trigger one task/job processing
- Confirm:
  - API logs: `journalctl -u mvpipeline-api -f`
  - Worker logs: `journalctl -u mvpipeline-worker -f`
  - Frontend logs: `journalctl -u mvpipeline-frontend-dev -f`
  - Output file exists under `/opt/mvPipeline/output/<task-id>/`

## 12) Update / Sync Workflow

Pull dependencies and restart **backend** services when Python or env changes; restart **frontend** when Node dependencies change. No static rsync for normal dev.

```bash
ssh deployer@flow.mentoverse.eu <<'EOF'
set -euo pipefail
cd /opt/mvPipeline
git pull --ff-only
source venv/bin/activate
pip install -r requirements.txt
cd frontend
npm ci
sudo systemctl restart mvpipeline-api.service
sudo systemctl restart mvpipeline-worker.service
sudo systemctl restart mvpipeline-frontend-dev.service
EOF
```

### 12.1) Daily editing (Cursor or SSH)

- Edit under `/opt/mvPipeline` as `deployer`.
- **Python / API / worker logic:**  
  `sudo systemctl restart mvpipeline-api.service`  
  `sudo systemctl restart mvpipeline-worker.service`
- **Vue / static assets in `frontend/src`:** no service restart; Vite reloads.
- **`package.json` / lockfile / `vite.config.js`:**  
  `sudo systemctl restart mvpipeline-frontend-dev.service`

### 12.2) Optional: static build preview

To test a production build without Vite:

```bash
cd /opt/mvPipeline/frontend && npm run build
sudo mkdir -p /var/www/flow.mentoverse.eu/frontend-dist
sudo rsync -a --delete /opt/mvPipeline/frontend/dist/ /var/www/flow.mentoverse.eu/frontend-dist/
```

You would temporarily point Nginx `location /` at `root /var/www/flow.mentoverse.eu/frontend-dist` (and `try_files`) instead of the Vite proxy; switch back when returning to dev-server mode.

## 13) Operational Notes

- Override sensitive settings through `/opt/mvPipeline/.env` on the server.
- Back up at minimum:
  - MySQL database (daily dump)
  - `/opt/mvPipeline/output/` (if these assets are required for publish/audit)
- If one worker cannot keep up with job volume, you can run additional worker processes (they compete on the same DB polling model) or split tenants using multiple units each with a different `WORKER_TENANT_ID`.
- The Vite dev server is convenient for a dedicated dev VPS; do not use this exact pattern for a hard production environment where you want immutable artifacts and no dev tooling on the edge.

## 14) Quick Troubleshooting

- **API not reachable:**  
  `sudo systemctl status mvpipeline-api`  
  `sudo journalctl -u mvpipeline-api -n 200 --no-pager`
- **Worker idle:** confirm at least one **active** tenant exists; check logs: `journalctl -u mvpipeline-worker -n 200 --no-pager`
- **Blank page or HMR disconnects:**  
  - `sudo systemctl status mvpipeline-frontend-dev`  
  - Confirm `VITE_DEV_PUBLIC_HOST` matches the browser hostname and port `443` for HMR  
  - Confirm Nginx has `Upgrade` / `Connection $connection_upgrade` on `location /`
- **API errors from the UI:** ensure `frontend/.env.development` has `VITE_API_URL=/api/v1` on the VPS; check Nginx `/api/` proxy block.
- **502 on `/`:** Vite service down or not listening on `127.0.0.1:3000`
- **502 on `/api/`:** API not bound to `127.0.0.1:8000`
