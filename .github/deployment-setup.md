# TimeTrackerApp – Continuous Deployment to Ubuntu EC2

A battle‑tested playbook that wires GitHub Actions to push every change on `main` straight to your running EC2 instance.

---

## 1  Prep your EC2 instance

| Step                                  | Command / Note        |
| ------------------------------------- | --------------------- |
| **1.1 SSH in**                        | `ssh ubuntu@<EC2‑IP>` |
| **1.2 Create a non‑root deploy user** |                       |

````bash
sudo adduser --disabled-password --gecos "" deploy
sudo usermod -aG sudo deploy   # optional sudo
```|
|**1.3 Give deploy ownership of the app**|`sudo chown -R deploy:deploy /var/www/timetrackerapp`|
|**1.4 Ensure a systemd unit** (`/etc/systemd/system/timetracker.service`)|
```ini
[Unit]
Description=TimeTrackerApp
After=network.target

[Service]
User=deploy
Group=deploy
WorkingDirectory=/var/www/timetrackerapp
ExecStart=/usr/bin/python3 app.py      # or gunicorn / uvicorn / docker
Restart=on-failure

[Install]
WantedBy=multi-user.target
```|
|**1.5 Reload + enable**|
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now timetracker
```|

---

## 2  Generate a CI‑only SSH key pair

```bash
ssh-keygen -t ed25519 -C "gh-actions-timetracker" -f ~/.ssh/timetracker_ci_ed25519
````

*Creates:*
• **timetracker\_ci\_ed25519** (private)
• **timetracker\_ci\_ed25519.pub** (public)

---

## 3  Install the public key on EC2

```bash
scp ~/.ssh/timetracker_ci_ed25519.pub deploy@<EC2-IP>:
ssh deploy@<EC2-IP>
mkdir -p ~/.ssh && chmod 700 ~/.ssh
cat ~/timetracker_ci_ed25519.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
rm ~/timetracker_ci_ed25519.pub
exit
```

> **Pro‑tip:** prepend a `command="…",restrict` option in `authorized_keys` for extra safety.

---

## 4  Pin the host key (anti‑MITM)

```bash
ssh-keyscan -H <EC2-IP> > ec2_known_hosts
```

Store the file contents for a GitHub secret in step 5.

---

## 5  Add GitHub repository secrets

| Secret             | Value                               |
| ------------------ | ----------------------------------- |
| `EC2_SSH_KEY`      | Entire **private** key (multi‑line) |
| `EC2_HOST`         | `deploy@<EC2-IP>` or public DNS     |
| `KNOWN_HOSTS`      | Contents of `ec2_known_hosts`       |
| `EC2_PORT` *(opt)* | Non‑22 port if used                 |

GitHub → **Settings → Secrets → Actions → New repository secret**.

---

## 6  Commit the workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to EC2

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.2.2
        with:
          host: ${{ secrets.EC2_HOST }}
          username: deploy
          key: ${{ secrets.EC2_SSH_KEY }}
          port: ${{ secrets.EC2_PORT || '22' }}
          known_hosts: ${{ secrets.KNOWN_HOSTS }}
          script_stop: true
          timeout: 10m
          script: |
            cd /var/www/timetrackerapp
            git fetch --all
            git reset --hard origin/main
            sudo systemctl restart timetracker
```

Commit & push:

```bash
git add .github/workflows/deploy.yml DEPLOYMENT_SETUP.md
git commit -m "CI: auto‑deploy to EC2"
git push origin main
```

---

## 7  First‑time smoke test

1. Watch the **Actions** tab – job should turn green.
2. Verify:

```bash
curl -I http://<EC2-IP>/health   # or open in a browser
```

Latest code should be live.

---

## 8  Rollback one‑liner

```bash
ssh -i ~/.ssh/timetracker_ci_ed25519 deploy@<EC2-IP> \
  "cd /var/www/timetrackerapp && git checkout <GOOD_SHA> && sudo systemctl restart timetracker"
```

---

## 9  Hardening & best practices

* **Security‑groups:** restrict port 22 to trusted IPs or use AWS Session Manager.
* **Environments:** add a protected *production* environment in Actions and require manual approval.
* **Branch protection:** require passing checks + reviews before `main` merges.
* **Key rotation:** CI‑only key — rotate periodically.
* **Log hygiene:** avoid `set -x`; appleboy redacts secrets but play it safe.

---

🎉 **Done!** Every push to `main` now auto‑deploys in under a minute. Want blue‑green or canaries next? Ping me anytime.
