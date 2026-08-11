import os
from functools import wraps

import jwt
from flask import jsonify, request

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
TOKEN_EXPIRY_HOURS = 12

ALLOWED_EXTENSIONS = {"csv"}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def error_response(message, status_code=400):
    return jsonify({"message": message}), status_code


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return error_response("Authentication token is missing", 401)

        token = auth_header.split(" ", 1)[1]

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return error_response("Session expired, please log in again", 401)
        except jwt.InvalidTokenError:
            return error_response("Invalid authentication token", 401)

        sub = payload.get("sub")

        request.user = {
            "id": int(sub) if sub is not None else None,
            "email": payload.get("email"),
            "name": payload.get("name"),
        }

        return f(*args, **kwargs)

    return decorated
