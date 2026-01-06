"""Interactive setup wizard for field-agent."""

import getpass
import os
import secrets
import shutil
import sys
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console
from rich.panel import Panel

from field_agent.auth import PassphraseHasher

console = Console()

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "field-agent"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"


def check_tmux() -> bool:
    """Check if tmux is installed."""
    return shutil.which("tmux") is not None


def get_tmux_install_instructions() -> str:
    """Get OS-specific tmux installation instructions."""
    if sys.platform == "darwin":
        return "brew install tmux"
    elif sys.platform.startswith("linux"):
        # Check for common package managers
        if shutil.which("apt-get"):
            return "sudo apt-get install tmux"
        elif shutil.which("yum"):
            return "sudo yum install tmux"
        elif shutil.which("dnf"):
            return "sudo dnf install tmux"
        elif shutil.which("pacman"):
            return "sudo pacman -S tmux"
        else:
            return "Install tmux using your package manager"
    else:
        return "Install tmux for your operating system"


def generate_secret_key() -> str:
    """Generate a secure secret key."""
    return secrets.token_urlsafe(32)


def prompt_passphrase() -> Optional[str]:
    """Prompt user for passphrase with confirmation."""
    console.print("\n[cyan]Set your login passphrase[/cyan]")
    console.print("This is what you'll enter to access field-agent from your browser.")
    console.print("Use at least 8 characters (16+ recommended).\n")

    while True:
        passphrase = getpass.getpass("Enter passphrase: ")

        if len(passphrase) < 8:
            console.print("[red]Passphrase must be at least 8 characters. Try again.[/red]\n")
            continue

        confirm = getpass.getpass("Confirm passphrase: ")

        if passphrase != confirm:
            console.print("[red]Passphrases don't match. Try again.[/red]\n")
            continue

        return passphrase


def save_config(
    config_path: Path,
    secret_key: str,
    passphrase_hash: str,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> None:
    """Save configuration to YAML file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config = {
        "secret_key": secret_key,
        "passphrase_hash": passphrase_hash,
        "host": host,
        "port": port,
    }

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    # Set restrictive permissions (readable only by owner)
    os.chmod(config_path, 0o600)


def load_existing_config(config_path: Path) -> Optional[dict]:
    """Load existing config if it exists."""
    if not config_path.exists():
        return None

    try:
        with open(config_path) as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def run_setup(config_path: Optional[Path] = None, force: bool = False) -> bool:
    """Run the interactive setup wizard.

    Args:
        config_path: Path to save config (default: ~/.config/field-agent/config.yaml)
        force: If True, overwrite existing config without asking

    Returns:
        True if setup completed successfully, False otherwise
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_FILE

    console.print(Panel.fit(
        "[bold cyan]field-agent Setup[/bold cyan]\n"
        "This wizard will configure field-agent for you.",
        border_style="cyan"
    ))

    # Step 1: Check for existing config
    existing_config = load_existing_config(config_path)
    if existing_config and not force:
        console.print(f"\n[yellow]Existing config found at {config_path}[/yellow]")
        response = console.input("Overwrite? [y/N]: ").strip().lower()
        if response != "y":
            console.print("[dim]Setup cancelled. Existing config preserved.[/dim]")
            return False

    # Step 2: Check tmux
    console.print("\n[bold]Step 1: Checking dependencies[/bold]")
    if check_tmux():
        console.print("[green]  ✓[/green] tmux found")
    else:
        console.print("[red]  ✗[/red] tmux not found")
        install_cmd = get_tmux_install_instructions()
        console.print(f"\n[yellow]Please install tmux first:[/yellow]")
        console.print(f"  {install_cmd}")
        console.print("\nThen run 'field-agent setup' again.")
        return False

    # Step 3: Generate secret key
    console.print("\n[bold]Step 2: Generating secret key[/bold]")
    secret_key = generate_secret_key()
    console.print("[green]  ✓[/green] Secret key generated")

    # Step 4: Prompt for passphrase
    console.print("\n[bold]Step 3: Setting passphrase[/bold]")
    passphrase = prompt_passphrase()
    if passphrase is None:
        console.print("[red]Setup cancelled.[/red]")
        return False

    hasher = PassphraseHasher()
    passphrase_hash = hasher.hash_passphrase(passphrase)
    console.print("[green]  ✓[/green] Passphrase hash generated")

    # Step 5: Save config
    console.print("\n[bold]Step 4: Saving configuration[/bold]")
    save_config(config_path, secret_key, passphrase_hash)
    console.print(f"[green]  ✓[/green] Config saved to {config_path}")

    # Success message
    console.print(Panel.fit(
        "[bold green]Setup complete![/bold green]\n\n"
        "Start the server:\n"
        "  [cyan]field-agent serve[/cyan]\n\n"
        "Then open in your browser:\n"
        "  [cyan]http://localhost:8080[/cyan]\n\n"
        "For remote access (phone/tablet):\n"
        "  [cyan]field-agent serve --tunnel[/cyan]",
        border_style="green"
    ))

    return True
