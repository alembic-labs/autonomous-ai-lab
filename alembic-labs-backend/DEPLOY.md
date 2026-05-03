# DEPLOY.md — ALEMBIC LABS backend

VPS production deployment guide for **Hetzner CCX** or **DigitalOcean**.
Tested on Ubuntu 22.04 LTS, 4 GB RAM (CCX13 / 2 vCPU + 8 GB recommended
for headroom — the agent loop is mostly I/O-bound but the DB benefits
from the extra RAM).

Target host: `api.alembic.bio`.

---

## 1. Provision the VPS

- Ubuntu 22.04 LTS
- 4 GB RAM minimum, 2 vCPU, 40 GB SSD
- Add your SSH key during provisioning

```bash
ssh root@<server-ip>
```

---

## 2. Harden the box

```bash
adduser alembic
usermod -aG sudo alembic
rsync --archive --chown=alembic:alembic ~/.ssh /home/alembic
passwd -l root  # disable root password login

apt update && apt upgrade -y
apt install -y ufw fail2ban
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

systemctl enable --now fail2ban
```

Edit `/etc/ssh/sshd_config`: `PermitRootLogin no`, `PasswordAuthentication no`,
then `systemctl restart ssh`.

Reconnect as the `alembic` user.

---

## 3. Install runtime dependencies

```bash
sudo apt install -y \
  python3.11 python3.11-venv python3.11-dev \
  build-essential \
  postgresql-15 postgresql-contrib \
  nginx \
  git
```

If 22.04 doesn't ship 3.11 by default, use the deadsnakes PPA:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

---

## 4. Create Postgres user and database

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE alembic WITH LOGIN PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
CREATE DATABASE alembic_labs OWNER alembic;
GRANT ALL PRIVILEGES ON DATABASE alembic_labs TO alembic;
SQL
```

---

## 5. Clone repo, venv, install deps

```bash
sudo mkdir -p /opt/alembic-labs
sudo chown alembic:alembic /opt/alembic-labs
cd /opt/alembic-labs
git clone <your-repo-url> .

python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
```

---

## 6. Production `.env`

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Key values:

```env
APP_ENV=production
LOG_LEVEL=INFO

ANTHROPIC_API_KEY=sk-ant-...
REPLICATE_API_TOKEN=r8_...
BOLTZ2_MODEL_ID=<from replicate.com/explore>
CHAI1_MODEL_ID=<from replicate.com/explore>

DATABASE_URL=postgresql+asyncpg://alembic:CHANGE_ME_STRONG_PASSWORD@localhost:5432/alembic_labs
DISTILLATION_INTERVAL_MINUTES=45
ENABLE_CHAI1=true
ENABLE_SCHEDULER=true

CORS_ALLOWED_ORIGINS=https://alembic.bio,https://www.alembic.bio
```

The first uvicorn boot will create tables and seed peptides automatically.

---

## 7. Initialise the database

```bash
cd /opt/alembic-labs
source venv/bin/activate
python -c "
import asyncio
from alembic_labs.db.session import init_db
from alembic_labs.db.seed import run_seed
asyncio.run(init_db())
asyncio.run(run_seed())
"
deactivate
```

This is also done automatically on the first uvicorn startup; running it
manually lets you confirm the DB connection independently.

---

## 8. systemd unit

```bash
sudo tee /etc/systemd/system/alembic-labs.service >/dev/null <<'EOF'
[Unit]
Description=ALEMBIC LABS Backend
After=network.target postgresql.service

[Service]
Type=simple
User=alembic
WorkingDirectory=/opt/alembic-labs
EnvironmentFile=/opt/alembic-labs/.env
ExecStart=/opt/alembic-labs/venv/bin/uvicorn alembic_labs.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now alembic-labs
sudo systemctl status alembic-labs
```

Tail logs:

```bash
sudo journalctl -u alembic-labs -f
```

---

## 9. Nginx reverse proxy

```bash
sudo tee /etc/nginx/sites-available/alembic-labs >/dev/null <<'EOF'
server {
    listen 80;
    server_name api.alembic.bio;

    client_max_body_size 8m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/alembic-labs /etc/nginx/sites-enabled/alembic-labs
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Point `api.alembic.bio` A record to the server's public IP before the
next step.

---

## 10. SSL via Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.alembic.bio --non-interactive --agree-tos -m ops@alembic.bio
sudo systemctl enable --now certbot.timer
```

`certbot` adds an auto-renewal cron via the timer; renewals will reload
nginx automatically.

---

## 11. Log rotation

```bash
sudo tee /etc/logrotate.d/alembic-labs >/dev/null <<'EOF'
/var/log/alembic-labs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 alembic alembic
    sharedscripts
    postrotate
        systemctl reload alembic-labs >/dev/null 2>&1 || true
    endscript
}
EOF
```

journalctl handles the systemd unit's stdout, but if you redirect logs to
`/var/log/alembic-labs/` (e.g. via a future file logger), this rotates
them.

---

## 12. Postgres nightly backup → S3 / Backblaze B2

```bash
sudo apt install -y restic awscli
sudo mkdir -p /opt/backups
sudo chown alembic:alembic /opt/backups

sudo tee /usr/local/bin/alembic-backup.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
TS=$(date -u +%Y%m%dT%H%M%SZ)
DUMP=/opt/backups/alembic_labs-${TS}.sql.gz
sudo -u postgres pg_dump alembic_labs | gzip -9 > "$DUMP"

# upload to your bucket of choice; AWS example shown
aws s3 cp "$DUMP" "s3://alembic-backups/postgres/" --storage-class STANDARD_IA

# keep last 14 local copies
ls -1t /opt/backups/alembic_labs-*.sql.gz | tail -n +15 | xargs -r rm -f
EOF
sudo chmod 750 /usr/local/bin/alembic-backup.sh

sudo tee /etc/cron.d/alembic-backup >/dev/null <<'EOF'
15 3 * * * root /usr/local/bin/alembic-backup.sh >> /var/log/alembic-backup.log 2>&1
EOF
```

Set AWS credentials via `aws configure --profile alembic` and `export
AWS_PROFILE=alembic` in `/root/.profile`, or use IAM-Roles-for-EC2 if
running on AWS.

---

## 13. Healthcheck cron

```bash
sudo tee /etc/cron.d/alembic-healthcheck >/dev/null <<'EOF'
*/5 * * * * alembic curl -fs --max-time 10 https://api.alembic.bio/api/health > /dev/null || echo "$(date -u) alembic-labs unhealthy" | tee -a /var/log/alembic-health.log
EOF
```

Wire this into your alerting (PagerDuty, Telegram bot, Healthchecks.io,
etc.) — for the MVP a tail-watching script is enough.

---

## post-deploy verification

```bash
curl -s https://api.alembic.bio/api/health
# {"status":"ok","lab":"ALEMBIC LABS"}

curl -s https://api.alembic.bio/api/agents/status | jq '.[].agent_name'
# "RESEARCHER" "LITERATURE" "STRUCTURAL" "CLINICAL" "COMMUNICATOR"

curl -s 'https://api.alembic.bio/api/folds?page=1&page_size=5' | jq '.total'

# After ~1 hour the first scheduled cycle should populate /api/folds.
sudo journalctl -u alembic-labs -n 200 | grep alembic.cycle
```

---

## rollback

```bash
sudo systemctl stop alembic-labs
cd /opt/alembic-labs
git fetch && git checkout <previous-tag>
source venv/bin/activate
pip install -r requirements.txt
deactivate
sudo systemctl start alembic-labs
```

If a migration has poisoned the DB, restore from the latest pg_dump:

```bash
gunzip -c /opt/backups/alembic_labs-<TS>.sql.gz | sudo -u postgres psql alembic_labs
```

---

## monitoring & cost guardrails

Tune via env vars and watch `journalctl`:

- Reduce frequency: `DISTILLATION_INTERVAL_MINUTES=90`.
- Disable Chai-1 cross-validation: `ENABLE_CHAI1=false`.
- Cap output: lower `max_tokens` in `agents/communicator.py` (default 6000).
- Watch for Replicate timeouts (`alembic.replicate.timeout` log events).
- Set up Anthropic + Replicate spend alerts in their dashboards.
