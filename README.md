# Kivra sync

An automation tool that connects to Kivra (a Swedish digital mailbox service) to download and organize your digital receipts and letters, helping you maintain a local backup of your important documents.

This tool is originaly based on a script created here https://github.com/stefangorling/fetch-kivra, thanks Stefan! It has since gone through major changes and feature additions.

## Disclaimer

This project is not affiliated with Kivra in any way. It is an independent, open-source tool created by the community to help users download their documents from Kivra - a feature that is otherwise only available through manual clicks in their user interface.

We believe individuals should have easy access to their own data. Digital mailboxes like Kivra hold important documents on behalf of users, and the lack of an efficient export option makes it unnecessarily cumbersome for users to retrieve and back up their documents. This tool aims to bridge that gap.

Use it responsibly and at your own discretion.

## Key Features

- **Authentication**: Fetches and displays a QR code for authentication via BankID.
- **Flexible Storage**: Store documents locally on your filesystem or integrate with Paperless-ngx for advanced document management
- **Multiple Interaction Modes**: Scan the BankID QR code right in your terminal, or set up a "headless" mode that listens for triggers and shows QR codes via a web page or ntfy.sh

## Quick Start

This will:
1. Authenticate with Kivra using BankID
2. Fetch receipts and letters
3. Store them in the filesystem

### Option 1: Using Docker (recommended)

Build the image, then run it interactively. The BankID QR code is drawn directly in your terminal and refreshes until you scan it with the BankID app:

```bash
docker build -t kivra-sync .
docker run -it --rm -v "$(pwd)/data:/data" kivra-sync:latest YYYYMMDDXXXX --base-dir /data
```

Documents are saved to `./data` on your machine.

- `-it` is required, since the QR code is shown in the terminal.
- `--base-dir /data` makes the documents land in the mounted volume rather than inside the container.
- Before login, the terminal must be at least 60 columns × 32 rows. A typical compact QR and its status area need about 54 columns × 32 rows; larger payloads may require more space, which the error message will report.

### Option 2: Using Docker Compose (headless, web UI)

For a long-running setup without an interactive terminal, use the `web` interaction provider and open the QR code in your browser:

```bash
# Edit docker-compose.yml to set your configuration,
# especially "your-national-identification-number-here"
# Then run:
docker compose build && docker compose up
```

Then navigate to `http://localhost:8080` to trigger a sync and scan the QR code.

The supplied Compose setup has neither an interactive terminal for `terminal` nor a desktop image viewer for `local`, so it uses `web`. The `ntfy` provider is another option for headless runs.

### Option 3: Using Python

```bash
# Install system dependencies (Debian/Ubuntu)
apt-get install weasyprint

# Install Python dependencies
pip install -r requirements.txt

# Run the script
python kivra_sync.py YYYYMMDDXXXX
```

### Option 4: Using Nix (flake)

If you have Nix with flakes enabled:

```bash
# Run (uses the flake-provided environment)
nix run . -- --help

# Typical run, storing under ./data/<ssn>/
nix run . -- YYYYMMDDXXXX --base-dir ./data

# Run with the web interaction provider
nix run . -- YYYYMMDDXXXX --interaction-provider web --web-port 8080

# Build and run help on resulting executable
nix build && result/bin/kivra-sync --help 

# Dev shell with Python + deps + system libs
nix develop

```

## Advanced Configuration

### Storage Providers

#### Filesystem Storage (Default)

Documents are stored in the local filesystem. 

```bash
python kivra_sync.py YYYYMMDDXXXX --storage-provider filesystem --base-dir /path/to/store
```

#### Paperless-ngx Storage

Upload documents directly to Paperless-ngx:

```bash
python kivra_sync.py YYYYMMDDXXXX --storage-provider paperless \
  --paperless-url http://your-paperless-server:8000/api \
  --paperless-token your_paperless_api_token \
  --paperless-tags "kivra,receipts,automated"
```

### Interaction Providers

Interaction providers handle user interaction during authentication and report completion statistics.

#### Terminal Interaction (Default)

Draws the BankID QR code directly in the terminal and refreshes it on every poll, so the code you scan is always current. Reports progress to the console:

```bash
python kivra_sync.py YYYYMMDDXXXX --interaction-provider terminal
```

Uses Unicode half-block characters to fit two QR rows into each terminal line. Requires an interactive terminal (use `docker run -it` in Docker) with a font that supports these characters. Startup checks for at least 60 columns × 32 rows before authentication; the exact size is checked again when the QR payload arrives. A typical compact QR and its status area need about 54 columns × 32 rows, but larger payloads may require more. Windows console ANSI handling is initialized automatically. If output isn't a terminal, use the `web` or `ntfy` provider instead.

When upgrading, cron, systemd, and Docker runs without `-it` must select `web` or `ntfy` explicitly because `terminal` is now the default. If the window is resized too small during authentication, QR updates pause until it is enlarged again.

#### Web Interaction

Provides a web interface for triggering syncs and viewing results:

```bash
python kivra_sync.py YYYYMMDDXXXX --interaction-provider web --web-port 8080
```

Then navigate to `http://localhost:8080` in your browser to access the interface. Perfect for containerized deployments where GUI access is not available.

#### ntfy Interaction

Sends QR codes and reports via ntfy.sh, with optional listening mode:

```bash
python kivra_sync.py YYYYMMDDXXXX --interaction-provider ntfy --ntfy-topic your-topic
```

To trigger the script in listening mode, send the trigger message to the ntfy topic:

```bash
curl -d "run now" ntfy.sh/your-topic
```

#### Local Interaction (deprecated)

Opens the QR code image in your system's image viewer. It only shows a single static frame, which BankID may reject as stale ("QR-koden är ogiltig", RFA17). This provider will be removed in a future release; use `terminal` instead.

```bash
python kivra_sync.py YYYYMMDDXXXX --interaction-provider local
```

### Fetch Options

Customize which documents to fetch and how many:

```bash
# Fetch only letters
python kivra_sync.py YYYYMMDDXXXX --no-fetch-receipts

# Fetch only receipts
python kivra_sync.py YYYYMMDDXXXX --no-fetch-letters

# Fetch up to 10 letters and 5 receipts
python kivra_sync.py YYYYMMDDXXXX --max-letters 10 --max-receipts 5

# Fetch unlimited receipts
python kivra_sync.py YYYYMMDDXXXX --max-receipts 0
```

## Command-Line Reference

### General Options
| Option | Description |
|--------|-------------|
| `YYYYMMDDXXXX` (positional) | Personal identity number |
| `--dry-run` | Do not actually store documents, just simulate |

### Storage Options
| Option | Description |
|--------|-------------|
| `--storage-provider {filesystem,paperless}` | Storage provider to use (default: filesystem) |
| `--base-dir DIR` | Base directory for storing documents (default: current working directory) |

### Paperless-specific Options
| Option | Description |
|--------|-------------|
| `--paperless-url URL` | Paperless API URL (required for paperless) |
| `--paperless-token TOKEN` | Paperless API token (required for paperless) |
| `--paperless-tags TAGS` | Comma-separated list of tags to apply to all documents |

### Interaction Options
| Option | Description |
|--------|-------------|
| `--interaction-provider {terminal,web,ntfy,local}` | Interaction provider to use (default: terminal; `local` is deprecated) |
| `--ntfy-topic TOPIC` | ntfy topic to send notifications to (required for ntfy) |
| `--ntfy-server URL` | ntfy server URL (default: https://ntfy.sh) |
| `--ntfy-user USER` | ntfy username for authentication |
| `--ntfy-pass PASS` | ntfy password for authentication |
| `--web-port PORT` | Port for web interface (default: 8080) |
| `--web-host HOST` | Host for web interface (default: 0.0.0.0) |
| `--trigger-message MSG` | Message that triggers the script (default: "run now") |

### Document Fetch Options
| Option | Description |
|--------|-------------|
| `--fetch-receipts` / `--no-fetch-receipts` | Enable/disable receipt fetching (default: enabled) |
| `--fetch-letters` / `--no-fetch-letters` | Enable/disable letter fetching (default: enabled) |
| `--max-receipts N` | Maximum number of receipts to fetch (0 for unlimited) |
| `--max-letters N` | Maximum number of letters to fetch (0 for unlimited) |

## Project Structure

The code is organized into logical modules:
- `kivra/`: Kivra-specific functionality (auth, API, models)
- `storage/`: Document storage providers
- `interaction/`: User interaction providers
- `utils/`: Utility functions
