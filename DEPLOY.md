# Deploying to the server, with automatic deploys from GitHub

After this setup, every push to `main` runs the tests on GitHub and, if they pass, updates the server automatically.

```
push to main ──► GitHub Actions: tests ──► SSH to server ──► deploy/deploy.sh
                                                              git pull, docker compose up --build,
                                                              wait until healthy
```

The SSH key GitHub uses can only run `deploy/deploy.sh` on the server, nothing else.

Placeholders used below. Replace them with your values:

| Placeholder | Example |
|---|---|
| `SERVER_IP` | `65.108.1.2` |
| `symvolaia.example.gr` | the subdomain for the app, e.g. `symvolaia.client-domain.gr` |

---

## 1. Look at the server

```bash
ssh root@SERVER_IP            # or your usual user, then use sudo
cat /etc/os-release           # these steps assume Ubuntu or Debian
nproc; free -h; df -h /       # CPUs, RAM, free disk
sudo ss -tlnp | grep -E ':(80|443|8000) '   # what already listens on the web ports
```

- Needs roughly 4 GB of free RAM and 10 GB of disk for the app and the Whisper model.
- Note what owns ports 80/443 (usually `nginx`, or `apache2`). The steps below assume **nginx**; if it is something else (Apache, Plesk, Caddy, Traefik), stop at step 6 and ask.
- If something already uses port 8000, pick another port for `APP_PORT` in step 4.

## 2. Install Docker

Skip if `docker compose version` already works.

```bash
curl -fsSL https://get.docker.com | sudo sh
docker compose version
```

## 3. Create a `deploy` user and get the code

```bash
sudo adduser --disabled-password --gecos "" deploy
sudo usermod -aG docker deploy
sudo mkdir -p /opt/voice-to-text && sudo chown deploy:deploy /opt/voice-to-text
sudo -iu deploy               # everything until step 6 runs as "deploy"
```

The server pulls code from GitHub with a read-only **deploy key**:

```bash
ssh-keygen -t ed25519 -N "" -C "server pull" -f ~/.ssh/github_pull
cat ~/.ssh/github_pull.pub
```

On GitHub: **repository → Settings → Deploy keys → Add deploy key**. Paste the key, title "server pull", and leave **Allow write access unticked**.

```bash
cat >> ~/.ssh/config <<'CFG'
Host github.com
  IdentityFile ~/.ssh/github_pull
  IdentitiesOnly yes
CFG
ssh -o StrictHostKeyChecking=accept-new -T git@github.com   # "successfully authenticated" is the expected answer

git clone git@github.com:aptaliko/voice-to-text.git /opt/voice-to-text
cd /opt/voice-to-text
```

## 4. Configure

```bash
cp .env.example .env
nano .env
```

Set at least:

| Setting | Value |
|---|---|
| `APP_USERNAME` / `APP_PASSWORD` | the login for the page; use a long random password (`openssl rand -base64 24`) |
| `APP_CPUS` | at most the server's CPU count from `nproc` (half is kinder to the website) |
| `APP_MEMORY` | e.g. `4g`; must fit in the free RAM |
| `WHISPER_MODEL` | `large-v3-turbo` (default); `medium` or `small` if the server is weak |
| `APP_PORT` | `8000`, unless that port is taken |
| `AI_CORRECTION` | leave `false` on the server for now |

`.env` is not in git, so deploys never overwrite it.

## 5. First deploy by hand

```bash
./deploy/deploy.sh
```

The first run builds the image (a few minutes). It ends with `healthy` and `Deployed <commit>`.
The first dictation afterwards downloads the Whisper model (~1.6 GB) once.

## 6. Domain and HTTPS

Browsers only allow the microphone on `https://` pages, so the app needs a hostname and a certificate.

1. **DNS**: at the client's domain provider, add an **A record**: `symvolaia` → `SERVER_IP`. Check it with `dig +short symvolaia.example.gr` (may take a few minutes to an hour).
2. **nginx site with a certificate** (back as root or your sudo user: `exit` from the deploy user first).
   Replace `symvolaia.example.gr` with your subdomain, and `8000` if you changed `APP_PORT`:

   ```bash
   sudo apt-get install -y certbot python3-certbot-nginx
   sudo tee /etc/nginx/sites-available/symvolaia >/dev/null <<'NGINX'
   server {
       listen 80;
       server_name symvolaia.example.gr;
       client_max_body_size 200m;   # long dictations, multi-page PDFs
       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_read_timeout 300s;
           proxy_request_buffering off;
       }
   }
   NGINX
   sudo ln -s /etc/nginx/sites-available/symvolaia /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   sudo certbot --nginx -d symvolaia.example.gr
   ```

   certbot adds HTTPS and the http→https redirect to that file, and renews the certificate automatically.
   The client's website is not touched: it is a separate nginx site.

3. **Firewall** (only if `ufw` is active, see `sudo ufw status`): `sudo ufw allow 'Nginx Full'`.
   Port 8000 does not need opening; the app listens on localhost only.
4. Open `https://symvolaia.example.gr`, log in, try a dictation.

Optional, recommended: if the office has a fixed IP, allow only it. Add inside `location /`:
`allow OFFICE_IP; deny all;`, then `sudo nginx -t && sudo systemctl reload nginx`.

## 7. Let GitHub deploy automatically

On the server, as the deploy user (`sudo -iu deploy`), create the key GitHub Actions will use, restricted so it can **only** run the deploy script:

```bash
ssh-keygen -t ed25519 -N "" -C "github actions deploy" -f ~/.ssh/github_actions
echo "command=\"/opt/voice-to-text/deploy/deploy.sh\",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty $(cat ~/.ssh/github_actions.pub)" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
cat ~/.ssh/github_actions        # the PRIVATE key, for the next step
```

From your own computer, get the server's host key (so GitHub can verify it is talking to your server):

```bash
ssh-keyscan -t ed25519 SERVER_IP
```

On GitHub: **repository → Settings → Environments → New environment** named `production`. In it, **Add environment secret** for each:

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | `SERVER_IP` |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_SSH_KEY` | the whole private key printed above, including the `-----BEGIN/END …-----` lines |
| `DEPLOY_KNOWN_HOSTS` | the line printed by `ssh-keyscan` |
| `DEPLOY_PORT` | only if SSH is not on port 22 |

Then delete the private key from the server: `rm ~/.ssh/github_actions` (keep `github_actions.pub`; it is already in `authorized_keys`).

Optional: in the `production` environment you can add **Required reviewers** so each deploy waits for your click, or restrict it to the `main` branch.

## 8. Test it

GitHub → **Actions → Test and deploy → Run workflow** (or push any commit to `main`).
The `test` job runs the test suite; `deploy` runs only if it passes, and prints the deploy script's output.
If the app does not come up healthy, the job fails and shows the last 50 log lines; the previous containers are replaced only when the new image built successfully.

## Everyday operations

All as the deploy user in `/opt/voice-to-text`:

| Task | Command |
|---|---|
| Logs | `docker compose logs -f --tail 100` |
| Restart | `docker compose restart` |
| Deploy by hand | `./deploy/deploy.sh` |
| Change settings | `nano .env`, then `docker compose up -d` |
| Stop | `docker compose down` |
| Roll back | `git reset --hard <older-commit> && docker compose up -d --build` (the next push to `main` deploys again) |
| Enable AI correction | in `.env`: `AI_CORRECTION=true`, `COMPOSE_PROFILES=ai`, `AI_URL=http://ollama:11434`; then `./deploy/deploy.sh` and `docker compose exec ollama ollama pull gemma3:4b` |
