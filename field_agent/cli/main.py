"""CLI for field-agent."""

import click
from rich.console import Console

from field_agent import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """field-agent - Browser-based tmux session manager."""
    pass


@cli.command()
@click.option("--host", "-h", default="0.0.0.0", help="Host to bind to")
@click.option("--port", "-p", default=8080, type=int, help="Port to listen on")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.option("--tunnel", is_flag=True, help="Start a Cloudflare tunnel for remote access")
def serve(host: str, port: int, reload: bool, tunnel: bool):
    """Start the field-agent server."""
    import asyncio
    import threading

    import uvicorn

    from field_agent.config import Config, ConfigError

    # Validate config before starting
    try:
        config = Config.load()
        console.print(f"[green]Configuration loaded successfully[/green]")
    except ConfigError as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        console.print("\nMake sure you have run: [cyan]field-agent setup[/cyan]")
        console.print("\nOr manually set:")
        console.print("  - FIELD_AGENT_SECRET_KEY (at least 32 characters)")
        console.print("  - FIELD_AGENT_PASSPHRASE_HASH (run 'field-agent hash-passphrase')")
        raise SystemExit(1)

    if not config.passphrase_hash:
        console.print("[yellow]Warning:[/yellow] No passphrase hash configured")
        console.print("Run 'field-agent setup' or 'field-agent hash-passphrase' to configure")

    console.print(f"\n[cyan]Starting field-agent server...[/cyan]")
    console.print(f"  Host: {host}")
    console.print(f"  Port: {port}")
    console.print(f"  Local URL: http://localhost:{port}")

    # Start tunnel if requested
    tunnel_provider = None
    if tunnel:
        from field_agent.tunnels import CloudflareTunnelProvider, TunnelError

        tunnel_provider = CloudflareTunnelProvider()

        if not tunnel_provider.is_available:
            console.print("\n[yellow]cloudflared not found. Attempting to install...[/yellow]")
            success = asyncio.get_event_loop().run_until_complete(tunnel_provider.install())
            if not success:
                console.print(f"[red]Failed to install cloudflared.[/red]")
                console.print(f"\nInstall manually:\n  {tunnel_provider.get_install_instructions()}")
                console.print("\nStarting without tunnel...")
                tunnel_provider = None

        if tunnel_provider:
            console.print("\n[cyan]Starting tunnel...[/cyan]")
            try:
                info = asyncio.get_event_loop().run_until_complete(tunnel_provider.start(port))
                console.print(f"\n[bold green]Remote access enabled![/bold green]")
                console.print(f"  Public URL: [cyan]{info.url}[/cyan]")
            except TunnelError as e:
                console.print(f"[red]Failed to start tunnel:[/red] {e}")
                console.print("\nStarting without tunnel...")
                tunnel_provider = None

    console.print(f"\nPress Ctrl+C to stop\n")

    try:
        uvicorn.run(
            "field_agent.server.app:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info",
        )
    finally:
        if tunnel_provider:
            asyncio.get_event_loop().run_until_complete(tunnel_provider.stop())
            console.print("\n[dim]Tunnel stopped.[/dim]")


@cli.command("hash-passphrase")
def hash_passphrase():
    """Generate a bcrypt hash for a passphrase."""
    import getpass

    from field_agent.auth import PassphraseHasher

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
    console.print(f'  export FIELD_AGENT_PASSPHRASE_HASH="{hashed}"')


@cli.command("generate-secret")
def generate_secret():
    """Generate a random secret key for JWT signing."""
    import secrets

    secret = secrets.token_urlsafe(32)

    console.print("[green]Secret key generated![/green]")
    console.print("\nAdd this to your environment or config:\n")
    console.print(f'  export FIELD_AGENT_SECRET_KEY="{secret}"')


@cli.command()
@click.option("--force", "-f", is_flag=True, help="Overwrite existing config without asking")
def setup(force: bool):
    """Interactive setup wizard - configure field-agent in one command."""
    from field_agent.cli.setup import run_setup

    success = run_setup(force=force)
    if not success:
        raise SystemExit(1)


@cli.command()
def check():
    """Check configuration and dependencies."""
    import shutil

    console.print("[cyan]Checking field-agent configuration...[/cyan]\n")

    # Check tmux
    tmux_path = shutil.which("tmux")
    if tmux_path:
        console.print(f"[green]✓[/green] tmux found: {tmux_path}")
    else:
        console.print("[red]✗[/red] tmux not found - please install tmux")

    # Check config
    from field_agent.config import Config, ConfigError

    try:
        config = Config.load()
        console.print("[green]✓[/green] Configuration valid")

        if config.passphrase_hash:
            console.print("[green]✓[/green] Passphrase hash configured")
        else:
            console.print("[yellow]![/yellow] No passphrase hash (run 'field-agent hash-passphrase')")

    except ConfigError as e:
        console.print(f"[red]✗[/red] Configuration error: {e}")


# Register tunnel subcommand group
from field_agent.cli.tunnel import tunnel

cli.add_command(tunnel)


if __name__ == "__main__":
    cli()
