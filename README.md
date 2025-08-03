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
- **Multiple Interaction Modes**: Run interactively in your terminal or set up a "headless" mode that listens for triggers and sends QR codes via ntfy.sh

## Quick Start

This will:
1. Authenticate with Kivra using BankID
2. Fetch receipts and letters
3. Store them in the filesystem

### Option 1: Using Python

```bash
# Install system dependencies (Debian/Ubuntu)
apt-get install weasyprint

# Install Python dependencies
pip install -r requirements.txt

# Run the script
python kivra_sync.py YYYYMMDDXXXX
```

### Option 2: Using Docker

```bash
# Edit docker-compose.example.yml to set your configuration
# Then run:
docker compose -f docker-compose.example.yml up
```

Note: this will not work with the default `local` interaction provider since there is currently no way for the provider to show the QR code required for login.

## Advanced Configuration

### Storage Providers

#### Filesystem Storage (Default)

Documents are stored in the local filesystem:

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

#### Local Interaction (Default)

Displays QR codes locally and reports to the console:

```bash
python kivra_sync.py YYYYMMDDXXXX --interaction-provider local
```

#### ntfy Interaction

Sends QR codes and reports via ntfy.sh, with optional listening mode:

```bash
python kivra_sync.py YYYYMMDDXXXX --interaction-provider ntfy --ntfy-topic your-topic
```

To trigger the script in listening mode, send the trigger message to the ntfy topic:

```bash
curl -d "run now" ntfy.sh/your-topic
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
| `--base-dir DIR` | Base directory for storing documents (default: script directory) |

### Paperless-specific Options
| Option | Description |
|--------|-------------|
| `--paperless-url URL` | Paperless API URL (required for paperless) |
| `--paperless-token TOKEN` | Paperless API token (required for paperless) |
| `--paperless-tags TAGS` | Comma-separated list of tags to apply to all documents |

### Interaction Options
| Option | Description |
|--------|-------------|
| `--interaction-provider {local,ntfy}` | Interaction provider to use (default: local) |
| `--ntfy-topic TOPIC` | ntfy topic to send notifications to (required for ntfy) |
| `--ntfy-server URL` | ntfy server URL (default: https://ntfy.sh) |
| `--ntfy-user USER` | ntfy username for authentication |
| `--ntfy-pass PASS` | ntfy password for authentication |
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
