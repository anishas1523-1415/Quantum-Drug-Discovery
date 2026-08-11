import secrets
from datetime import datetime, timedelta, timezone

from extensions import db

RESET_TOKEN_TTL_MINUTES = 30


def utcnow():
    return datetime.now(timezone.utc)


def _as_aware_utc(value):
    """SQLite drops tzinfo on round-trip; Postgres keeps it. Normalize
    to an aware UTC datetime either way before comparing."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    reset_token_hash = db.Column(db.String(64), nullable=True)
    reset_token_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)

    audit_logs = db.relationship("AuditLog", backref="user", lazy=True)

    def to_public_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email}

    def issue_reset_token(self):
        raw_token = secrets.token_urlsafe(32)
        self.reset_token_hash = _hash_token(raw_token)
        self.reset_token_expires_at = utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
        return raw_token

    def verify_reset_token(self, raw_token):
        if not self.reset_token_hash or not self.reset_token_expires_at:
            return False

        if utcnow() > _as_aware_utc(self.reset_token_expires_at):
            return False

        return secrets.compare_digest(self.reset_token_hash, _hash_token(raw_token))

    def clear_reset_token(self):
        self.reset_token_hash = None
        self.reset_token_expires_at = None


def _hash_token(raw_token):
    import hashlib

    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class AuditLog(db.Model):
    """Traceability log: records that an action happened, never patient data."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(64), nullable=False)
    detail = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
