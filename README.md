# HealthGuard

Professional-grade disease prediction platform with OTP authentication, user profiles, prediction history, and ABHA integration.

## Highlights

- End-to-end Flask API for auth, prediction, profile, and ABHA workflows
- Email OTP login with JWT access and refresh tokens
- Machine learning prediction pipeline using scikit-learn artifacts
- Persistent user data with MongoDB (PyMongo)
- Responsive single-page frontend (Vanilla JS + modern CSS)
- Docker-ready runtime and deployment documentation

## Tech Stack

- Backend: Flask, PyMongo, Flask-JWT-Extended, Flask-CORS
- ML: scikit-learn, pandas, numpy, joblib
- Auth: OTP over SMTP + JWT
- Storage: MongoDB, configurable via MONGODB_URI and MONGODB_DB
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
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=disease_prediction

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

Prediction behavior notes:

- `/api/predict` now supports `symptom_text` (free-form paragraph input)
- Profile gender (`M` or `F`) is mandatory before prediction
- Gender-incompatible symptom/disease mappings are blocked to reduce false sex-specific predictions

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

## ABHA Dummy Dataset (When API Is Inactive)

Generate synthetic ABHA-like historical data and trend summaries:

```bash
python generate_abha_dummy_data.py
```

This writes:

- `data/abha_dummy_history.csv` (visit-level historical records)
- `data/abha_disease_trends.csv` (aggregated trend/signal view)

### How to use the dummy ABHA dataset

1. Ensure your project virtual environment is active.
2. Run:

```bash
python generate_abha_dummy_data.py
```

3. Open `data/abha_dummy_history.csv` to inspect simulated longitudinal patient records:
	- Includes `symptom_text`, interpreted symptoms, vitals, and diagnosed disease.
	- Helps demonstrate how historical records accumulate over time.
4. Open `data/abha_disease_trends.csv` to inspect trend analytics:
	- `total_cases`
	- `cases_last_90_days`
	- `avg_recurrence_per_user`
	- `signal_strength`
5. Use these files for ABHA feature demos when live ABHA endpoints are unavailable.
	- You can present this as "mock ABHA history" while keeping the same downstream prediction and analysis workflow.

### In-app dummy ABHA linking (recommended demo flow)

When users click **Link ABHA Account** on the ABHA tab, the app now supports a dummy mode endpoint:

- `POST /api/abha/link-dummy`

What it does:

1. Links a synthetic ABHA ID to the logged-in user.
2. Generates random past health issues for that user (for example: diabetes history, fracture/injury, asthma, hypertension).
3. Stores them in `health_records.past_illnesses` and ABHA raw payload (`abha_data`).
4. Makes this past history available during prediction.

How prediction uses past history:

- Past illnesses are loaded as part of prediction context.
- Confidence is adjusted conservatively when symptom patterns suggest possible recurrence from prior issues (for example, old injury + current musculoskeletal pain).
- LLM review context includes past medical history so the final output can account for recurrence narratives (for example, shoulder pain after old accident).

### Notes

- The dataset is synthetic and demo-only; do not treat it as real clinical data.
- Re-run the script anytime to regenerate fresh sample history and trend summaries.

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
- Use MongoDB Atlas or a managed MongoDB deployment in production

## Troubleshooting

OTP not delivered:

- Verify MAIL_USERNAME and MAIL_PASSWORD
- Confirm Gmail app password usage (not account password)
- Check SMTP access and firewall/network policies

Dependency issues on latest Python:

- Use Python 3.10/3.11 to match pinned ML package versions

Database reset (development):

```powershell
python -c "from app import app, db; app.app_context().push(); db.database.drop_collection('users'); db.database.drop_collection('otps'); db.database.drop_collection('prediction_history'); db.database.drop_collection('health_records'); db.database.drop_collection('abha_tokens'); db.create_all(); print('Collections initialized')"
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
