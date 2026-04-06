# Quick Start Guide

Get HealthGuard running in 5 minutes!

## TL;DR

```bash
# 1. Activate virtual environment
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure email (.env file)
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# 4. Initialize database
python -c "from app import app, db; app.app_context().push(); db.create_all()"

# 5. Run
python app.py

# 6. Open http://localhost:5000
```

## Step-by-Step

### 1️⃣ Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 2️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```

### 3️⃣ Setup Email (CRITICAL)
Without this, OTP emails won't work!

**Option A: Gmail**
1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and "Windows Computer"
3. Copy the 16-character password
4. Create `.env` file:
```env
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

**Option B: Other Email Providers**
```env
MAIL_SERVER=your-smtp-server
MAIL_PORT=587
MAIL_USERNAME=your-email
MAIL_PASSWORD=your-password
```

### 4️⃣ Initialize Database
```bash
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

Verify: Check for `app.db` file in the project directory.

### 5️⃣ Run the Server
```bash
python app.py
```

Output should show:
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

### 6️⃣ Open in Browser
Visit: **http://localhost:5000**

## First Test

1. Enter any email address
2. Click "Request OTP"
3. Check your email inbox (may take 10-30 seconds)
4. Enter the 6-digit code
5. Click "Verify"
6. Select symptoms and make a prediction!

## Features Overview

| Tab | What It Does |
|-----|--------------|
| **Prediction** | Select symptoms → Get disease prediction with precautions |
| **History** | View all past predictions with confidence scores |
| **Profile** | Update personal info + manage health records |
| **ABHA** | Link to government health account (optional) |

## Common Issues

### "Email not received after 5 minutes"
- Check spam/junk folder
- Verify `MAIL_USERNAME` and `MAIL_PASSWORD` in `.env`
- Gmail: Use app-specific password, not regular password
- Disable antivirus/firewall blocking SMTP

### "Port 5000 already in use"
```bash
# Use different port
python -c "from app import app; app.run(port=5001)"
```

### "Database error"
```bash
# Reset database
del app.db
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

### "401 Unauthorized" on prediction
- Logout and login again
- Refresh browser
- Check localStorage (F12 → Application → Local Storage)

## Environment File Template

Copy this to `.env`:

```env
# Flask
FLASK_ENV=development
SECRET_KEY=change-me-to-random-string
JWT_SECRET_KEY=change-me-to-another-random-string

# Email (Gmail)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# ABHA (Optional - for government health account linking)
ABHA_CLIENT_ID=
ABHA_CLIENT_SECRET=
ABHA_REDIRECT_URI=http://localhost:5000/api/abha/callback

# OTP Settings
OTP_VALIDITY_MINUTES=5
OTP_MAX_ATTEMPTS=3
```

## Next Steps

- ✅ Run the app
- 📧 Test OTP email delivery
- 🔮 Try disease predictions
- 📊 Upload health records
- 🔗 (Optional) Link ABHA account

## Need Help?

1. Check `flask_out.txt` for error logs
2. Open browser F12 → Console for JavaScript errors
3. Check `.env` file has correct email credentials
4. Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`

## Development Commands

```bash
# Run in debug mode (auto-reload)
python app.py

# Run tests (if available)
pytest

# Train new model
python train.py

# Access Flask shell
flask shell

# View database
# Connect to MongoDB and inspect collections
# mongosh mongodb://localhost:27017/disease_prediction
```

## Production Checklist

Before deploying:

- [ ] Change SECRET_KEY to random string
- [ ] Change JWT_SECRET_KEY to random string
- [ ] Set FLASK_ENV=production
- [ ] Set MONGODB_URI and MONGODB_DB for production MongoDB
- [ ] Setup HTTPS/SSL
- [ ] Configure CORS properly
- [ ] Use Gunicorn/Waitress instead of Flask dev server
- [ ] Setup rate limiting
- [ ] Enable logging to file

Run with Gunicorn:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

---

**Time to setup**: 5-10 minutes  
**Time to first prediction**: <1 minute  
**Questions?** Check README.md for detailed documentation
