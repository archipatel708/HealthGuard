# Deployment Guide

## Railway

Set these variables in Railway:

```env
FLASK_ENV=production
SECRET_KEY=change-me
JWT_SECRET_KEY=change-me
MONGODB_URI=<your-mongodb-uri>
MONGODB_DB=healthguard
```

Use a start command such as:

```bash
gunicorn --bind 0.0.0.0:$PORT app:app
```

## Docker

```bash
docker compose up --build
```

This project expects MongoDB, not relational databases.
