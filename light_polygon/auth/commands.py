from __future__ import annotations

import typer

from light_polygon.auth.manager import AuthError, UserManager
from light_polygon.auth.session import clear_session, load_session, save_session
from light_polygon.db.connection import init_db, get_connection
from light_polygon.utils.console import console

auth_app = typer.Typer(help="User management", no_args_is_help=True)


def get_current_user() -> str | None:
    return load_session()


def require_user() -> str:
    username = load_session()
    if username is None:
        console.print("[red]Not logged in. Run 'lp user login' first.[/red]")
        raise typer.Exit(1)
    return username


@auth_app.command()
def register(
    username: str = typer.Argument(..., help="Username for the new account"),
    display_name: str = typer.Option("", "--display-name", help="Display name"),
) -> None:
    """Register a new user account."""
    import getpass

    init_db()
    conn = get_connection()
    try:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            console.print("[red]Passwords do not match[/red]")
            raise typer.Exit(1)
        if len(password) < 4:
            console.print("[red]Password must be at least 4 characters[/red]")
            raise typer.Exit(1)

        mgr = UserManager(conn)
        user = mgr.register(username, password, display_name)
        conn.commit()
        console.print(f"[green]User '{user.username}' registered successfully.[/green]")
    except AuthError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        conn.close()


@auth_app.command()
def login(
    username: str = typer.Argument(..., help="Username"),
) -> None:
    """Log in to an existing account."""
    import getpass

    init_db()
    conn = get_connection()
    try:
        password = getpass.getpass("Password: ")
        mgr = UserManager(conn)
        user = mgr.verify(username, password)
        save_session(user.username)
        console.print(f"[green]Logged in as '{user.username}'.[/green]")
    except AuthError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        conn.close()


@auth_app.command()
def logout() -> None:
    """Log out of the current session."""
    username = load_session()
    if username:
        clear_session()
        console.print(f"[green]Logged out from '{username}'.[/green]")
    else:
        console.print("[dim]Not logged in.[/dim]")


@auth_app.command()
def whoami() -> None:
    """Show the currently logged-in user."""
    username = load_session()
    if username:
        console.print(f"Logged in as [bold]{username}[/bold]")
    else:
        console.print("[dim]Not logged in.[/dim]")


@auth_app.command("list")
def list_users() -> None:
    """List all registered users."""
    init_db()
    conn = get_connection()
    try:
        from light_polygon.db.models import User

        users = User.list_all(conn)
        if not users:
            console.print("[dim]No users registered yet.[/dim]")
            return
        from rich.table import Table

        table = Table(title="Users")
        table.add_column("ID", style="dim")
        table.add_column("Username")
        table.add_column("Display Name")
        table.add_column("Role")
        for u in users:
            table.add_row(str(u.id), u.username, u.display_name, u.role)
        console.print(table)
    finally:
        conn.close()
