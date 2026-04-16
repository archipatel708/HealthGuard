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
gunicorn --workers 1 --bind 0.0.0.0:$PORT app:app
```

## Notes

- Railway can run this project directly from source using the included `Procfile`.
- No Docker step is required.
- The app expects MongoDB, not relational databases.
