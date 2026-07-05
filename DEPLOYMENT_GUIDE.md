# Deployment Guide — GitHub + Free AWS Hosting

## Part 1 — Push the project to GitHub

1. Create a new empty repository on GitHub (no README/license, since you already have files) —
   call it e.g. `neurodoc-ai`.
2. On your machine, open a terminal in the project's root folder (the one containing `backend/`,
   `frontend/`, `README.md`) and run:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: NeuroDoc AI multi-agent RAG assistant"
   git branch -M main
   git remote add origin https://github.com/<your-username>/neurodoc-ai.git
   git push -u origin main
   ```
3. Confirm on GitHub.com that all files uploaded — `backend/`, `frontend/`, `README.md`,
   `.gitignore`, `DEPLOYMENT_GUIDE.md`. Your `.env` file will **not** upload (that's intentional —
   it's in `.gitignore` so your API key stays private).

## Part 2 — Deploy free on AWS (EC2 Free Tier)

AWS gives new accounts a **t2.micro / t3.micro instance free for 12 months** (750 hours/month —
enough to run this 24/7). Total cost: $0 if you stay within free-tier limits.

### Step 1: Launch the instance
1. Log into the [AWS Console](https://console.aws.amazon.com) → search **EC2** → **Launch instance**.
2. Name: `neurodoc-ai-server`.
3. AMI: **Ubuntu Server 22.04 LTS** (Free tier eligible).
4. Instance type: **t2.micro** (Free tier eligible).
5. Key pair: create a new one, download the `.pem` file, and keep it safe — you need it to SSH in.
6. Network settings → Edit → allow:
   - SSH (port 22) from "My IP"
   - HTTP (port 80) from Anywhere
   - Custom TCP (port 8000) from Anywhere — for testing before you put Nginx in front
7. Storage: default 8GB is fine.
8. Click **Launch instance**.

### Step 2: Connect to the instance
```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@<your-instance-public-ip>
```
(Find the public IP on the EC2 dashboard under your instance's details.)

### Step 3: Install dependencies on the server
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git nginx
```

### Step 4: Clone your repo and set up the app
```bash
git clone https://github.com/<your-username>/neurodoc-ai.git
cd neurodoc-ai/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env    # paste your free Groq API key, then Ctrl+O, Enter, Ctrl+X to save
```

### Step 5: Test it directly
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```
Visit `http://<your-instance-public-ip>:8000` in a browser. If the chat UI loads, it's working.
Press `Ctrl+C` to stop this test run.

### Step 6: Keep it running permanently with systemd
```bash
sudo nano /etc/systemd/system/neurodoc.service
```
Paste in:
```ini
[Unit]
Description=NeuroDoc AI FastAPI app
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/neurodoc-ai/backend
Environment="PATH=/home/ubuntu/neurodoc-ai/backend/.venv/bin"
ExecStart=/home/ubuntu/neurodoc-ai/backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```
Save, then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable neurodoc
sudo systemctl start neurodoc
sudo systemctl status neurodoc   # should show "active (running)"
```

### Step 7: Put Nginx in front (so it's reachable on port 80, no `:8000` needed)
```bash
sudo nano /etc/nginx/sites-available/neurodoc
```
Paste in:
```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;              # required so streamed tokens aren't buffered
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```
Then:
```bash
sudo ln -s /etc/nginx/sites-available/neurodoc /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

Now visit `http://<your-instance-public-ip>` — no port number needed.

### Step 8 (optional): Free HTTPS with a domain name
If you point a domain you own at the instance's IP (an A record), you can get a free SSL
certificate:
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### Updating the app later
```bash
cd ~/neurodoc-ai
git pull
sudo systemctl restart neurodoc
```

## Cost checklist to stay at $0
- Use `t2.micro`/`t3.micro` only.
- Don't attach Elastic IPs you're not using (unattached Elastic IPs are billed).
- Stay under 750 instance-hours/month (one instance running 24/7 = ~730 hours, fine).
- Delete the instance if you exceed your free-tier 12-month window and don't want to pay.
