# Troubleshooting Guide

Common issues and solutions for HealthGuard disease prediction system.

---

## Installation & Setup Issues

### "ModuleNotFoundError: No module named 'flask'"

**Problem:** Flask not installed in virtual environment

**Solutions:**
```bash
# Verify virtual environment is activated
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Reinstall all dependencies
pip install -r requirements.txt --upgrade

# Or install Flask individually
pip install Flask==2.3.3
```

---

### "pip: command not found"

**Problem:** pip not in PATH or Python not properly installed

**Solutions:**
```bash
# Check Python installation
python --version
python3 --version

# Use Python module directly
python -m pip install -r requirements.txt

# Or if using just Python 3
python3 -m pip install -r requirements.txt
```

---

### "The system cannot find the path specified"

**Problem:** Path has spaces or special characters

**Solutions:**
```bash
# Navigate using quotes
cd "c:\Users\SHREE\Desktop\Disease prediction"

# Or use short paths
cd c:\Users\SHREE\Desktop\Disease prediction

# Check current directory
cd
```

---

### "venv\Scripts\activate not found"

**Problem:** Virtual environment not created

**Solutions:**
```bash
# Remove old venv if corrupted
rmdir /s venv

# Create fresh virtual environment
python -m venv venv

# Activate
venv\Scripts\activate

# Verify activation (should show (venv) in prompt)
```

---

## Database Issues

### "sqlite3.OperationalError: unable to open database file"

**Problem:** Database file location or permissions

**Solutions:**
```bash
# Ensure you're in the project directory
cd "c:\Users\SHREE\Desktop\Disease prediction"

# Recreate database
del app.db

# Initialize fresh
python -c "from app import app, db; app.app_context().push(); db.create_all()"

# Verify file created
dir app.db
```

---

### "table users does not exist"

**Problem:** Database tables not initialized

**Solutions:**
```bash
# Delete old database
del app.db

# Run Flask initialization
python -c "from app import app, db; app.app_context().push(); db.create_all(); print('Database initialized!')"

# Verify
python
>>> from app import db
>>> from models import User
>>> print("Success!")
```

---

### "Foreign key constraint failed"

**Problem:** Wrong data type or cascading delete issue

**Solutions:**
```bash
# Backup data
cp app.db app.db.backup

# Reset database
python -c "from app import app, db; app.app_context().push(); db.drop_all(); db.create_all()"

# Restore if needed from backup
```

---

## Email/OTP Issues

### "OTP not received in email"

**Problem 1: Gmail app password incorrect**
- Solution: Generate new app-specific password
  1. Go to https://myaccount.google.com/apppasswords
  2. Select "Mail" and "Windows Computer"
  3. Copy new 16-character password
  4. Update MAIL_PASSWORD in .env
  5. Restart Flask: `Ctrl+C` then `python app.py`

**Problem 2: SMTP blocked**
- Solution: Check firewall/antivirus
  ```bash
  # Test SMTP connection
  python -c "
  import smtplib
  try:
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
      server.starttls()
      print('SMTP connection successful')
  except Exception as e:
    print(f'SMTP error: {e}')
  "
  ```

**Problem 3: Wrong email in .env**
- Solution: Verify .env file
  ```bash
  # Check if .env exists
  dir .env
  
  # Verify content
  type .env  # Windows
  cat .env   # Mac/Linux
  ```

---

### "SMTPAuthenticationError: Invalid username or password"

**Problem:** Wrong Gmail credentials

**Solutions:**
1. Verify you're using app-specific password (not regular Gmail password)
2. Generate new app-specific password:
   - Enable 2FA in Google Account
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Windows Computer"
   - Use the 16-digit code (remove spaces)
3. Update .env file:
   ```env
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=xxxx-xxxx-xxxx-xxxx
   ```

---

### "SMTP connection timeout"

**Problem:** Firewall or ISP blocking port 587

**Solutions:**
```bash
# Try different port
MAIL_PORT=465  # Use SSL instead of TLS

# Or use different email provider
# Outlook: smtp-mail.outlook.com:587
# Yahoo: smtp.mail.yahoo.com:587

# Test with telnet
telnet smtp.gmail.com 587
```

---

## Login & Authentication Issues

### "Invalid or expired OTP"

**Problem 1: OTP expired before entrance**
- Solution: OTP valid for 5 minutes by default
- Request new OTP: Click "Request OTP" again

**Problem 2: OTP code entered incorrectly**
- Solution: 
  - Check email for exact 6-digit code
  - No spaces or hyphens
  - Case sensitive (if applicable)

**Problem 3: Too many failed attempts**
- Solution: Wait 10 minutes and request new OTP

---

### "401 Unauthorized" when making predictions

**Problem 1: Token expired**
- Solution: Log out and log in again
  1. Click logout
  2. Re-enter email and OTP
  3. Try prediction again

**Problem 2: Invalid token in localStorage**
- Solution: Clear browser storage
  1. Press F12 (Developer Tools)
  2. Application tab → Local Storage
  3. Delete all entries
  4. Refresh page and login again

**Problem 3: Network issue during login**
- Solution: Check console for errors
  1. F12 → Console tab
  2. Look for red error messages
  3. Check network tab for failed requests

---

### "CORS error when accessing API"

**Problem:** Frontend trying to access backend from different origin

**Solutions:**
```bash
# Verify CORS is enabled in .env
CORS_ORIGINS=*

# For production, specify allowed domains
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Check Flask logs for CORS details
# In browser F12 Console, look for "Access-Control-Allow-Origin" errors
```

---

## Application Runtime Issues

### "Address already in use" on port 5000

**Problem:** Another application using port 5000

**Solutions:**
```bash
# Find process using port 5000
netstat -ano | findstr :5000  # Windows
lsof -i :5000               # Mac/Linux

# Kill the process (Windows)
taskkill /PID <PID> /F

# Or use different port
python -c "from app import app; app.run(port=5001)"
```

---

### "RuntimeError: Working outside of application context"

**Problem:** Trying to access database outside Flask app context

**Solutions:**
```bash
# Use app context
python -c "
from app import app, db
from models import User
with app.app_context():
    users = User.query.all()
    print(f'Total users: {len(users)}')
"
```

---

### "TypeError: Object of type function is not JSON serializable"

**Problem:** Trying to return non-serializable object from API

**Solution:** Check that all API endpoints return JSON-compatible data
```python
# ❌ Wrong
return {'func': some_function}

# ✅ Correct
return {'result': some_function()}
```

---

## Frontend Issues

### "Blank page after login"

**Problem 1: JavaScript error**
- Solution:
  1. Open F12 Developer Tools
  2. Check Console tab for red errors
  3. Look for specific error messages

**Problem 2: Token not saving to localStorage**
- Solution:
  1. F12 → Application → Local Storage
  2. Check if `accessToken` exists
  3. Clear localStorage and login again

**Problem 3: API endpoint URL wrong**
- Solution: Verify in app.js
  ```javascript
  const API_BASE = 'http://localhost:5000';
  // Ensure this matches your Flask app URL
  ```

---

### "Symptoms not loading in dropdown"

**Problem:** API call to /api/symptoms failing

**Solutions:**
```bash
# Test endpoint manually
curl http://localhost:5000/api/symptoms

# Or in browser console
fetch('http://localhost:5000/api/symptoms')
  .then(r => r.json())
  .then(d => console.log(d))

# Check if Flask is running
python app.py
```

---

### "Prediction results not displaying"

**Problem 1: API returned error**
- Solution:
  1. Check F12 Console for error messages
  2. Check Network tab for failed request
  3. View response details

**Problem 2: Symptoms not selected**
- Solution: Select at least 1 symptom before predicting

**Problem 3: Missing required fields**
- Solution: Ensure symptoms array is not empty
  ```javascript
  // In browser console
  console.log(selectedSymptoms);  // Should have items
  ```

---

### CSS not loading (page looks unstyled)

**Problem:** Static CSS file not found

**Solutions:**
```bash
# Verify file exists
dir static\style.css

# Check Flask static configuration
# In Flask: app.static_url_path = '/static'

# Clear browser cache
# Ctrl+Shift+Delete in Chrome/Firefox
# Then reload page
```

---

## Performance Issues

### "Site loading very slowly"

**Problem 1: Large database queries**
- Solution: Add query indexing
  ```python
  # In models.py
  user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
  ```

**Problem 2: Too many symptoms in dropdown**
- Solution: Implement search/filtering (already done)

**Problem 3: Database file too large**
- Solution: Backup and rebuild
  ```bash
  cp app.db app.db.old
  python -c "from app import app, db; app.app_context().push(); db.drop_all(); db.create_all()"
  ```

---

### "API response taking >5 seconds"

**Problem 1: ML model inference slow**
- Solution: Prediction model is fast; check database queries
  
**Problem 2: Database connection pool exhausted**
- Solution: Increase connection pool
  ```python
  # In config.py
  SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 3600,
  }
  ```

---

## ABHA Integration Issues

### "ABHA authorization URL not generating"

**Problem:** ABHA credentials not configured

**Solutions:**
1. Verify .env has ABHA credentials
   ```bash
   # Check .env
   echo %ABHA_CLIENT_ID%
   ```

2. Register with NDHM:
   - Development: https://healthiddev.ndhm.gov.in
   - Production: https://healthid.ndhm.gov.in

3. Update .env:
   ```env
   ABHA_CLIENT_ID=your-client-id
   ABHA_CLIENT_SECRET=your-client-secret
   ABHA_REDIRECT_URI=http://localhost:5000/api/abha/callback
   ```

---

### "ABHA callback failing"

**Problem 1: Invalid redirect URI**
- Solution: Ensure redirect URI matches exactly in NDHM and .env

**Problem 2: Authorization code expired**
- Solution: Code valid for 5 minutes; quickly complete flow

**Problem 3: OAuth token exchange failing**
- Solution: Check ABHA API status
  ```bash
  # Test ABHA API connectivity
  curl https://healthiddev.ndhm.gov.in/api/v1/status
  ```

---

## Deployment Issues

### Docker build failing

**Problem 1: Python version not found**
- Solution: Update Dockerfile
  ```dockerfile
  FROM python:3.10-slim  # or 3.11, 3.12
  ```

**Problem 2: pip install hanging**
- Solution: Add timeout and retry
  ```dockerfile
  RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
  ```

---

### Docker container exits immediately

**Problem:** Application crashing on startup

**Solutions:**
```bash
# Check logs
docker logs container-name

# Run interactively to see errors
docker run -it healthguard bash

# Inside container, test individually
python -c "import flask; print('Flask OK')"
python -c "from app import app; app.run()"
```

---

### Port 5000 already in use in Docker

**Solutions:**
```bash
# Use different port
docker run -p 5001:5000 healthguard

# Or stop previous container
docker stop container-name
docker rm container-name
```

---

## Debugging Tips

### Enable verbose logging

**In Flask:**
```python
# Add to app.py
app.logger.setLevel(logging.DEBUG)
```

**In .env:**
```env
LOG_LEVEL=DEBUG
```

---

### Check all logs

```bash
# Application logs
type flask_out.txt

# Browser console (F12)
# Network tab for API calls
# Application tab for localStorage

# Server logs
tail -f app.log  # Modern terminal
```

---

### Test individual components

```python
# Test database
python -c "from app import db; print(db.engine.url)"

# Test email
from auth import AuthService
auth = AuthService()
auth.send_otp_email('test@example.com')

# Test model
python -c "
from app import app
from models import User
with app.app_context():
    count = User.query.count()
    print(f'Users in DB: {count}')
"
```

---

## Getting Help

1. **Check Documentation:**
   - README.md - Overview
   - QUICKSTART.md - Setup guide
   - API_DOCUMENTATION.md - API details

2. **Review Error Messages:**
   - Browser Console (F12)
   - Flask Terminal Output
   - flask_out.txt log file

3. **Search for solutions:**
   - Flask documentation: flask.palletsprojects.com
   - SQLAlchemy docs: sqlalchemy.org
   - Stack Overflow: search the error message

4. **Still stuck?**
   - Review this troubleshooting guide again
   - Check similar issues in documentation
   - Restart from QUICKSTART.md

---

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError` | Package not installed | `pip install -r requirements.txt` |
| `Address already in use` | Port 5000 occupied | `python -c "from app import app; app.run(port=5001)"` |
| `No module named 'app'` | Not in right directory | `cd "Disease prediction"` |
| `database is locked` | Multiple Flask instances | Stop all Flask processes, restart |
| `SMTP error` | Email settings wrong | Update .env with correct Gmail credentials |
| `401 Unauthorized` | Token expired | Logout and login again |
| `CORS error` | Cross-origin issue | Check CORS_ORIGINS in .env |
| `500 Internal Server Error` | Backend bug | Check Flask console output |

---

**Last Updated:** January 2024  
**If problem persists:** Review README.md section on "Getting Help" or check Flask/SQLAlchemy official documentation.
