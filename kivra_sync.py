#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import os
import logging
import argparse
import base64
import copy
import re
import tempfile

from __version__ import __version__
from kivra.auth import KivraAuth
from kivra.api import KivraApiClient
from kivra.receipts import ReceiptFetcher
from kivra.letters import LetterFetcher
from storage.filesystem import FileSystemStoreProvider
from utils.helpers import clean_filename
from interaction.local import LocalInteractionProvider
from interaction.ntfy import NtfyInteractionProvider
from interaction.web import WebInteractionProvider

def select_business_accounts(api_client, args):
    """
    Select the business accounts (company/association inboxes) to sync.
    
    Args:
        api_client (KivraApiClient): API client for the logged in user
        args: Command line arguments
        
    Returns:
        list: Business inboxes to sync
    """
    inboxes = [inbox for inbox in api_client.get_inboxes() if inbox.get('type') != 'user']
    
    if args.business_accounts:
        wanted = [w.strip().lower() for w in args.business_accounts.split(',') if w.strip()]
        selected = [inbox for inbox in inboxes
                    if inbox.get('key', '').lower() in wanted or (inbox.get('name') or '').lower() in wanted]
        found = {inbox.get('key', '').lower() for inbox in selected} | {(inbox.get('name') or '').lower() for inbox in selected}
        for w in wanted:
            if w not in found:
                logging.warning(f"Business account '{w}' not found among accessible accounts")
        inboxes = selected
    
    print(f"Found {len(inboxes)} business account(s) to sync: {', '.join(inbox.get('name') or inbox.get('key') for inbox in inboxes) or 'none'}")
    return inboxes

def sync_account(api_client, document_store, args, fetch_receipts):
    """
    Fetch receipts and letters for a single Kivra inbox.
    
    Args:
        api_client (KivraApiClient): API client acting on the inbox
        document_store: Document storage provider for the inbox
        args: Command line arguments
        fetch_receipts (bool): Whether to fetch receipts (only available for the personal inbox)
        
    Returns:
        dict: Statistics for the inbox
    """
    stats = {}
    
    # Fetch receipts if enabled
    if fetch_receipts:
        receipt_fetcher = ReceiptFetcher(api_client, document_store)
        stats.update(receipt_fetcher.fetch_receipts(max_count=None if args.max_receipts == 0 else args.max_receipts))
    
    # Fetch letters if enabled
    if args.fetch_letters:
        letter_fetcher = LetterFetcher(api_client, document_store)
        stats.update(letter_fetcher.fetch_letters(max_count=None if args.max_letters == 0 else args.max_letters))
    
    return stats

ACCOUNT_MODES = ('personal', 'business', 'both')

def normalize_ssn(ssn):
    """
    Normalize a personal identity number to YYYYMMDDXXXX.
    
    Args:
        ssn (str): Personal identity number, optionally with a dash or spaces
        
    Returns:
        str: The normalized number, or None if it is not 12 digits
    """
    ssn = re.sub(r'[\s-]', '', ssn or '')
    return ssn if re.fullmatch(r'\d{12}', ssn) else None

def apply_run_options(args, options):
    """
    Return a copy of args with per-run options (e.g. from the web UI) applied.
    
    Args:
        args: Command line arguments
        options (dict): Optional 'ssn' and 'account_mode' ('personal', 'business' or 'both')
        
    Returns:
        Namespace: Arguments for this run
        
    Raises:
        ValueError: If an option is invalid or no personal identity number is available
    """
    run_args = copy.copy(args)
    options = options or {}
    
    if options.get('ssn'):
        run_args.ssn = normalize_ssn(options['ssn'])
        if not run_args.ssn:
            raise ValueError("Personal identity number must be 12 digits (YYYYMMDDXXXX)")
    if not run_args.ssn:
        raise ValueError("No personal identity number configured")
    
    mode = options.get('account_mode')
    if mode:
        if mode not in ACCOUNT_MODES:
            raise ValueError(f"Invalid account mode: {mode}")
        run_args.include_business = mode in ('business', 'both')
        run_args.business_only = mode == 'business'
    
    return run_args

def fetch_documents(args, interaction_provider, create_document_store, temp_dir):
    """
    Fetch documents from Kivra.
    
    Args:
        args: Command line arguments
        interaction_provider: Interaction provider to use
        create_document_store: Function returning a document storage provider for an
            account, called with the personal identity number and None for the personal
            inbox or a business inbox dict
        temp_dir: Temporary directory for QR codes and other files
        
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    try:
        # Authenticate with Kivra
        auth = KivraAuth(temp_dir, interaction_provider)
        token_info = auth.authenticate(args.ssn)
        
        # Extract tokens
        access_token = token_info['access_token']
        actor_key = token_info['actor_key']
        
        # Initialize API client
        api_client = KivraApiClient(access_token, actor_key)
        
        # Initialize statistics
        stats = {
            'receipts_total': 0,
            'receipts_fetched': 0,
            'receipts_stored': 0,
            'letters_total': 0,
            'letters_fetched': 0,
            'letters_stored': 0
        }
        
        def add_stats(account_stats):
            for key, value in account_stats.items():
                stats[key] = stats.get(key, 0) + value
        
        # Sync the personal inbox
        if not args.business_only:
            add_stats(sync_account(api_client, create_document_store(args.ssn, None), args, args.fetch_receipts))
        
        # Sync business accounts if enabled
        exit_code = 0
        if args.include_business:
            try:
                business_inboxes = select_business_accounts(api_client, args)
            except Exception as e:
                logging.error(f"Error listing business accounts: {str(e)}")
                business_inboxes = []
                exit_code = 1
            for inbox in business_inboxes:
                name = inbox.get('name') or inbox.get('key')
                print(f"\nSyncing business account: {name}")
                try:
                    business_client = api_client.for_actor(inbox['key'], 'company')
                    # Receipts are only available for the personal inbox
                    add_stats(sync_account(business_client, create_document_store(args.ssn, inbox), args, fetch_receipts=False))
                except Exception as e:
                    logging.error(f"Error syncing business account {name}: {str(e)}")
                    exit_code = 1
        
        # Report completion
        interaction_provider.report_completion(stats)
        
        return exit_code
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return 1

def main():
    """Main function to fetch receipts and letters from Kivra."""
    
    # Configure logging
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description=f'Fetch receipts and letters from Kivra. (version {__version__})',
        prog='kivra-sync'
    )
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('ssn', nargs='?',
                        help='Personal identity number (YYYYMMDDXXXX). Optional with the web interaction provider, '
                             'where it can be entered in the browser instead')
    
    # Storage provider selection
    parser.add_argument('--storage-provider', choices=['filesystem', 'paperless'], default='filesystem',
                        help='Storage provider to use (default: filesystem)')
    parser.add_argument('--base-dir', help='Base directory for storing documents (default: script directory)')
    
    # Interaction provider selection
    parser.add_argument('--interaction-provider', choices=['local', 'ntfy', 'web'], default='local',
                        help='Interaction provider to use (default: local)')
    
    # ntfy provider options
    parser.add_argument('--ntfy-topic', help='ntfy topic to send notifications to')
    parser.add_argument('--ntfy-server', default='https://ntfy.sh', help='ntfy server URL (default: https://ntfy.sh)')
    parser.add_argument('--ntfy-user', help='ntfy username for authentication')
    parser.add_argument('--ntfy-pass', help='ntfy password for authentication')
    parser.add_argument('--trigger-message', default='run now', 
                        help='Message that triggers the script when using a listening interaction provider (default: "run now")')
    
    # Web provider options
    parser.add_argument('--web-port', type=int, default=8080, 
                        help='Port for web interface (default: 8080)')
    parser.add_argument('--web-host', default='0.0.0.0',
                        help='Host for web interface (default: 0.0.0.0)')
    
    # Paperless provider options
    parser.add_argument('--paperless-url', help='Paperless API URL (e.g., http://localhost:8000/api)')
    parser.add_argument('--paperless-token', help='Paperless API token')
    parser.add_argument('--paperless-tags', help='Comma-separated list of tags to apply to all documents')
    parser.add_argument('--dry-run', action='store_true', help='Do not actually store documents, just simulate')
    
    # Fetch options
    parser.add_argument('--fetch-receipts', action='store_true', default=True, help='Fetch receipts')
    parser.add_argument('--no-fetch-receipts', action='store_false', dest='fetch_receipts', help='Do not fetch receipts')
    parser.add_argument('--fetch-letters', action='store_true', default=True, help='Fetch letters')
    parser.add_argument('--no-fetch-letters', action='store_false', dest='fetch_letters', help='Do not fetch letters')
    parser.add_argument('--max-receipts', type=int, default=0, help='Maximum number of receipts to fetch (default: 0, 0 for unlimited)')
    parser.add_argument('--max-letters', type=int, default=0, help='Maximum number of letters to fetch (default: 0, 0 for unlimited)')
    
    # Business account options
    parser.add_argument('--include-business', action='store_true',
                        help='Also sync letters from business accounts (company/association inboxes) you have access to')
    parser.add_argument('--business-accounts',
                        help='Comma-separated list of business account names or keys to sync (default: all, implies --include-business)')
    parser.add_argument('--business-only', action='store_true',
                        help='Only sync business accounts, skip the personal inbox (implies --include-business)')
    
    args = parser.parse_args()
    if args.business_accounts or args.business_only:
        args.include_business = True
    if args.ssn:
        args.ssn = normalize_ssn(args.ssn)
        if not args.ssn:
            parser.error("ssn must be 12 digits (YYYYMMDDXXXX)")
    elif args.interaction_provider != 'web':
        parser.error("ssn is required unless using the web interaction provider")
    
    # Create temp directory for QR codes and other temporary files
    # Prefer env overrides and OS temp; avoid writing into read-only installs
    script_dir = os.path.dirname(os.path.abspath(__file__))
    temp_base = (
        os.environ.get("XDG_RUNTIME_DIR")
        or tempfile.gettempdir()
    )
    temp_dir = os.path.join(temp_base, "kivra-sync")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Initialize the document storage provider
    if args.storage_provider == 'filesystem':
        # Use base_dir if provided, otherwise use env or current directory
        base_dir = (
            args.base_dir
            if args.base_dir
            else os.getcwd()
        )
        def create_document_store(ssn, business_inbox):
            personal_dir = os.path.join(base_dir, ssn)
            if business_inbox is None:
                return FileSystemStoreProvider(personal_dir, dry_run=args.dry_run)
            # Business accounts are stored under <base-dir>/<ssn>/Business/<name>_<key>
            account_dir = clean_filename(f"{business_inbox.get('name') or 'business'}_{business_inbox['key']}")
            return FileSystemStoreProvider(os.path.join(personal_dir, 'Business', account_dir), dry_run=args.dry_run)
    elif args.storage_provider == 'paperless':
        # Check if required paperless options are provided
        if not args.paperless_url or not args.paperless_token:
            parser.error("--paperless-url and --paperless-token are required when using the paperless storage provider")
        
        from storage.paperless import PaperlessNgxStoreProvider
        tags = args.paperless_tags.split(',') if args.paperless_tags else []
        
        def create_document_store(ssn, business_inbox):
            account_tags = list(tags)
            # Tag business account documents with the account name
            if business_inbox is not None:
                account_tags.append(business_inbox.get('name') or business_inbox['key'])
            return PaperlessNgxStoreProvider(
                api_url=args.paperless_url,
                api_token=args.paperless_token,
                tags=account_tags or None,
                dry_run=args.dry_run
            )
    
    # Initialize the interaction provider
    if args.interaction_provider == 'local':
        interaction_provider = LocalInteractionProvider()
    elif args.interaction_provider == 'ntfy':
        if not args.ntfy_topic:
            parser.error("--ntfy-topic is required when using the ntfy interaction provider")
        
        # Set up authentication headers if provided
        ntfy_headers = {}
        if args.ntfy_user and args.ntfy_pass:
            auth_str = f"{args.ntfy_user}:{args.ntfy_pass}"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            ntfy_headers["Authorization"] = f"Basic {encoded_auth}"
        
        interaction_provider = NtfyInteractionProvider(
            topic=args.ntfy_topic,
            server=args.ntfy_server,
            headers=ntfy_headers,
            trigger_message=args.trigger_message
        )
    elif args.interaction_provider == 'web':
        if args.business_only:
            default_account_mode = 'business'
        elif args.include_business:
            default_account_mode = 'both'
        else:
            default_account_mode = 'personal'
        interaction_provider = WebInteractionProvider(
            port=args.web_port,
            host=args.web_host,
            ssn_configured=bool(args.ssn),
            default_account_mode=default_account_mode
        )
    
    # Check if the provider can listen
    if interaction_provider.can_listen:
        # Start listening
        print(f"Listening for triggers via {args.interaction_provider}...")
        # Listening providers may pass per-run options (personal identity number, account mode)
        def run(options=None):
            return fetch_documents(apply_run_options(args, options), interaction_provider, create_document_store, temp_dir)
        interaction_provider.listen(run, temp_dir=temp_dir)
    else:
        # Execute immediately
        exit_code = fetch_documents(args, interaction_provider, create_document_store, temp_dir)
        sys.exit(exit_code)

if __name__ == "__main__":
    main()
