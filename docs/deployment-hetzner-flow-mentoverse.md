# Deployment Plan (Hetzner Ubuntu) for flow.mentoverse.eu

This runbook deploys mvPipeline to a single Hetzner VPS with:

- Nginx as reverse proxy and static frontend host
- FastAPI backend as a systemd service
- Tenant worker as a systemd service (one worker instance)
- MySQL on the same VPS
- TLS certificate from Let's Encrypt
- Non-root SSH user for Cursor-based live development

It is written for Ubuntu 24.04 LTS and domain `flow.mentoverse.eu`.

This server is treated as a long-running development instance (not immutable-only production), so the setup below keeps app code owned by a non-root user and allows safe SSH editing/deployment loops from Cursor.

## 1) Target Topology

- Public URL: `https://flow.mentoverse.eu`
- Frontend: built Vue app served by Nginx from `/var/www/flow.mentoverse.eu/frontend-dist`
- API: Uvicorn on `127.0.0.1:8000`
- Worker: background process `python -m app.worker` with `WORKER_TENANT_ID`
- Database: local MySQL (`mvpipeline` database)
- Generated files: repo `output/` served via Nginx under `/output/`

## 2) Preflight Inputs (fill these first)

- VPS public IPv4
- Domain A record: `flow.mentoverse.eu -> <your-vps-ip>`
- Deploy/development user on server (recommended): `deployer`
- Repo path (this guide uses): `/opt/mvPipeline`
- Tenant UUID for worker: `<WORKER_TENANT_ID>`
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
npm run build
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

Build frontend env:

```bash
cat > /opt/mvPipeline/frontend/.env.production <<'EOF'
VITE_API_URL=/api/v1
EOF
cd /opt/mvPipeline/frontend
npm run build
```

## 6) Filesystem Layout for Nginx

```bash
sudo mkdir -p /var/www/flow.mentoverse.eu
sudo rsync -a --delete /opt/mvPipeline/frontend/dist/ /var/www/flow.mentoverse.eu/frontend-dist/
sudo chown -R www-data:www-data /var/www/flow.mentoverse.eu
```

Ensure runtime output/log paths exist:

```bash
mkdir -p /opt/mvPipeline/output /opt/mvPipeline/logs
```

## 7) systemd Services

Create API service:

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
ExecStart=/opt/mvPipeline/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

# Allow deploy user writes while service reads env/code
UMask=0022

[Install]
WantedBy=multi-user.target
EOF
```

Create worker service (single tenant):

```bash
sudo tee /etc/systemd/system/mvpipeline-worker.service >/dev/null <<'EOF'
[Unit]
Description=mvPipeline Tenant Worker
After=network.target mysql.service mvpipeline-api.service
Wants=mysql.service

[Service]
User=deployer
Group=deployer
WorkingDirectory=/opt/mvPipeline
EnvironmentFile=/opt/mvPipeline/.env
Environment=WORKER_TENANT_ID=<WORKER_TENANT_ID>
ExecStart=/opt/mvPipeline/venv/bin/python -m app.worker
Restart=always
RestartSec=5
UMask=0022

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mvpipeline-api.service
sudo systemctl enable --now mvpipeline-worker.service
sudo systemctl status mvpipeline-api.service --no-pager
sudo systemctl status mvpipeline-worker.service --no-pager
```

## 8) Nginx Configuration

Create site config:

```bash
sudo tee /etc/nginx/sites-available/flow.mentoverse.eu >/dev/null <<'EOF'
server {
    listen 80;
    server_name flow.mentoverse.eu;

    root /var/www/flow.mentoverse.eu/frontend-dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
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
sudo ln -s /etc/nginx/sites-available/flow.mentoverse.eu /etc/nginx/sites-enabled/flow.mentoverse.eu
sudo nginx -t
sudo systemctl reload nginx
```

## 9) TLS (Let's Encrypt)

```bash
sudo certbot --nginx -d flow.mentoverse.eu
sudo systemctl status certbot.timer --no-pager
```

## 10) First-Time App Bootstrap

Create first user:

```bash
cd /opt/mvPipeline
source venv/bin/activate
python scripts/create_user.py --username admin --email you@example.com
```

Check API health and login flow:

```bash
curl -sS https://flow.mentoverse.eu/health
```

## 11) Verify End-to-End

- Open `https://flow.mentoverse.eu/login`
- Sign in with bootstrap user
- Confirm task list loads
- Trigger one task/job processing
- Confirm:
  - API logs: `journalctl -u mvpipeline-api -f`
  - Worker logs: `journalctl -u mvpipeline-worker -f`
  - Output file exists under `/opt/mvPipeline/output/<task-id>/`

## 12) Update / Deploy Workflow

Use this on each deploy:

```bash
ssh deployer@flow.mentoverse.eu <<'EOF'
set -euo pipefail
cd /opt/mvPipeline
git pull --ff-only
source venv/bin/activate
pip install -r requirements.txt
cd frontend
npm ci
npm run build
sudo rsync -a --delete /opt/mvPipeline/frontend/dist/ /var/www/flow.mentoverse.eu/frontend-dist/
sudo systemctl restart mvpipeline-api.service
sudo systemctl restart mvpipeline-worker.service
sudo systemctl reload nginx
EOF
```

For Cursor live development on the VPS:

- Connect Cursor via SSH as `deployer`.
- Edit code directly in `/opt/mvPipeline`.
- Restart services after backend changes:
  - `sudo systemctl restart mvpipeline-api.service`
  - `sudo systemctl restart mvpipeline-worker.service`
- Rebuild frontend after UI changes:
  - `cd /opt/mvPipeline/frontend && npm run build`
  - `sudo rsync -a --delete /opt/mvPipeline/frontend/dist/ /var/www/flow.mentoverse.eu/frontend-dist/`
  - `sudo systemctl reload nginx`

## 13) Operational Notes

- This project currently defaults several sensitive settings in code; always override through `/opt/mvPipeline/.env` in production.
- Back up at minimum:
  - MySQL database (daily dump)
  - `/opt/mvPipeline/output/` (if these assets are required for publish/audit)
- If you later add more tenants with high volume, run one worker service per tenant (`mvpipeline-worker@<tenant-id>.service` template).

## 14) Quick Troubleshooting

- API not reachable:
  - `sudo systemctl status mvpipeline-api`
  - `sudo journalctl -u mvpipeline-api -n 200 --no-pager`
- Worker idle/not processing:
  - validate `WORKER_TENANT_ID`
  - `sudo journalctl -u mvpipeline-worker -n 200 --no-pager`
- Frontend loads but API fails:
  - check `VITE_API_URL=/api/v1`
  - check Nginx `/api/` proxy block and reload
- 502 from Nginx:
  - API service likely down or not bound to `127.0.0.1:8000`
