# HealthGuard

Disease prediction platform with password-based authentication, MongoDB persistence, prediction history, health records, and ABHA integration.

## Stack

- Flask
- MongoDB with PyMongo
- Flask-JWT-Extended
- scikit-learn, pandas, numpy, joblib
- Vanilla HTML, CSS, JavaScript

## Required Environment Variables

```env
FLASK_ENV=development
SECRET_KEY=change-me
JWT_SECRET_KEY=change-me

MONGODB_URI=mongodb://localhost:27017/healthguard
MONGODB_DB=healthguard

ABHA_API_URL=https://healthiddev.ndhm.gov.in
ABHA_CLIENT_ID=
ABHA_CLIENT_SECRET=
ABHA_CM_ID=
ABHA_REDIRECT_URI=http://localhost:5000/api/abha/callback

CORS_ORIGINS=*
```

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

## Auth Endpoints

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`

## MongoDB Collections

- `users`
- `prediction_history`
- `health_records`
- `abha_tokens`

Indexes are initialized automatically on startup.
