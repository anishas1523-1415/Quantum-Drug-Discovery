"""Admin CLI commands: `flask users promote <email>` / `flask users list`.

Deliberately not exposed as an HTTP endpoint — granting the admin role
is an operator action (someone with shell/deploy access to the server),
not something reachable over the API by any authenticated user,
including existing admins. This is the standard pattern for the first
admin in a system that otherwise has no self-service path to that role.
"""

import click
from flask import Blueprint

from extensions import db
from models import ALL_ROLES, User

users_cli = Blueprint("users", __name__, cli_group="users")


@users_cli.cli.command("promote")
@click.argument("email")
@click.option("--role", default="admin", help="Role to grant (default: admin)")
def promote(email, role):
    role = role.strip().lower()

    if role not in ALL_ROLES:
        click.echo(f"Unknown role '{role}'. Valid roles: {', '.join(sorted(ALL_ROLES))}")
        raise SystemExit(1)

    user = User.query.filter_by(email=email.strip().lower()).first()

    if user is None:
        click.echo(f"No user found with email '{email}'")
        raise SystemExit(1)

    previous_role = user.role
    user.role = role
    db.session.commit()

    click.echo(f"Updated {user.email}: {previous_role} -> {role}")


@users_cli.cli.command("list")
def list_users():
    users = User.query.order_by(User.created_at).all()

    if not users:
        click.echo("No users found.")
        return

    for user in users:
        click.echo(f"{user.id:>4}  {user.role:<11} {user.email:<35} {user.name}")
