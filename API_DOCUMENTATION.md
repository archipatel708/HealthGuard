# API Documentation

Complete API reference for HealthGuard disease prediction system.

## Base URL
```
http://localhost:5000
```

## Authentication

All protected endpoints require a JWT token in the Authorization header:

```bash
Authorization: Bearer {access_token}
```

## Response Format

All responses are in JSON format:

### Success Response
```json
{
  "status": "success",
  "data": { ... },
  "message": "Operation completed successfully"
}
```

### Error Response
```json
{
  "status": "error",
  "error": "Error code",
  "message": "Detailed error message"
}
```

---

## Public Endpoints

### Health Check
```
GET /api/health
```

Returns server status.

**Response:**
```json
{
  "status": "success",
  "message": "Server is running",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Get All Symptoms
```
GET /api/symptoms
```

Returns list of all available symptoms for prediction.

**Response:**
```json
{
  "status": "success",
  "data": {
    "symptoms": [
      "itching",
      "skin_rash",
      "nodal_skin_eruptions",
      ...
    ],
    "count": 132
  }
}
```

---

## Authentication Endpoints

### Request OTP
```
POST /api/auth/request-otp
Content-Type: application/json
```

Request a one-time password for email-based login.

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "email": "user@example.com",
    "validity_minutes": 5,
    "user_id": 1
  },
  "message": "OTP sent successfully to user@example.com"
}
```

**Response (Error):**
```json
{
  "status": "error",
  "error": "INVALID_EMAIL",
  "message": "Invalid email format"
}
```

**Status Codes:**
- `200` - OTP sent successfully
- `400` - Invalid email format
- `429` - Too many requests (rate limited)

---

### Verify OTP
```
POST /api/auth/verify-otp
Content-Type: application/json
```

Verify OTP and receive JWT tokens.

**Request Body:**
```json
{
  "email": "user@example.com",
  "otp_code": "123456"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "user_id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 2592000
  },
  "message": "Login successful"
}
```

**Status Codes:**
- `200` - Login successful
- `400` - Invalid OTP or expired
- `404` - User not found

---

### Refresh Access Token
```
POST /api/auth/refresh
Authorization: Bearer {refresh_token}
```

Get a new access token using refresh token.

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 2592000
  },
  "message": "Token refreshed successfully"
}
```

**Status Codes:**
- `200` - Token refreshed
- `401` - Invalid or expired refresh token

---

## Protected Endpoints (Require Authentication)

### Make Prediction
```
POST /api/predict
Authorization: Bearer {access_token}
Content-Type: application/json
```

Predict disease based on symptoms and optional health vitals.

**Request Body:**
```json
{
  "symptoms": [
    "cough",
    "fever",
    "sore_throat"
  ],
  "health_vitals": {
    "blood_pressure": "120/80",
    "heart_rate": 78,
    "temperature": 98.6,
    "oxygen_saturation": 98,
    "blood_sugar": 110
  },
  "notes": "Patient reports symptoms started 3 days ago"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "prediction_id": 42,
    "disease": "Common Cold",
    "confidence_score": 87.5,
    "description": "Viral infection affecting the upper respiratory tract...",
    "precautions": [
      "Get plenty of rest",
      "Stay hydrated",
      "Use throat lozenges for throat pain",
      "Gargle with salt water"
    ],
    "top3_predictions": [
      {
        "disease": "Common Cold",
        "confidence": 87.5,
        "severity": "mild"
      },
      {
        "disease": "Pharyngitis",
        "confidence": 78.2,
        "severity": "mild"
      },
      {
        "disease": "Viral Fever",
        "confidence": 71.3,
        "severity": "mild"
      }
    ],
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

**Status Codes:**
- `200` - Prediction successful
- `400` - Invalid symptoms
- `401` - Unauthorized

---

### Get Prediction History
```
GET /api/predictions/history?page=1&per_page=10
Authorization: Bearer {access_token}
```

Retrieve all past predictions for the user.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number for pagination |
| `per_page` | int | 10 | Items per page |

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "predictions": [
      {
        "id": 42,
        "disease": "Common Cold",
        "confidence_score": 87.5,
        "symptoms": ["cough", "fever"],
        "created_at": "2024-01-15T10:30:00Z"
      },
      {
        "id": 41,
        "disease": "Headache",
        "confidence_score": 92.1,
        "symptoms": ["headache", "migraine"],
        "created_at": "2024-01-14T14:20:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 10,
      "total": 2,
      "pages": 1
    }
  }
}
```

---

### Get Prediction Detail
```
GET /api/predictions/{id}
Authorization: Bearer {access_token}
```

Get detailed information about a specific prediction.

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "id": 42,
    "disease": "Common Cold",
    "confidence_score": 87.5,
    "description": "Viral infection affecting...",
    "symptoms": ["cough", "fever", "sore_throat"],
    "health_vitals": {
      "blood_pressure": "120/80",
      "temperature": 98.6
    },
    "precautions": [...],
    "top3_predictions": [...],
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

---

## User Profile Endpoints

### Get User Profile
```
GET /api/user/profile
Authorization: Bearer {access_token}
```

Retrieve user profile information.

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "age": 30,
    "gender": "M",
    "phone": "+91-9876543210",
    "abha_id": null,
    "abha_linked_at": null,
    "is_verified": true,
    "created_at": "2024-01-10T08:00:00Z",
    "updated_at": "2024-01-15T10:00:00Z"
  }
}
```

---

### Update User Profile
```
PUT /api/user/profile
Authorization: Bearer {access_token}
Content-Type: application/json
```

Update user profile information.

**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "age": 31,
  "gender": "M",
  "phone": "+91-9876543210"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "age": 31,
    "phone": "+91-9876543210",
    "updated_at": "2024-01-15T10:35:00Z"
  },
  "message": "Profile updated successfully"
}
```

---

## Health Records Endpoints

### Get Health Records
```
GET /api/user/health-records
Authorization: Bearer {access_token}
```

Retrieve user's health records.

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "records": [
      {
        "id": 1,
        "blood_pressure": "120/80",
        "heart_rate": 78,
        "temperature": 98.6,
        "oxygen_saturation": 98,
        "blood_sugar": 110,
        "allergies": ["Penicillin"],
        "medications": ["Aspirin"],
        "created_at": "2024-01-15T10:00:00Z"
      }
    ],
    "count": 1
  }
}
```

---

### Add Health Record
```
POST /api/user/health-records
Authorization: Bearer {access_token}
Content-Type: application/json
```

Add a new health record.

**Request Body:**
```json
{
  "blood_pressure": "120/80",
  "heart_rate": 78,
  "temperature": 98.6,
  "oxygen_saturation": 98,
  "blood_sugar": 110,
  "allergies": ["Penicillin"],
  "medications": ["Aspirin"]
}
```

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "id": 2,
    "blood_pressure": "120/80",
    "heart_rate": 78,
    "temperature": 98.6,
    "created_at": "2024-01-15T10:45:00Z"
  },
  "message": "Health record added successfully"
}
```

---

## ABHA Integration Endpoints

### Get ABHA Authorization URL
```
GET /api/abha/authorization-url
Authorization: Bearer {access_token}
```

Get OAuth URL to link ABHA account.

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "authorization_url": "https://healthiddev.ndhm.gov.in/oauth/authorize?client_id=...",
    "state": "random-state-token"
  }
}
```

---

### List Supported ABHA Operations
```
GET /api/abha/operations
Authorization: Bearer {access_token}
```

Returns all ABHA operations currently supported by the backend whitelist.

**Response (Success):**
```json
{
  "operations": {
    "auth.cert": {
      "method": "GET",
      "endpoint": "/v1/auth/cert",
      "required_fields": [],
      "requires_auth_token": false
    },
    "auth.init": {
      "method": "POST",
      "endpoint": "/v1/auth/init",
      "required_fields": ["authMethod", "healthId"],
      "requires_auth_token": false
    }
  },
  "count": 24
}
```

---

### Execute ABHA Operation
```
POST /api/abha/execute
Authorization: Bearer {access_token}
Content-Type: application/json
```

Executes one whitelisted ABHA operation and forwards payload to ABDM.

**Request Body:**
```json
{
  "operation": "auth.init",
  "payload": {
    "authMethod": "AADHAAR_OTP",
    "healthId": "user@abdm"
  }
}
```

**Response (Success):**
```json
{
  "operation": "auth.init",
  "endpoint": "/v1/auth/init",
  "response": {
    "txnId": "abc123..."
  }
}
```

---

### ABHA OAuth Callback
```
POST /api/abha/callback
Authorization: Bearer {access_token}
Content-Type: application/json
```

Handle ABHA OAuth callback after user authorization.

**Request Body:**
```json
{
  "code": "authorization-code",
  "state": "random-state-token"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "abha_id": "YYYY-YYYY-YYYY-YYYY",
    "access_token": "...",
    "expires_at": "2024-01-22T10:45:00Z"
  },
  "message": "ABHA account linked successfully"
}
```

---

### Get ABHA Health Data
```
GET /api/abha/health-data
Authorization: Bearer {access_token}
```

Fetch health data from linked ABHA account.

**Response (Success):**
```json
{
  "status": "success",
  "data": {
    "abha_id": "YYYY-YYYY-YYYY-YYYY",
    "health_data": {
      "vital_signs": [...],
      "allergies": [...],
      "medications": [...]
    },
    "last_synced_at": "2024-01-15T10:45:00Z"
  }
}
```

---

### Unlink ABHA Account
```
POST /api/abha/unlink
Authorization: Bearer {access_token}
```

Unlink ABHA account from user profile.

**Response (Success):**
```json
{
  "status": "success",
  "message": "ABHA account unlinked successfully"
}
```

---

### ABHA Operation Keys and Official ABDM Endpoints

| Operation Key | Method | Official Endpoint |
|---|---|---|
| auth.cert | GET | /v1/auth/cert |
| search.by_health_id | POST | /v1/search/searchByHealthId |
| auth.init | POST | /v1/auth/init |
| auth.confirm_aadhaar_otp | POST | /v1/auth/confirmWithAadhaarOtp |
| auth.confirm_mobile_otp | POST | /v1/auth/confirmWithMobileOTP |
| forgot.health_id.aadhaar.generate_otp | POST | /v2/forgot/healthId/aadhaar/generateOtp |
| forgot.health_id.aadhaar.verify | POST | /v2/forgot/healthId/aadhaar |
| forgot.health_id.mobile.generate_otp | POST | /v1/forgot/healthId/mobile/generateOtp |
| forgot.health_id.mobile.verify | POST | /v1/forgot/healthId/mobile |
| account.profile.get | GET | /v1/account/profile |
| account.qr_code.get | GET | /v1/account/qrCode |
| account.change_mobile.new.generate_otp | POST | /v2/account/change/mobile/new/generateOTP |
| account.change_mobile.new.verify_otp | POST | /v2/account/change/mobile/new/verifyOTP |
| account.change_mobile.aadhaar.generate_otp | POST | /v2/account/change/mobile/aadhaar/generateOTP |
| account.change_mobile.old.generate_otp | POST | /v2/account/change/mobile/old/generateOTP |
| account.change_mobile.update_authentication | POST | /v2/account/change/mobile/update/authentication |
| account.email.verification.initiate_send | POST | /v2/account/email/verification/auth/initiate/send |
| account.email.verification.verify | POST | /v2/account/email/verification/auth/verify |
| account.deactivate.generate_otp | POST | /v2/account/deactivate/generateOTP |
| account.mobile.generate_otp | POST | /v2/account/mobile/generateOTP |
| account.profile.delete | POST | /v2/account/profile/delete |
| account.aadhaar.generate_otp | POST | /v2/account/aadhaar/generateOTP |
| account.profile.deactivate | POST | /v2/account/profile/deactivate |

---

## Error Codes

| Code | Message | Description |
|------|---------|-------------|
| `INVALID_EMAIL` | Invalid email format | Email doesn't meet requirements |
| `EMAIL_NOT_FOUND` | Email not found | User doesn't exist |
| `INVALID_OTP` | Invalid or expired OTP | OTP is incorrect or expired |
| `MAX_OTP_ATTEMPTS` | Maximum OTP attempts exceeded | Too many failed verification attempts |
| `UNAUTHORIZED` | Unauthorized access | Missing or invalid token |
| `INVALID_SYMPTOMS` | Invalid symptom provided | Symptom not in database |
| `ABHA_ERROR` | ABHA API error | Error connecting to ABHA servers |
| `INTERNAL_ERROR` | Internal server error | Unknown error occurred |

---

## Rate Limiting

- **OTP Request:** 5 requests per minute per email
- **OTP Verification:** 3 attempts per OTP code
- **API Requests:** 100 requests per minute per user

---

## Request Examples

### cURL

**Request OTP:**
```bash
curl -X POST http://localhost:5000/api/auth/request-otp \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

**Verify OTP:**
```bash
curl -X POST http://localhost:5000/api/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "otp_code": "123456"}'
```

**Make Prediction:**
```bash
curl -X POST http://localhost:5000/api/predict \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symptoms": ["cough", "fever"],
    "health_vitals": {"temperature": 98.6}
  }'
```

### Python

```python
import requests

# Request OTP
response = requests.post(
    'http://localhost:5000/api/auth/request-otp',
    json={'email': 'user@example.com'}
)

# Get tokens
response = requests.post(
    'http://localhost:5000/api/auth/verify-otp',
    json={'email': 'user@example.com', 'otp_code': '123456'}
)
tokens = response.json()['data']
access_token = tokens['access_token']

# Make prediction
response = requests.post(
    'http://localhost:5000/api/predict',
    headers={'Authorization': f'Bearer {access_token}'},
    json={'symptoms': ['cough', 'fever']}
)
print(response.json())
```

### JavaScript/Fetch

```javascript
// Request OTP
const response = await fetch('http://localhost:5000/api/auth/request-otp', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({email: 'user@example.com'})
});

// Verify OTP and get tokens
const loginRes = await fetch('http://localhost:5000/api/auth/verify-otp', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    email: 'user@example.com',
    otp_code: '123456'
  })
});
const {data} = await loginRes.json();
const token = data.access_token;

// Make prediction
const predRes = await fetch('http://localhost:5000/api/predict', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({symptoms: ['cough', 'fever']})
});
const prediction = await predRes.json();
console.log(prediction);
```

---

## Changelog

### v1.0.0 (2024-01-15)
- Initial release
- Email/OTP authentication
- Disease prediction with confidence scores
- User profiles and health records
- ABHA integration framework
- Prediction history tracking

---

For support and issues, contact: support@healthguard.com
