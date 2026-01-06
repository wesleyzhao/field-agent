"""CLI commands for tunnel management."""

import asyncio

import click
from rich.console import Console
from rich.panel import Panel

from field_agent.tunnels import CloudflareTunnelProvider, TunnelError

console = Console()

# Global tunnel instance (persists across commands in same process)
_tunnel_provider = None


def get_tunnel_provider() -> CloudflareTunnelProvider:
    """Get or create the tunnel provider singleton."""
    global _tunnel_provider
    if _tunnel_provider is None:
        _tunnel_provider = CloudflareTunnelProvider()
    return _tunnel_provider


@click.group()
def tunnel():
    """Manage remote access tunnels."""
    pass


@tunnel.command()
@click.option("--port", "-p", default=8080, type=int, help="Local port to tunnel")
@click.option("--install", "do_install", is_flag=True, help="Auto-install cloudflared if missing")
def start(port: int, do_install: bool):
    """Start a tunnel for remote access."""
    provider = get_tunnel_provider()

    # Check if cloudflared is available
    if not provider.is_available:
        if do_install:
            console.print("[cyan]Installing cloudflared...[/cyan]")
            success = asyncio.run(provider.install())
            if not success:
                console.print("[red]Failed to install cloudflared automatically.[/red]")
                console.print(f"\nInstall manually:\n  {provider.get_install_instructions()}")
                raise SystemExit(1)
            console.print("[green]cloudflared installed successfully![/green]\n")
        else:
            console.print("[red]cloudflared not found.[/red]")
            console.print(f"\nInstall with:\n  {provider.get_install_instructions()}")
            console.print("\nOr run with --install to auto-install.")
            raise SystemExit(1)

    # Check if already running
    if provider.is_running():
        info = provider.get_info()
        console.print("[yellow]Tunnel is already running.[/yellow]")
        if info:
            console.print(f"\nURL: [cyan]{info.url}[/cyan]")
        return

    # Start tunnel
    console.print(f"[cyan]Starting tunnel to localhost:{port}...[/cyan]")

    try:
        info = asyncio.run(provider.start(port))
        console.print(Panel.fit(
            f"[bold green]Tunnel started![/bold green]\n\n"
            f"Access field-agent from anywhere:\n"
            f"  [cyan]{info.url}[/cyan]\n\n"
            f"[dim]Press Ctrl+C to stop[/dim]",
            border_style="green"
        ))

        # Keep running until interrupted
        try:
            while provider.is_running():
                asyncio.run(asyncio.sleep(1))
        except KeyboardInterrupt:
            pass

    except TunnelError as e:
        console.print(f"[red]Failed to start tunnel:[/red] {e}")
        raise SystemExit(1)
    finally:
        asyncio.run(provider.stop())
        console.print("\n[dim]Tunnel stopped.[/dim]")


@tunnel.command()
def stop():
    """Stop the running tunnel."""
    provider = get_tunnel_provider()

    if not provider.is_running():
        console.print("[yellow]No tunnel is running.[/yellow]")
        return

    asyncio.run(provider.stop())
    console.print("[green]Tunnel stopped.[/green]")


@tunnel.command()
def status():
    """Show tunnel status."""
    provider = get_tunnel_provider()

    if not provider.is_available:
        console.print(f"[yellow]cloudflared not installed.[/yellow]")
        console.print(f"\nInstall with:\n  {provider.get_install_instructions()}")
        return

    if not provider.is_running():
        console.print("[dim]No tunnel running.[/dim]")
        console.print("\nStart one with: [cyan]field-agent tunnel start[/cyan]")
        return

    info = provider.get_info()
    if info:
        console.print(f"[green]Tunnel running[/green]")
        console.print(f"\nURL: [cyan]{info.url}[/cyan]")
        console.print(f"Local port: {info.local_port}")
        console.print(f"Provider: {info.provider}")


@tunnel.command()
def install():
    """Install the cloudflared CLI tool."""
    provider = get_tunnel_provider()

    if provider.is_available:
        console.print("[green]cloudflared is already installed.[/green]")
        return

    console.print("[cyan]Installing cloudflared...[/cyan]")
    success = asyncio.run(provider.install())

    if success:
        console.print("[green]cloudflared installed successfully![/green]")
    else:
        console.print("[red]Automatic installation failed.[/red]")
        console.print(f"\nInstall manually:\n  {provider.get_install_instructions()}")
        raise SystemExit(1)
