from flask import Blueprint, render_template

from app.services.auth_service import current_user_from_cookie

ui_bp = Blueprint("ui", __name__)


@ui_bp.get("/")
def auth_page():
    return render_template("auth.html")


@ui_bp.get("/app")
def app_page():
    if not current_user_from_cookie():
        return render_template("auth.html")
    return render_template("app.html")
