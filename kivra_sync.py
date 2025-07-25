#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import os
import logging
import argparse
import base64

from __version__ import __version__
from kivra.auth import KivraAuth
from kivra.api import KivraApiClient
from kivra.receipts import ReceiptFetcher
from kivra.letters import LetterFetcher
from storage.filesystem import FileSystemStoreProvider
from interaction.local import LocalInteractionProvider
from interaction.ntfy import NtfyInteractionProvider

def fetch_documents(args, interaction_provider, document_store, temp_dir):
    """
    Fetch documents from Kivra.
    
    Args:
        args: Command line arguments
        interaction_provider: Interaction provider to use
        document_store: Document storage provider to use
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
        
        # Fetch receipts if enabled
        if args.fetch_receipts:
            receipt_fetcher = ReceiptFetcher(api_client, document_store)
            receipt_stats = receipt_fetcher.fetch_receipts(max_count=None if args.max_receipts == 0 else args.max_receipts)
            stats.update(receipt_stats)
        
        # Fetch letters if enabled
        if args.fetch_letters:
            letter_fetcher = LetterFetcher(api_client, document_store)
            letter_stats = letter_fetcher.fetch_letters(max_count=None if args.max_letters == 0 else args.max_letters)
            stats.update(letter_stats)
        
        # Report completion
        interaction_provider.report_completion(stats)
        
        return 0
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
    parser.add_argument('ssn', help='Personal identity number (YYYYMMDDXXXX)')
    
    # Storage provider selection
    parser.add_argument('--storage-provider', choices=['filesystem', 'paperless'], default='filesystem',
                        help='Storage provider to use (default: filesystem)')
    parser.add_argument('--base-dir', help='Base directory for storing documents (default: script directory)')
    
    # Interaction provider selection
    parser.add_argument('--interaction-provider', choices=['local', 'ntfy'], default='local',
                        help='Interaction provider to use (default: local)')
    
    # ntfy provider options
    parser.add_argument('--ntfy-topic', help='ntfy topic to send notifications to')
    parser.add_argument('--ntfy-server', default='https://ntfy.sh', help='ntfy server URL (default: https://ntfy.sh)')
    parser.add_argument('--ntfy-user', help='ntfy username for authentication')
    parser.add_argument('--ntfy-pass', help='ntfy password for authentication')
    parser.add_argument('--trigger-message', default='run now', 
                        help='Message that triggers the script when using a listening interaction provider (default: "run now")')
    
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
    
    args = parser.parse_args()
    
    # Configuration
    FETCH_RECEIPTS = args.fetch_receipts
    FETCH_LETTERS = args.fetch_letters
    MAX_RECEIPTS = None if args.max_receipts == 0 else args.max_receipts
    MAX_LETTERS = None if args.max_letters == 0 else args.max_letters
    
    # Create temp directory for QR codes and other temporary files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    temp_dir = os.path.join(script_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Initialize the document storage provider
    if args.storage_provider == 'filesystem':
        # Use base_dir if provided, otherwise use script_dir
        base_dir = args.base_dir if args.base_dir else script_dir
        document_store = FileSystemStoreProvider(os.path.join(base_dir, args.ssn), dry_run=args.dry_run)
    elif args.storage_provider == 'paperless':
        # Check if required paperless options are provided
        if not args.paperless_url or not args.paperless_token:
            parser.error("--paperless-url and --paperless-token are required when using the paperless storage provider")
        
        from storage.paperless import PaperlessNgxStoreProvider
        tags = args.paperless_tags.split(',') if args.paperless_tags else None
        document_store = PaperlessNgxStoreProvider(
            api_url=args.paperless_url,
            api_token=args.paperless_token,
            tags=tags,
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
    
    # Check if the provider can listen
    if interaction_provider.can_listen:
        # Start listening
        print(f"Listening for triggers via {args.interaction_provider}...")
        interaction_provider.listen(lambda: fetch_documents(args, interaction_provider, document_store, temp_dir))
    else:
        # Execute immediately
        exit_code = fetch_documents(args, interaction_provider, document_store, temp_dir)
        sys.exit(exit_code)

if __name__ == "__main__":
    main()
