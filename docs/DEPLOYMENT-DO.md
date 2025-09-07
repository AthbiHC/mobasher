## DigitalOcean Deployment Plan (High-Level)

This guide describes how to deploy Mobasher to a single DigitalOcean droplet with persistent storage, background services, secure ingress, and built-in monitoring.

### 1) Droplet and storage
- Ubuntu 24.04. Suggested size for API + recorder + ASR + monitoring: 8 vCPU / 16 GB RAM (adjust as needed).
- Attach a Block Storage volume for persistent data (e.g., 200–500 GB) mounted at `/mnt/media-data`.
- Optional: Use DigitalOcean Managed PostgreSQL and Managed Redis instead of local containers.
- Optional: Domain and subdomains, e.g., `api.example.com`, `grafana.example.com`.

### 2) Create non-root user and harden SSH
```bash
adduser mobasher && usermod -aG sudo mobasher
rsync -av ~/.ssh /home/mobasher && chown -R mobasher:mobasher /home/mobasher/.ssh
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload ssh
```

### 3) System packages and firewall
```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install git curl build-essential ffmpeg jq unzip ufw
sudo ufw allow OpenSSH
sudo ufw allow 80,443/tcp
sudo ufw allow 9090,3000/tcp   # Prometheus, Grafana (restrict later or reverse-proxy)
sudo ufw enable
```

### 4) Install Docker and Compose v2
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
docker compose version
```

### 5) Directory layout and data volume
```bash
sudo mkdir -p /opt/media-view /mnt/media-data
# If a Block Storage volume is attached (example device /dev/sda):
lsblk
sudo mkfs.ext4 -F /dev/sda
echo '/dev/sda /mnt/media-data ext4 defaults,nofail 0 2' | sudo tee -a /etc/fstab
sudo mount -a
sudo mkdir -p /mnt/media-data/data /mnt/media-data/postgres
sudo chown -R $USER:$USER /mnt/media-data
```

### 6) Clone repo and basic env
```bash
cd /opt/media-view
git clone https://github.com/AthbiHC/Media-View.git .
```

Create `/opt/media-view/.env`:
```bash
cat > /opt/media-view/.env <<'EOF'
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mobasher
DB_USER=mobasher
DB_PASSWORD=mobasher
REDIS_URL=redis://localhost:6379/0
MOBASHER_DATA_ROOT=/mnt/media-data/data
EOF
```

### 7) Database/Redis
- Option A (recommended): DO Managed PostgreSQL and Managed Redis; update `.env` accordingly.
- Option B: Local containers:
```bash
cd /opt/media-view/mobasher/docker
docker compose up -d postgres redis
```
Apply schema:
```bash
cd /opt/media-view/mobasher
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

### 8) Monitoring (Prometheus + Grafana)
```bash
cd /opt/media-view/mobasher/docker
docker compose --profile monitoring up -d prometheus grafana
# Prometheus: http://<droplet-ip>:9090 , Grafana: http://<droplet-ip>:3000 (admin/admin)
```
Later, reverse-proxy and restrict access.

### 9) Systemd services
API:
```ini
[Unit]
Description=Mobasher API
After=network.target

[Service]
User=mobasher
WorkingDirectory=/opt/media-view
EnvironmentFile=/opt/media-view/.env
ExecStart=/opt/media-view/mobasher/venv/bin/python -m uvicorn mobasher.api.app:app --host 127.0.0.1 --port 8010
Restart=always

[Install]
WantedBy=multi-user.target
```

Recorder:
```ini
[Unit]
Description=Mobasher Recorder
After=network.target

[Service]
User=mobasher
WorkingDirectory=/opt/media-view
EnvironmentFile=/opt/media-view/.env
ExecStart=/opt/media-view/scripts/mediaview recorder start --config mobasher/channels/kuwait1.yaml --heartbeat 15 --metrics-port 9108
ExecStop=/opt/media-view/scripts/mediaview recorder stop
Restart=always

[Install]
WantedBy=multi-user.target
```

ASR Worker (solo pool):
```ini
[Unit]
Description=Mobasher ASR Worker
After=network.target

[Service]
User=mobasher
WorkingDirectory=/opt/media-view
EnvironmentFile=/opt/media-view/.env
ExecStart=/opt/media-view/scripts/mediaview asr worker --pool solo --concurrency 1 --metrics-port 9109
Restart=always

[Install]
WantedBy=multi-user.target
```

ASR Scheduler:
```ini
[Unit]
Description=Mobasher ASR Scheduler
After=network.target

[Service]
User=mobasher
WorkingDirectory=/opt/media-view
EnvironmentFile=/opt/media-view/.env
ExecStart=/opt/media-view/scripts/mediaview asr scheduler --interval 30 --lookback 20
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mobasher-api mobasher-recorder mobasher-asr-worker mobasher-asr-scheduler
systemctl status mobasher-api mobasher-recorder mobasher-asr-worker mobasher-asr-scheduler | cat
```

### 10) Reverse proxy + TLS (Caddy)
```bash
sudo apt -y install debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo tee /etc/apt/trusted.gpg.d/caddy-stable.asc
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt -y install caddy
```
`/etc/caddy/Caddyfile`:
```caddy
api.example.com {
  reverse_proxy 127.0.0.1:8010
}

grafana.example.com {
  reverse_proxy 127.0.0.1:3000
}
```
```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

### 11) Validation
```bash
curl -s http://127.0.0.1:8010/metrics | head
curl -s http://127.0.0.1:9108/metrics | head
curl -s http://127.0.0.1:9109/metrics | head
```
Open Grafana and the “Mobasher Overview” dashboard.

### 12) Backlog + continuous processing
```bash
/opt/media-view/scripts/mediaview asr enqueue --limit 10000 | cat
# ASR scheduler keeps enqueuing thereafter every 30s
```

### 13) Updates
```bash
cd /opt/media-view
git pull
source mobasher/venv/bin/activate && pip install -r mobasher/requirements.txt
cd mobasher && alembic upgrade head
sudo systemctl restart mobasher-api mobasher-recorder mobasher-asr-worker
```

### 14) Security hardening
- Restrict 9090/3000 to localhost and access via Caddy only (or enable auth/VPN).
- UFW: default deny, open only 22/80/443.
- Fail2ban, unattended-upgrades.


