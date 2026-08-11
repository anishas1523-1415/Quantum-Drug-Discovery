import logging

from sqlalchemy.exc import OperationalError, ProgrammingError
from werkzeug.security import generate_password_hash

from extensions import db
from models import User

logger = logging.getLogger("qdd.database")


def seed_demo_user():
    """Create the demo doctor account on first run (idempotent).

    No-ops quietly if the users table doesn't exist yet (e.g. this app
    context was created by `flask db migrate` before the first migration
    has been applied).
    """

    try:
        existing = User.query.filter_by(email="doctor@gmail.com").first()
    except (OperationalError, ProgrammingError):
        logger.warning("Skipping demo user seed: users table not migrated yet")
        db.session.rollback()
        return

    if existing is None:
        demo_user = User(
            name="Dr. Demo",
            email="doctor@gmail.com",
            password_hash=generate_password_hash("password123"),
        )
        db.session.add(demo_user)
        db.session.commit()
