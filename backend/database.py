import logging

from sqlalchemy.exc import OperationalError, ProgrammingError
from werkzeug.security import generate_password_hash

from extensions import db
from models import User

logger = logging.getLogger("qdd.database")


def seed_demo_user():
    """Create the demo doctor and admin accounts on first run (idempotent).

    No-ops quietly on any OperationalError/ProgrammingError — this covers
    both "table doesn't exist yet" (e.g. this app context was created by
    `flask db migrate` before the first migration has been applied) and
    "database is locked" (a concurrent process, e.g. the dev server, is
    using the same SQLite file). The log message reports the real
    exception rather than assuming which of those it was.
    """

    try:
        existing = User.query.filter_by(email="doctor@gmail.com").first()
    except (OperationalError, ProgrammingError) as exc:
        logger.warning("Skipping demo user seed, database not ready: %s", exc)
        db.session.rollback()
        return

    if existing is None:
        demo_user = User(
            name="Dr. Demo",
            email="doctor@gmail.com",
            password_hash=generate_password_hash("password123"),
            role="doctor",
        )
        db.session.add(demo_user)

    existing_admin = User.query.filter_by(email="admin@gmail.com").first()

    if existing_admin is None:
        demo_admin = User(
            name="Admin Demo",
            email="admin@gmail.com",
            password_hash=generate_password_hash("adminpass123"),
            role="admin",
        )
        db.session.add(demo_admin)

    db.session.commit()
