"""Admin-only endpoints: audit log visibility.

AuditLog rows have been written since the upload/recommend/analyze
endpoints were built, but nothing ever surfaced them until now — this
closes that gap rather than leaving traceability data collected but
unreachable, which isn't real auditability.
"""

from flask import Blueprint, jsonify, request

from models import AuditLog, User
from utils import error_response, role_required, token_required

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25


@admin_bp.route("/audit-logs", methods=["GET"])
@token_required
@role_required("admin")
def audit_logs():
    try:
        page = max(1, int(request.args.get("page", 1)))
        page_size = min(MAX_PAGE_SIZE, max(1, int(request.args.get("page_size", DEFAULT_PAGE_SIZE))))
    except ValueError:
        return error_response("page and page_size must be integers")

    query = AuditLog.query.order_by(AuditLog.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    user_ids = {row.user_id for row in rows if row.user_id is not None}
    users_by_id = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}

    entries = []
    for row in rows:
        user = users_by_id.get(row.user_id)
        entries.append({
            "id": row.id,
            "action": row.action,
            "detail": row.detail,
            "created_at": row.created_at.isoformat(),
            "user": {"id": user.id, "email": user.email, "name": user.name} if user else None,
        })

    return jsonify({
        "entries": entries,
        "page": page,
        "page_size": page_size,
        "total": total,
    })


@admin_bp.route("/users", methods=["GET"])
@token_required
@role_required("admin")
def list_users():
    users = User.query.order_by(User.created_at).all()
    return jsonify({"users": [u.to_public_dict() for u in users]})
