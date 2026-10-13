#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
from utils.helpers import format_date
from kivra.models import LETTERS_QUERY, KivraLetter

class LetterFetcher:
    """Class for fetching letters from Kivra."""
    
    def __init__(self, api_client, document_store):
        """
        Initialize the letter fetcher.
        
        Args:
            api_client (KivraApiClient): Kivra API client
            document_store (DocumentStoreProvider): Document store provider
        """
        self.api_client = api_client
        self.document_store = document_store
        self.use_graphql_details = False
    
    def fetch_letters(self, max_count=None):
        """
        Fetch letters from Kivra.
        
        Args:
            max_count (int, optional): Maximum number of letters to fetch
            
        Returns:
            dict: Statistics about fetched letters
        """
        print("\nFetching letters...")
        
        try:
            # Fetch all letters with pagination
            all_letters = []
            after = None
            
            while True:
                variables = {
                    "after": after,
                    "filter": "inbox",
                    "senderKey": None,
                    "take": 100  # Increase per-page count for fewer requests
                }
                
                data = self.api_client.graphql_query("ContentList", LETTERS_QUERY, variables)
                
                page_content = data.get('data', {}).get('contents', {})
                page_letters = page_content.get('list', [])
                all_letters.extend(page_letters)
                
                exists_more = page_content.get('existsMore', False)
                if not exists_more or not page_letters:
                    break
                    
                # Use the last letter's key as 'after' for the next page
                after = page_letters[-1]['key']
                print(f"Fetched {len(all_letters)} letters of {page_content.get('total', '?')}...")
            
            total_letters = len(all_letters)
            print(f"\nFound a total of {total_letters} letters")
            
            # Report letter list for storage
            self.document_store.report_listing('letters', all_letters)
            
            # Limit the number of letters if max_count is set
            if max_count is not None:
                print(f"\nLimiting to {max_count} letters (of {len(all_letters)} available)")
                all_letters = all_letters[:max_count]
            
            # Add a counter for stored letters
            letters_stored = 0
            
            # Process each letter
            print("\nFetching PDF and details for each letter...")
            for letter_data in all_letters:
                # Pass the counter to _process_letter and get the updated value
                letters_stored = self._process_letter(letter_data, letters_stored)
                
            print("\nFinished processing all letters!")
            
            # Return statistics
            return {
                'letters_total': total_letters,
                'letters_fetched': len(all_letters[:max_count] if max_count is not None else all_letters),
                'letters_stored': letters_stored
            }
            
        except Exception as e:
            logging.error(f"Error fetching letters: {str(e)}")
            raise
    
    def _process_letter(self, letter_data, letters_stored):
        """
        Process a single letter.
        
        Args:
            letter_data (dict): Letter data from the list
            letters_stored (int): Counter for stored letters
            
        Returns:
            int: Updated counter for stored letters
        """
        letter_key = letter_data.get('key')
        if not letter_key:
            logging.warning("Letter missing key, skipping")
            return
        
        # Create metadata based on date and sender
        date = format_date(letter_data.get('receivedAt', 'unknown_date'))
        sender = letter_data.get('sender', {}).get('name', 'unknown_sender')
        
        # Create letter object
        letter = KivraLetter(letter_key, date, sender)
        
        # Check if JSON metadata already exists
        json_metadata = letter.get_metadata()
        if self.document_store.exists(json_metadata):
            print(f"Skipping letter {letter_key} - already fetched")
            return letters_stored
        
        print(f"\nProcessing letter: {letter_key}")
        
        try:
            # 1. Fetch detailed letter information
            content_data = self._get_content_details(letter_key)
            
            # Combine metadata from the list with detailed information
            letter_data = {**letter_data, "content": content_data}
            
            # 2. Store letter metadata
            self.document_store.report_metadata(letter_data, json_metadata)
            print(f"Saved metadata for letter {letter_key}")
            
            # 3. Process letter parts
            parts_stored = self._process_letter_parts(letter, content_data)
            if parts_stored > 0:
                letters_stored += 1
            
        except Exception as e:
            logging.error(f"Error processing letter {letter_key}: {str(e)}")
        
        return letters_stored
    
    def _get_content_details(self, letter_key):
        """
        Get letter details, falling back to the actor-scoped GraphQL API for
        business accounts if the REST endpoint does not grant access.
        
        Args:
            letter_key (str): Letter key
            
        Returns:
            dict: Letter content data
        """
        if self.use_graphql_details:
            return self.api_client.get_content_details_v2(letter_key)
        try:
            return self.api_client.get_content_details(letter_key)
        except Exception:
            if self.api_client.actor_type == 'user':
                raise
            logging.info("Falling back to GraphQL content details for this business account")
            self.use_graphql_details = True
            return self.api_client.get_content_details_v2(letter_key)
    
    def _process_letter_parts(self, letter, content_data):
        """
        Process the parts of a letter.
        
        Args:
            letter (KivraLetter): Letter object
            content_data (dict): Letter content data
            
        Returns:
            int: Number of parts stored
        """
        parts = content_data.get('parts', [])
        if not parts:
            logging.error(f"Letter {letter.key} has no parts")
            return 0
        
        parts_stored = 0
        
        for part_index, part in enumerate(parts):
            content_type = part.get('content_type')
            
            # Create a letter object for this part
            part_letter = KivraLetter(
                letter.key, 
                letter.date, 
                letter.sender_name, 
                part_index=part_index if len(parts) > 1 else None
            )
            
            if content_type == 'text/plain':
                # Save text/plain content
                text_content = part.get('body') if 'body' in part else self._get_part_text(part)
                text_metadata = part_letter.get_metadata(content_type='text/plain')
                
                if self.document_store.store(text_content, text_metadata):
                    parts_stored += 1
                    print(f"Saved text/plain for letter {letter.key}")
                
            elif content_type == 'text/html':
                # Save HTML content
                html_content = part.get('body') if 'body' in part else self._get_part_text(part)
                html_metadata = part_letter.get_metadata(content_type='text/html')
                
                if self.document_store.store(html_content, html_metadata):
                    parts_stored += 1
                    print(f"Saved HTML for letter {letter.key}")
                
            elif content_type == 'application/pdf':
                # Fetch and save PDF
                file_key = part.get('key')
                file_path = part.get('path')
                if not file_key and not file_path:
                    logging.warning(f"PDF part in letter {letter.key} missing key")
                    continue
                
                try:
                    # Fetch PDF content
                    if file_key:
                        pdf_content = self.api_client.get_content_file(letter.key, file_key)
                    else:
                        pdf_content = self.api_client.get_core_path(file_path)
                    
                    # Store PDF
                    pdf_metadata = part_letter.get_metadata(content_type='application/pdf')
                    if self.document_store.store(pdf_content, pdf_metadata):
                        parts_stored += 1
                        print(f"Saved PDF for letter {letter.key}")
                    
                except Exception as e:
                    logging.error(f"Error fetching PDF for letter {letter.key}, file {file_key}: {str(e)}")
                    raise
            else:
                logging.warning(f"Unknown content type in letter {letter.key}: {content_type}")
        
        return parts_stored
    
    def _get_part_text(self, part):
        """
        Fetch the text body of a letter part that only has a path (GraphQL fallback).
        
        Args:
            part (dict): Letter part
            
        Returns:
            str: Part body
        """
        if not part.get('path'):
            return ''
        return self.api_client.get_core_path(part['path']).decode('utf-8', errors='replace')
