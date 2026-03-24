"""ABHA (Ayushman Bharat Health Account) API integration helpers."""

from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import requests
from flask import current_app

from models import ABHAToken, HealthRecord, User, db


class ABHAService:
    """Service layer for ABHA/ABDM API operations."""

    OPERATION_CATALOG = {
        # Login via Aadhaar/Mobile OTP
        "auth.cert": {
            "method": "GET",
            "endpoint": "/v1/auth/cert",
            "required_fields": [],
            "requires_auth_token": False,
        },
        "search.by_health_id": {
            "method": "POST",
            "endpoint": "/v1/search/searchByHealthId",
            "required_fields": ["healthId"],
            "requires_auth_token": False,
        },
        "auth.init": {
            "method": "POST",
            "endpoint": "/v1/auth/init",
            "required_fields": ["authMethod", "healthId"],
            "requires_auth_token": False,
        },
        "auth.confirm_aadhaar_otp": {
            "method": "POST",
            "endpoint": "/v1/auth/confirmWithAadhaarOtp",
            "required_fields": ["otp", "txnId"],
            "requires_auth_token": False,
        },
        "auth.confirm_mobile_otp": {
            "method": "POST",
            "endpoint": "/v1/auth/confirmWithMobileOTP",
            "required_fields": ["otp", "txnId"],
            "requires_auth_token": False,
        },
        # Retrieve forgotten ABHA
        "forgot.health_id.aadhaar.generate_otp": {
            "method": "POST",
            "endpoint": "/v2/forgot/healthId/aadhaar/generateOtp",
            "required_fields": ["aadhaar"],
            "requires_auth_token": False,
        },
        "forgot.health_id.aadhaar.verify": {
            "method": "POST",
            "endpoint": "/v2/forgot/healthId/aadhaar",
            "required_fields": ["txnId", "otp"],
            "requires_auth_token": False,
        },
        "forgot.health_id.mobile.generate_otp": {
            "method": "POST",
            "endpoint": "/v1/forgot/healthId/mobile/generateOtp",
            "required_fields": ["mobile"],
            "requires_auth_token": False,
        },
        "forgot.health_id.mobile.verify": {
            "method": "POST",
            "endpoint": "/v1/forgot/healthId/mobile",
            "required_fields": ["otp", "txnId"],
            "requires_auth_token": False,
        },
        # User profile and QR
        "account.profile.get": {
            "method": "GET",
            "endpoint": "/v1/account/profile",
            "required_fields": [],
            "requires_auth_token": True,
        },
        "account.qr_code.get": {
            "method": "GET",
            "endpoint": "/v1/account/qrCode",
            "required_fields": [],
            "requires_auth_token": True,
        },
        # Update mobile via Aadhaar OTP / Mobile OTP
        "account.change_mobile.new.generate_otp": {
            "method": "POST",
            "endpoint": "/v2/account/change/mobile/new/generateOTP",
            "required_fields": ["mobile"],
            "requires_auth_token": True,
        },
        "account.change_mobile.new.verify_otp": {
            "method": "POST",
            "endpoint": "/v2/account/change/mobile/new/verifyOTP",
            "required_fields": ["otp", "txnId"],
            "requires_auth_token": True,
        },
        "account.change_mobile.aadhaar.generate_otp": {
            "method": "POST",
            "endpoint": "/v2/account/change/mobile/aadhaar/generateOTP",
            "required_fields": ["txnId"],
            "requires_auth_token": True,
        },
        "account.change_mobile.old.generate_otp": {
            "method": "POST",
            "endpoint": "/v2/account/change/mobile/old/generateOTP",
            "required_fields": ["txnId"],
            "requires_auth_token": True,
        },
        "account.change_mobile.update_authentication": {
            "method": "POST",
            "endpoint": "/v2/account/change/mobile/update/authentication",
            "required_fields": ["otp", "txnId"],
            "requires_auth_token": True,
        },
        # Update email via Aadhaar OTP / Mobile OTP
        "account.email.verification.initiate_send": {
            "method": "POST",
            "endpoint": "/v2/account/email/verification/auth/initiate/send",
            "required_fields": ["authMethod", "email"],
            "requires_auth_token": True,
        },
        "account.email.verification.verify": {
            "method": "POST",
            "endpoint": "/v2/account/email/verification/auth/verify",
            "required_fields": ["txnId", "otp", "authMethod"],
            "requires_auth_token": True,
        },
        # Delete health ID
        "account.deactivate.generate_otp": {
            "method": "POST",
            "endpoint": "/v2/account/deactivate/generateOTP",
            "required_fields": ["aadhaar"],
            "requires_auth_token": True,
        },
        "account.mobile.generate_otp": {
            "method": "POST",
            "endpoint": "/v2/account/mobile/generateOTP",
            "required_fields": [],
            "requires_auth_token": True,
        },
        "account.profile.delete": {
            "method": "POST",
            "endpoint": "/v2/account/profile/delete",
            "required_fields": ["otp", "txnId"],
            "requires_auth_token": True,
        },
        # Deactivate health ID
        "account.aadhaar.generate_otp": {
            "method": "POST",
            "endpoint": "/v2/account/aadhaar/generateOTP",
            "required_fields": ["aadhaar"],
            "requires_auth_token": True,
        },
        "account.profile.deactivate": {
            "method": "POST",
            "endpoint": "/v2/account/profile/deactivate",
            "required_fields": ["authMethod", "otp", "txnId"],
            "requires_auth_token": True,
        },
    }

    @staticmethod
    def get_base_url():
        raw_url = current_app.config.get("ABHA_API_URL", "https://healthiddev.ndhm.gov.in")
        parsed = urlsplit((raw_url or "").strip())

        # Keep only scheme + host; docs links like /docs/healthid are not API bases.
        if parsed.scheme and parsed.netloc:
            return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")

        return "https://sandbox.abdm.gov.in"

    @staticmethod
    def get_base_url_candidates():
        """Return preferred ABHA API host plus fallback hosts."""
        primary = ABHAService.get_base_url()
        fallbacks = [
            "https://sandbox.abdm.gov.in",
            "https://healthiddev.ndhm.gov.in",
        ]
        ordered = [primary] + [url for url in fallbacks if url != primary]
        return ordered

    @staticmethod
    def get_operation_catalog():
        return ABHAService.OPERATION_CATALOG

    @staticmethod
    def _headers(auth_token=None, accept="application/json"):
        headers = {
            "Accept": accept,
            "Content-Type": "application/json",
            "REQUEST-ID": str(uuid4()),
            "TIMESTAMP": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
        cm_id = (current_app.config.get("ABHA_CM_ID") or "").strip()
        if cm_id:
            headers["X-CM-ID"] = cm_id
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        return headers

    @staticmethod
    def _request(method, endpoint, payload=None, auth_token=None, timeout=25, accept="application/json"):
        last_error = None
        for base_url in ABHAService.get_base_url_candidates():
            url = f"{base_url}{endpoint}"
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=ABHAService._headers(auth_token=auth_token, accept=accept),
                    json=payload,
                    timeout=timeout,
                )
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    body = response.json()
                else:
                    body = response.text

                if response.ok:
                    return True, body, response.status_code
                return False, {"status_code": response.status_code, "response": body}, response.status_code
            except requests.RequestException as exc:
                last_error = exc
                # Retry with fallback host only for name resolution failures.
                if "getaddrinfo failed" in str(exc).lower() or "nameresolutionerror" in str(exc).lower():
                    continue
                return False, {
                    "status_code": 503,
                    "response": f"ABHA upstream request failed: {str(exc)}"
                }, 503

        return False, {
            "status_code": 503,
            "response": f"ABHA upstream request failed: {str(last_error)}"
        }, 503

    @staticmethod
    def execute_operation(operation, payload=None, auth_token=None):
        payload = payload or {}
        op = ABHAService.OPERATION_CATALOG.get(operation)
        if not op:
            return False, {"error": "Unsupported ABHA operation", "operation": operation}, 400

        missing = [field for field in op["required_fields"] if payload.get(field) in (None, "")]
        if missing:
            return False, {"error": "Missing required fields", "missing": missing}, 400

        if op["requires_auth_token"] and not auth_token:
            return False, {"error": "ABHA auth token is required for this operation"}, 401

        if operation == "forgot.health_id.mobile.generate_otp":
            raw_mobile = str(payload.get("mobile", "")).strip()
            digits = "".join(ch for ch in raw_mobile if ch.isdigit())
            last10 = digits[-10:] if len(digits) >= 10 else digits

            candidate_values = []
            for value in [raw_mobile, digits, last10, f"91{last10}" if last10 else ""]:
                if value and value not in candidate_values:
                    candidate_values.append(value)

            last_failure = None
            for mobile_value in candidate_values:
                success, result, status_code = ABHAService._request(
                    method=op["method"],
                    endpoint=op["endpoint"],
                    payload={"mobile": mobile_value},
                    auth_token=auth_token,
                    accept="application/json",
                )
                if success:
                    return success, result, status_code

                last_failure = (success, result, status_code)

                # For format-related validation failures, try next candidate.
                if status_code in {400, 422}:
                    continue

                return success, result, status_code

            if last_failure:
                return last_failure

        request_payload = payload if op["method"] != "GET" else None
        return ABHAService._request(
            method=op["method"],
            endpoint=op["endpoint"],
            payload=request_payload,
            auth_token=auth_token,
            accept="image/png" if operation == "account.qr_code.get" else "application/json",
        )

    @staticmethod
    def get_authorization_url(state):
        """Generate ABHA authorization URL for OAuth flow."""
        auth_url = f"{ABHAService.get_base_url()}/oauth/authorize"
        params = {
            "client_id": current_app.config["ABHA_CLIENT_ID"],
            "redirect_uri": current_app.config["ABHA_REDIRECT_URI"],
            "response_type": "code",
            "scope": "openid profile health_record",
            "state": state,
        }
        query_string = "&".join([f"{key}={value}" for key, value in params.items()])
        return f"{auth_url}?{query_string}"

    @staticmethod
    def exchange_code_for_token(code):
        """Exchange authorization code for access token."""
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": current_app.config["ABHA_CLIENT_ID"],
            "client_secret": current_app.config["ABHA_CLIENT_SECRET"],
            "redirect_uri": current_app.config["ABHA_REDIRECT_URI"],
        }
        return ABHAService._request("POST", "/oauth/token", payload=payload, auth_token=None)

    @staticmethod
    def get_user_health_data(access_token):
        """Fetch profile and health data using ABHA account profile endpoint."""
        profile_ok, profile_data, _ = ABHAService.execute_operation(
            operation="account.profile.get",
            payload={},
            auth_token=access_token,
        )
        if not profile_ok:
            return False, profile_data

        return True, {"profile": profile_data}

    @staticmethod
    def link_abha_account(user_id, access_token, abha_id):
        """Link ABHA account to user and persist token."""
        try:
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"

            user.abha_id = abha_id or user.abha_id
            user.abha_token = access_token
            user.abha_linked_at = datetime.utcnow()

            token = ABHAToken.query.filter_by(user_id=user_id).first()
            if not token:
                token = ABHAToken(user_id=user_id, access_token=access_token, token_type="Bearer")
                db.session.add(token)
            else:
                token.access_token = access_token

            token.expires_at = datetime.utcnow() + timedelta(hours=24)
            token.updated_at = datetime.utcnow()
            db.session.commit()
            return True, "ABHA account linked successfully"
        except Exception as exc:
            db.session.rollback()
            return False, f"Failed to link ABHA account: {str(exc)}"

    @staticmethod
    def fetch_and_store_health_records(user_id, access_token):
        """Fetch ABHA profile data and store raw payload in health records."""
        try:
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"

            success, data = ABHAService.get_user_health_data(access_token)
            if not success:
                return False, data

            health_record = HealthRecord(user_id=user_id, abha_data=data)
            db.session.add(health_record)
            db.session.commit()
            return True, "Health records fetched and stored successfully"
        except Exception as exc:
            db.session.rollback()
            return False, f"Failed to fetch health records: {str(exc)}"

    @staticmethod
    def refresh_abha_token(user_id):
        """Refresh ABHA access token if expired."""
        try:
            abha_token = ABHAToken.query.filter_by(user_id=user_id).first()
            if not abha_token:
                return False, "No ABHA token found"

            if not abha_token.is_expired():
                return True, abha_token.access_token

            if not abha_token.refresh_token:
                return False, "No refresh token available"

            payload = {
                "grant_type": "refresh_token",
                "refresh_token": abha_token.refresh_token,
                "client_id": current_app.config["ABHA_CLIENT_ID"],
                "client_secret": current_app.config["ABHA_CLIENT_SECRET"],
            }
            ok, response_data, _ = ABHAService._request("POST", "/oauth/token", payload=payload)
            if not ok:
                return False, response_data

            access_token = response_data.get("access_token")
            if not access_token:
                return False, "Refresh response did not include access_token"

            abha_token.access_token = access_token
            if response_data.get("refresh_token"):
                abha_token.refresh_token = response_data["refresh_token"]
            abha_token.expires_at = datetime.utcnow() + timedelta(hours=24)
            abha_token.updated_at = datetime.utcnow()
            db.session.commit()

            return True, access_token
        except Exception as exc:
            return False, f"Failed to refresh token: {str(exc)}"
