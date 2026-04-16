# Troubleshooting

## App cannot connect to the database

Check:

- `MONGODB_URI` is set correctly
- `MONGODB_DB` matches the intended database name
- your MongoDB instance is reachable from the app environment

## Prediction model fails to load

The app will attempt to retrain the model from the CSV files automatically. If needed, run:

```bash
python train.py
```

## Authentication fails

Check:

- the user exists in the `users` collection
- the password is correct
- `JWT_SECRET_KEY` is configured consistently across restarts
