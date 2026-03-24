# Deployment Guide

Guide for deploying HealthGuard to various platforms.

## Local Development

### Quick Start
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

pip install -r requirements.txt
python -c "from app import app, db; app.app_context().push(); db.create_all()"
python app.py
```

Visit: http://localhost:5000

---

## Docker & Docker Compose

### Option 1: Docker

**Build Image:**
```bash
docker build -t healthguard:1.0 .
```

**Run Container:**
```bash
docker run -d \
  --name healthguard \
  -p 5000:5000 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  healthguard:1.0
```

**View Logs:**
```bash
docker logs -f healthguard
```

### Option 2: Docker Compose (Recommended)

**Setup:**
```bash
# Ensure .env is configured
docker-compose up -d
```

**Stop:**
```bash
docker-compose down
```

**View Logs:**
```bash
docker-compose logs -f web
```

**Database Access:**
```bash
# PostgreSQL shell
docker-compose exec db psql -U postgres -d disease_predictor
```

---

## Platform-Specific Deployments

### Heroku

**Prerequisites:**
- Heroku CLI installed
- Heroku account with app created

**Steps:**

1. **Create `Procfile`:**
```
web: gunicorn -w 4 -b 0.0.0.0:$PORT app:app
```

2. **Create `runtime.txt`:**
```
python-3.10.13
```

3. **Deploy:**
```bash
heroku login
git push heroku main
```

4. **Configure Environment:**
```bash
heroku config:set FLASK_ENV=production
heroku config:set SECRET_KEY=your-random-secret
heroku config:set JWT_SECRET_KEY=your-random-jwt-secret
heroku config:set MAIL_USERNAME=your-email@gmail.com
heroku config:set MAIL_PASSWORD=your-app-password
```

5. **Add PostgreSQL:**
```bash
heroku addons:create heroku-postgresql:hobby-dev
```

6. **Initialize Database:**
```bash
heroku run python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

**Monitor:**
```bash
heroku logs --tail
heroku open
```

---

### AWS (EC2)

**Prerequisites:**
- AWS Account
- EC2 instance (Ubuntu 20.04)
- Security group with ports 80, 443, 5000 open

**Setup:**

1. **SSH into instance:**
```bash
ssh -i your-key.pem ubuntu@your-instance-ip
```

2. **Install dependencies:**
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv postgresql postgresql-contrib nginx git

# Clone repository
git clone <your-repo-url>
cd "Disease prediction"
```

3. **Setup virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

4. **Configure PostgreSQL:**
```bash
sudo -u postgres psql <<EOF
CREATE DATABASE disease_predictor;
CREATE USER healthguard WITH PASSWORD 'strong-password';
ALTER ROLE healthguard SET client_encoding TO 'utf8';
ALTER ROLE healthguard SET default_transaction_isolation TO 'read committed';
ALTER ROLE healthguard SET default_transaction_deferrable TO on;
ALTER ROLE healthguard SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE disease_predictor TO healthguard;
\q
EOF
```

5. **Setup .env:**
```bash
cp .env.example .env
# Edit .env with production settings
DATABASE_URL=postgresql://healthguard:strong-password@localhost:5432/disease_predictor
```

6. **Create systemd service:**
```bash
sudo tee /etc/systemd/system/healthguard.service > /dev/null <<EOF
[Unit]
Description=HealthGuard Flask Application
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/Disease\ prediction
Environment="PATH=/home/ubuntu/Disease\ prediction/venv/bin"
ExecStart=/home/ubuntu/Disease\ prediction/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

7. **Enable service:**
```bash
sudo systemctl daemon-reload
sudo systemctl start healthguard
sudo systemctl enable healthguard
```

8. **Configure Nginx:**
```bash
sudo tee /etc/nginx/sites-available/healthguard > /dev/null <<EOF
upstream healthguard {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://healthguard;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF
```

9. **Enable Nginx:**
```bash
sudo ln -s /etc/nginx/sites-available/healthguard /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

10. **Setup SSL (Let's Encrypt):**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

### Google Cloud Run

**Prerequisites:**
- Google Cloud account
- Cloud Run API enabled
- Docker installed

**Deployment:**

```bash
# Configure gcloud
gcloud config set project YOUR_PROJECT_ID

# Build and push image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/healthguard

# Deploy to Cloud Run
gcloud run deploy healthguard \
  --image gcr.io/YOUR_PROJECT_ID/healthguard \
  --platform managed \
  --region us-central1 \
  --memory 512Mi \
  --cpu 1 \
  --set-env-vars FLASK_ENV=production,SET_CLOUDSQL_INSTANCES=YOUR_CLOUDSQL_INSTANCE \
  --allow-unauthenticated
```

---

### Azure App Service

**Prerequisites:**
- Azure account
- Azure CLI installed

**Deployment:**

1. **Create App Service:**
```bash
az group create --name healthguard-rg --location eastus

az appservice plan create \
  --name healthguard-plan \
  --resource-group healthguard-rg \
  --sku B1 --is-linux

az webapp create \
  --resource-group healthguard-rg \
  --plan healthguard-plan \
  --name healthguard-app \
  --runtime "PYTHON|3.10"
```

2. **Configure deployment:**
```bash
az webapp up \
  --resource-group healthguard-rg \
  --name healthguard-app \
  --runtime python:3.10
```

3. **Set environment variables:**
```bash
az webapp config appsettings set \
  --resource-group healthguard-rg \
  --name healthguard-app \
  --settings \
  FLASK_ENV=production \
  SECRET_KEY=your-secret \
  MAIL_USERNAME=your-email \
  MAIL_PASSWORD=your-password
```

---

### PythonAnywhere

**Steps:**

1. Sign up at pythonanywhere.com

2. Upload files:
   - Go to "Files" tab
   - Upload project files

3. Create virtual environment:
   - Bash console: `python3 -m venv venv`
   - Activate: `source venv/bin/activate`
   - Install: `pip install -r requirements.txt`

4. Configure web app:
   - Add new web app
   - Select Python 3.10
   - Choose Flask
   - Point to `app.py`

5. Edit WSGI file:
```python
import sys
path = '/home/username/myapp'
if path not in sys.path:
    sys.path.append(path)

from app import app as application
```

6. Set environment variables in Web tab

---

## Production Ready Checklist

- [ ] Use production database (PostgreSQL/MySQL)
- [ ] Change SECRET_KEY to random 32+ character string
- [ ] Change JWT_SECRET_KEY to random 32+ character string
- [ ] Set FLASK_ENV=production
- [ ] Enable HTTPS/SSL certificates
- [ ] Configure CORS with specific domain
- [ ] Setup error logging (Sentry/LogRocket)
- [ ] Enable monitoring (Datadog/New Relic)
- [ ] Setup CI/CD pipeline (GitHub Actions/GitLab CI)
- [ ] Configure backup strategy for database
- [ ] Setup email service (SendGrid/Mailgun) for reliability
- [ ] Enable rate limiting
- [ ] Configure DDoS protection (CloudFlare)
- [ ] Setup health monitoring alerts
- [ ] Regular security audits
- [ ] Document deployment process

---

## Scaling

### For High Traffic

1. **Database:**
   - Use managed PostgreSQL (AWS RDS, Azure DB)
   - Enable read replicas
   - Setup read caching (Redis)

2. **Application:**
   - Use Kubernetes cluster
   - Setup auto-scaling based on CPU/memory
   - Use load balancer (nginx/HAProxy)

3. **Services:**
   - Use CDN for static assets (CloudFlare)
   - Separate email queue (Celery+Redis)
   - Cache API responses (Redis)

Example Docker Swarm setup:
```bash
docker swarm init
docker service create \
  --name healthguard \
  --replicas 3 \
  -p 5000:5000 \
  --env-file .env \
  healthguard:1.0
```

---

## Monitoring & Maintenance

### Health Checks
```bash
# Check API availability
curl http://your-domain/api/health

# Check database connection
flask shell
>>> from app import db
>>> db.engine.execute("SELECT 1")
```

### Logs
```bash
# View application logs
tail -f app.log

# View error logs
tail -f error.log

# Search for specific errors
grep "ERROR" app.log
```

### Database Maintenance
```bash
# Backup
pg_dump disease_predictor > backup.sql

# Restore
psql disease_predictor < backup.sql

# Optimize
VACUUM ANALYZE;
REINDEX;
```

---

## Troubleshooting

### 502 Bad Gateway
- Check if gunicorn is running
- Check port conflicts
- Review application logs
- Increase worker processes

### Database Connection Errors
- Verify DATABASE_URL
- Check database credentials
- Test connectivity: `psql -U user -d database`

### Email Not Working
- Verify MAIL credentials
- Check firewall SMTP settings (usually 587)
- Test with: `python -c "from auth import send_test_email; send_test_email()"`

### Memory Issues
- Reduce worker count: `gunicorn -w 2`
- Enable memory caching (Redis)
- Optimize database queries

---

For platform-specific issues, refer to official documentation:
- Heroku: heroku.com/docs
- AWS: docs.aws.amazon.com
- Azure: docs.microsoft.com/azure
- Google Cloud: cloud.google.com/docs
