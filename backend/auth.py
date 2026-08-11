import logging
import re
from datetime import datetime, timedelta, timezone

import jwt
from flask import Blueprint, jsonify, request

from email_utils import send_email
from extensions import db, limiter
from models import User
from utils import SECRET_KEY, TOKEN_EXPIRY_HOURS, error_response, token_required
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
logger = logging.getLogger("qdd.auth")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def issue_token(user):
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("10 per hour")
def register():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return error_response("Name, email and password are required")

    if not EMAIL_PATTERN.match(email):
        return error_response("Enter a valid email address")

    if len(password) < 6:
        return error_response("Password must be at least 6 characters")

    if User.query.filter_by(email=email).first() is not None:
        return error_response("An account with this email already exists", 409)

    user = User(name=name, email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()

    token = issue_token(user)

    return jsonify({
        "message": "Account created successfully",
        "token": token,
        "user": user.to_public_dict(),
    }), 201


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("15 per 15 minutes")
def login():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return error_response("Email and password are required")

    user = User.query.filter_by(email=email).first()

    if user is None or not check_password_hash(user.password_hash, password):
        return error_response("Invalid email or password", 401)

    token = issue_token(user)

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": user.to_public_dict(),
    })


@auth_bp.route("/me", methods=["GET"])
@token_required
def me():
    return jsonify({"user": request.user})


@auth_bp.route("/forgot-password", methods=["POST"])
@limiter.limit("5 per hour")
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    generic_response = jsonify({
        "message": "If an account exists for that email, a reset link has been sent"
    })

    if not email:
        return error_response("Email is required")

    user = User.query.filter_by(email=email).first()

    # Always return the same response whether or not the account exists,
    # so the endpoint can't be used to enumerate registered emails.
    if user is None:
        return generic_response

    raw_token = user.issue_reset_token()
    db.session.commit()

    reset_link = f"{request.headers.get('Origin', '')}/reset-password?token={raw_token}"

    send_email(
        user.email,
        "Reset your Quantum Drug Discovery password",
        f"Hi {user.name},\n\nUse the link below to reset your password. "
        f"It expires in 30 minutes.\n\n{reset_link}\n\n"
        f"If you didn't request this, you can ignore this email.",
    )

    return generic_response


@auth_bp.route("/reset-password", methods=["POST"])
@limiter.limit("10 per hour")
def reset_password():
    data = request.get_json(silent=True) or {}
    token = data.get("token") or ""
    new_password = data.get("password") or ""

    if not token or not new_password:
        return error_response("Reset token and new password are required")

    if len(new_password) < 6:
        return error_response("Password must be at least 6 characters")

    candidates = User.query.filter(User.reset_token_hash.isnot(None)).all()
    user = next((u for u in candidates if u.verify_reset_token(token)), None)

    if user is None:
        return error_response("This reset link is invalid or has expired", 400)

    user.password_hash = generate_password_hash(new_password)
    user.clear_reset_token()
    db.session.commit()

    logger.info("Password reset completed for user_id=%s", user.id)

    return jsonify({"message": "Password updated. You can now sign in."})
