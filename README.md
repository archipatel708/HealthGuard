# HealthGuard

Professional-grade disease prediction platform with OTP authentication, user profiles, prediction history, and ABHA integration.

## Highlights

- End-to-end Flask API for auth, prediction, profile, and ABHA workflows
- Email OTP login with JWT access and refresh tokens
- Machine learning prediction pipeline using scikit-learn artifacts
- Persistent user data with SQLAlchemy (SQLite by default)
- Responsive single-page frontend (Vanilla JS + modern CSS)
- Docker-ready runtime and deployment documentation

## Tech Stack

- Backend: Flask, Flask-SQLAlchemy, Flask-JWT-Extended, Flask-CORS
- ML: scikit-learn, pandas, numpy, joblib
- Auth: OTP over SMTP + JWT
- Storage: SQLite (default), configurable via DATABASE_URL
- Frontend: HTML, CSS, JavaScript

## Python Compatibility

This repository pins:

- scikit-learn 1.3.1
- numpy 1.24.3
- pandas 2.0.3

Recommended runtime is Python 3.10 or 3.11 for reliable installs and execution.

## Project Structure

```text
.
|-- app.py
|-- auth.py
|-- abha.py
|-- config.py
|-- models.py
|-- train.py
|-- requirements.txt
|-- .env.example
|-- templates/
|   `-- index.html
|-- static/
|   |-- app.js
|   `-- style.css
|-- model/
|   |-- model.pkl
|   |-- symptom_list.pkl
|   `-- severity_map.pkl
`-- docs and guides
```

## Quick Start

### 1) Create and activate a virtual environment

Windows (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python -m venv venv
source venv/bin/activate
```

### 2) Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3) Configure environment

Create .env from .env.example and set required values:

```env
FLASK_ENV=development
SECRET_KEY=replace-with-strong-secret
JWT_SECRET_KEY=replace-with-strong-secret

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@healthguard.com

# Optional ABHA settings
ABHA_CLIENT_ID=
ABHA_CLIENT_SECRET=
ABHA_REDIRECT_URI=http://localhost:5000/api/abha/callback
```

### 4) Start the application

```bash
python app.py
```

Open: http://localhost:5000

## API Overview

Authentication:

- POST /api/auth/request-otp
- POST /api/auth/verify-otp
- POST /api/auth/refresh

Predictions:

- GET /api/symptoms
- POST /api/predict
- GET /api/predictions/history
- GET /api/predictions/<id>

User and health records:

- GET /api/user/profile
- PUT /api/user/profile
- GET /api/user/health-records
- POST /api/user/health-records

ABHA:

- GET /api/abha/authorization-url
- POST /api/abha/callback
- GET /api/abha/health-data
- POST /api/abha/unlink

Detailed endpoint contracts are available in API_DOCUMENTATION.md.

## Model Lifecycle

Retrain model artifacts with:

```bash
python train.py
```

The script regenerates model/model.pkl, model/symptom_list.pkl, and model/severity_map.pkl.

## Deployment

### Docker

```bash
docker build -t healthguard .
docker run -p 5000:5000 --env-file .env healthguard
```

### Production WSGI

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Security Checklist

- Use strong random values for SECRET_KEY and JWT_SECRET_KEY
- Keep .env out of version control
- Use app passwords for SMTP credentials
- Restrict CORS_ORIGINS in production
- Add OTP rate limiting before public internet exposure
- Prefer PostgreSQL for production workloads

## Troubleshooting

OTP not delivered:

- Verify MAIL_USERNAME and MAIL_PASSWORD
- Confirm Gmail app password usage (not account password)
- Check SMTP access and firewall/network policies

Dependency issues on latest Python:

- Use Python 3.10/3.11 to match pinned ML package versions

Database reset (development):

```powershell
Remove-Item .\app.db -ErrorAction Ignore
python -c "from app import app, db; app.app_context().push(); db.create_all(); print('Database initialized')"
```

## Contributing

1. Create a feature branch from main.
2. Keep commits focused and atomic.
3. Validate startup and core API flows locally.
4. Open a pull request with a clear change summary.

## License

MIT

## Maintainer Notes

- Version: 1.0.0
- Last updated: March 2026
