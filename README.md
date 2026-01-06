# field-agent

**Access your tmux sessions from anywhere - including your phone.**

field-agent is a lightweight web-based terminal that lets you manage and attach to tmux sessions through your browser. Perfect for:
- Checking on long-running processes from your iPhone
- Managing remote development sessions without SSH apps
- Quick terminal access when you're away from your desk

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (iPhone, iPad, Desktop)                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ field-agent                              [Logout]      │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │                                                     │    │
│  │  claude-agent-1              ●  2 windows   5m ago  │    │
│  │  dev-server                  ○  1 window    2h ago  │    │
│  │  monitoring                  ○  3 windows   1d ago  │    │
│  │                                                     │    │
│  │                    [+ New Session]                  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              ↓ tap to attach
┌─────────────────────────────────────────────────────────────┐
│  Full terminal with xterm.js - works on mobile!             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ $ claude "build a REST API"                         │    │
│  │ ● Working on feature 3/5: User authentication...    │    │
│  │ █                                                   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start (5 minutes)

### 1. Install

```bash
cd ~
git clone https://github.com/yourusername/field-agent.git
cd field-agent
pip install -e .
```

### 2. Generate your credentials

```bash
# Generate a secure secret key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Copy the output - this is your SECRET_KEY

# Generate a passphrase hash (you'll be prompted to enter a passphrase)
python3 -c "from field_agent.auth import PassphraseHasher; print(PassphraseHasher().hash_passphrase(input('Enter passphrase: ')))"
# Copy the output - this is your PASSPHRASE_HASH
```

### 3. Start the server

```bash
export FIELD_AGENT_SECRET_KEY="paste-your-secret-key-here"
export FIELD_AGENT_PASSPHRASE_HASH="paste-your-hash-here"

field-agent serve --host 0.0.0.0 --port 8080
```

### 4. Open in browser

Go to `http://your-server-ip:8080` and login with your passphrase.

That's it! You can now manage tmux sessions from any browser.

---

## Accessing from iPhone / Remote

If your server is on a cloud VM (like GCP), you'll need to:

1. **Open the firewall** for port 8080:
   ```bash
   # GCP example
   gcloud compute firewall-rules create allow-field-agent \
     --allow tcp:8080 \
     --source-ranges 0.0.0.0/0 \
     --description "Allow field-agent access"
   ```

2. **Get your external IP**:
   ```bash
   curl ifconfig.me
   ```

3. **Access from phone**: Open `http://YOUR_EXTERNAL_IP:8080`

---

## Configuration

All configuration is via environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FIELD_AGENT_SECRET_KEY` | **Yes** | - | JWT signing key (min 32 characters) |
| `FIELD_AGENT_PASSPHRASE_HASH` | **Yes** | - | bcrypt hash of your login passphrase |
| `FIELD_AGENT_HOST` | No | `0.0.0.0` | Server bind address |
| `FIELD_AGENT_PORT` | No | `8080` | Server port |
| `FIELD_AGENT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `15` | Access token lifetime |
| `FIELD_AGENT_REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token lifetime |
| `FIELD_AGENT_DEBUG` | No | `false` | Enable debug mode |

### Using a config file (optional)

Create `~/.config/field-agent/config.yaml`:

```yaml
host: 0.0.0.0
port: 8080
secret_key: your-secret-key-here
passphrase_hash: $2b$12$...your-hash-here...
```

---

## CLI Commands

```bash
# Start the server
field-agent serve [--host HOST] [--port PORT]

# Generate a passphrase hash (interactive, secure)
field-agent hash-passphrase

# Generate a random secret key
field-agent generate-secret

# Check configuration and dependencies
field-agent check

# Show version
field-agent --version
```

---

## Security Notes

- **Passphrase**: Use a strong passphrase (16+ characters recommended)
- **HTTPS**: For production, put field-agent behind a reverse proxy (nginx, Caddy) with HTTPS
- **Firewall**: Restrict access to trusted IPs if possible
- **Tokens**: Access tokens expire in 15 minutes; refresh tokens in 7 days

---

## Troubleshooting

### "Failed to load sessions"
- Check that tmux is installed: `which tmux`
- Check server logs for errors

### "WebSocket connection failed"
- Ensure the server is running
- Check firewall allows WebSocket connections on port 8080
- Try refreshing the page

### "Invalid passphrase"
- Make sure you're using the same passphrase you used when generating the hash
- Passphrase is case-sensitive

### Rate limited (429 error)
- Wait 60 seconds and try again
- The server limits login attempts to prevent brute force attacks

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with auto-reload for development
FIELD_AGENT_DEBUG=true field-agent serve
```

---

## How It Works

1. **Authentication**: Passphrase verified against bcrypt hash, returns JWT tokens
2. **Session Management**: REST API wraps tmux commands (list-sessions, new-session, kill-session)
3. **Terminal Attach**: WebSocket connects to a PTY running `tmux attach-session`
4. **Frontend**: xterm.js renders terminal in browser, works on mobile

---

## License

MIT
