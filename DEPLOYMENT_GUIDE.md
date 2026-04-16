# Deployment Guide

## Railway

This project includes a production `Dockerfile` for consistent startup on Railway.

Set these variables in Railway:

```env
FLASK_ENV=production
SECRET_KEY=change-me
JWT_SECRET_KEY=change-me
MONGODB_URI=<your-mongodb-uri>
MONGODB_DB=healthguard
```

Railway setup:

1. In your Railway service, choose Dockerfile-based deploy.
2. Keep the `PORT` variable managed by Railway (do not hardcode it).
3. Deploy; container start command is already defined in `Dockerfile`.

## Notes

- The Docker image runs `gunicorn` and binds to `0.0.0.0:$PORT`.
- `docker-compose.yml` is provided for local parity (`5000 -> 8080`).
- The app expects MongoDB, not relational databases.
