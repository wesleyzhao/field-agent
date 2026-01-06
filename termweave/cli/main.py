"""CLI for termweave."""

import click
from rich.console import Console

from termweave import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """termweave - Browser-based tmux session manager."""
    pass


@cli.command()
@click.option("--host", "-h", default="0.0.0.0", help="Host to bind to")
@click.option("--port", "-p", default=8080, type=int, help="Port to listen on")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host: str, port: int, reload: bool):
    """Start the termweave server."""
    import uvicorn

    from termweave.config import Config, ConfigError

    # Validate config before starting
    try:
        config = Config.load()
        console.print(f"[green]Configuration loaded successfully[/green]")
    except ConfigError as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        console.print("\nMake sure you have set:")
        console.print("  - TERMWEAVE_SECRET_KEY (at least 32 characters)")
        console.print("  - TERMWEAVE_PASSPHRASE_HASH (run 'termweave hash-passphrase')")
        raise SystemExit(1)

    if not config.passphrase_hash:
        console.print("[yellow]Warning:[/yellow] No passphrase hash configured")
        console.print("Run 'termweave hash-passphrase' to generate one")

    console.print(f"\n[cyan]Starting termweave server...[/cyan]")
    console.print(f"  Host: {host}")
    console.print(f"  Port: {port}")
    console.print(f"  URL: http://{host}:{port}")
    console.print(f"\nPress Ctrl+C to stop\n")

    uvicorn.run(
        "termweave.server.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@cli.command("hash-passphrase")
def hash_passphrase():
    """Generate a bcrypt hash for a passphrase."""
    import getpass

    from termweave.auth import PassphraseHasher

    console.print("[cyan]Generate passphrase hash[/cyan]")
    console.print("Enter a strong passphrase (16+ characters recommended)\n")

    passphrase = getpass.getpass("Passphrase: ")
    if len(passphrase) < 8:
        console.print("[red]Error:[/red] Passphrase must be at least 8 characters")
        raise SystemExit(1)

    confirm = getpass.getpass("Confirm: ")
    if passphrase != confirm:
        console.print("[red]Error:[/red] Passphrases do not match")
        raise SystemExit(1)

    hasher = PassphraseHasher()
    hashed = hasher.hash_passphrase(passphrase)

    console.print("\n[green]Passphrase hash generated![/green]")
    console.print("\nAdd this to your environment or config:\n")
    console.print(f'  export TERMWEAVE_PASSPHRASE_HASH="{hashed}"')


@cli.command("generate-secret")
def generate_secret():
    """Generate a random secret key for JWT signing."""
    import secrets

    secret = secrets.token_urlsafe(32)

    console.print("[green]Secret key generated![/green]")
    console.print("\nAdd this to your environment or config:\n")
    console.print(f'  export TERMWEAVE_SECRET_KEY="{secret}"')


@cli.command()
def check():
    """Check configuration and dependencies."""
    import shutil

    console.print("[cyan]Checking termweave configuration...[/cyan]\n")

    # Check tmux
    tmux_path = shutil.which("tmux")
    if tmux_path:
        console.print(f"[green]✓[/green] tmux found: {tmux_path}")
    else:
        console.print("[red]✗[/red] tmux not found - please install tmux")

    # Check config
    from termweave.config import Config, ConfigError

    try:
        config = Config.load()
        console.print("[green]✓[/green] Configuration valid")

        if config.passphrase_hash:
            console.print("[green]✓[/green] Passphrase hash configured")
        else:
            console.print("[yellow]![/yellow] No passphrase hash (run 'termweave hash-passphrase')")

    except ConfigError as e:
        console.print(f"[red]✗[/red] Configuration error: {e}")


if __name__ == "__main__":
    cli()
