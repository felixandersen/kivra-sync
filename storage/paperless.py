#!/usr/bin/python3
# -*- coding: utf-8 -*-

import requests
import json
import logging
import re
from datetime import datetime
from storage.base import DocumentStoreProvider

class PaperlessNgxStoreProvider(DocumentStoreProvider):
    """Storage provider that stores documents in paperless-ngx."""
    
    def __init__(self, api_url, api_token, tags=None, dry_run=False):
        """
        Initialize with paperless-ngx API details.
        
        Args:
            api_url (str): Base URL for the paperless-ngx API (e.g., 'http://localhost:8000/api')
            api_token (str): API token for authentication
            tags (list, optional): List of tag names to apply to all documents
            dry_run (bool, optional): If True, don't actually store documents, just simulate
        """
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.tags = tags or []
        self.dry_run = dry_run
        
        # Set up session with authentication
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {api_token}',
            'Accept': 'application/json'
        })
        
        # Get tag IDs if tags are provided
        self.tag_ids = self._get_tag_ids(self.tags) if self.tags else []
    
    def _get_tag_ids(self, tag_names):
        """
        Get tag IDs for the given tag names, creating them if they don't exist.
        
        Args:
            tag_names (list): List of tag names
            
        Returns:
            list: List of tag IDs
        """
        tag_ids = []
        
        logging.info(f"Processing tags: {tag_names}")
        
        for tag_name in tag_names:
            # Log the tag we're looking for
            logging.info(f"Looking for tag: {tag_name}")
            
            # Check if tag exists - use case-insensitive exact match
            response = self.session.get(
                f"{self.api_url}/tags/?name__iexact={tag_name}"
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['count'] > 0:
                    tag_id = data['results'][0]['id']
                    tag_ids.append(tag_id)
                    logging.info(f"Found existing tag '{tag_name}' with ID {tag_id}")
                    continue
            
            # Create new tag if not found
            response = self.session.post(
                f"{self.api_url}/tags/",
                json={'name': tag_name},
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code in [200, 201]:
                tag_id = response.json()['id']
                tag_ids.append(tag_id)
                logging.info(f"Created new tag '{tag_name}' with ID {tag_id}")
            else:
                logging.warning(f"Failed to create tag '{tag_name}': {response.status_code}, Response: {response.text}")
        
        logging.info(f"Using tag IDs: {tag_ids}")
        return tag_ids
    
    def _get_correspondent_id(self, sender_name):
        """
        Get correspondent ID for a sender name, creating one if it doesn't exist.
        
        Args:
            sender_name (str): Name of the sender/correspondent
            
        Returns:
            int: Correspondent ID
        """
        if not sender_name or sender_name.lower() in ['unknown store', 'unknown sender']:
            logging.warning(f"Invalid correspondent name: {sender_name}, skipping correspondent")
            return None
            
        logging.info(f"Looking for correspondent: {sender_name}")
        
        # First check if correspondent exists - use exact match
        try:
            # URL encode the name for the query
            import urllib.parse
            encoded_name = urllib.parse.quote(sender_name)
            
            # First try exact match
            response = self.session.get(
                f"{self.api_url}/correspondents/?name__iexact={encoded_name}"
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['count'] > 0:
                    correspondent_id = data['results'][0]['id']
                    logging.info(f"Found existing correspondent '{sender_name}' with ID {correspondent_id}")
                    return correspondent_id
                    
            # If no exact match, try contains match
            response = self.session.get(
                f"{self.api_url}/correspondents/?name__icontains={encoded_name}"
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['count'] > 0:
                    correspondent_id = data['results'][0]['id']
                    logging.info(f"Found similar correspondent '{data['results'][0]['name']}' with ID {correspondent_id}")
                    return correspondent_id
        except Exception as e:
            logging.error(f"Error searching for correspondent: {str(e)}")
        
        # Create new correspondent if not found
        try:
            logging.info(f"Creating new correspondent: {sender_name}")
            response = self.session.post(
                f"{self.api_url}/correspondents/",
                json={'name': sender_name, 'matching_algorithm': 6},
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code in [200, 201]:
                correspondent_id = response.json()['id']
                logging.info(f"Created new correspondent '{sender_name}' with ID {correspondent_id}")
                return correspondent_id
            else:
                logging.warning(f"Failed to create correspondent for '{sender_name}': {response.status_code}, Response: {response.text}")
        except Exception as e:
            logging.error(f"Error creating correspondent: {str(e)}")
        
        # Return None if creation fails
        logging.warning("Failed to create correspondent, correspondent will be skipped")
        return None
    
    def _get_document_type_id(self, doc_type):
        """
        Get document type ID based on metadata.
        
        Args:
            doc_type (str): Type of document ('receipt' or 'letter')
            
        Returns:
            int: Document type ID
        """
        # Map our document types to paperless document types
        # This assumes you've created these document types in paperless-ngx
        type_mapping = {
            'receipt': 'Receipt',
            'letter': 'Letter'
        }
        
        paperless_type = type_mapping.get(doc_type, 'Document')
        
        # Check if document type exists - use case-insensitive exact match
        response = self.session.get(
            f"{self.api_url}/document_types/?name__iexact={paperless_type}"
        )
        
        if response.status_code == 200:
            data = response.json()
            if data['count'] > 0:
                return data['results'][0]['id']
        
        # Create new document type if not found
        response = self.session.post(
            f"{self.api_url}/document_types/",
            json={'name': paperless_type},
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code in [200, 201]:
            return response.json()['id']
        
        # Return None if creation fails
        logging.warning(f"Failed to get/create document type for {doc_type}, document type will be skipped")
        return None
    
    def report_listing(self, doc_type, listing):
        """
        Report a list of documents for logging or other purposes.
        
        Args:
            doc_type (str): Type of document (receipt/letter)
            listing (dict): Document listing data
        """
        # For paperless, we don't need to store the listing separately
        # as documents are indexed by the paperless system
        pass
    
    def report_metadata(self, data, metadata):
        """
        Report document metadata.
        
        Args:
            data (dict): The document metadata as a dictionary
            metadata (dict): Document metadata
            
        Returns:
            bool: True if successful, False otherwise
        """
        # For paperless, we don't need to store the metadata separately
        # as we're only interested in the actual documents
        return True
    
    def _format_date_for_paperless(self, date_str):
        """
        Format a date string for Paperless in ISO format with timezone.
        
        Args:
            date_str (str): Date string in YYYY-MM-DD format
            
        Returns:
            str: ISO formatted date with timezone
        """
        try:
            # Check if date is in YYYY-MM-DD format
            if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                # Convert to ISO format with time and timezone
                return f"{date_str}T00:00:00Z"
            else:
                logging.warning(f"Date format not recognized: {date_str}, using current date")
                return datetime.utcnow().strftime('%Y-%m-%dT00:00:00Z')
        except Exception as e:
            logging.error(f"Error formatting date: {str(e)}")
            return datetime.utcnow().strftime('%Y-%m-%dT00:00:00Z')
    
    def exists(self, metadata):
        """
        Check if document exists by searching the filename.
        
        Args:
            metadata (dict): Document metadata
            
        Returns:
            bool: True if exists, False otherwise
        """
        try:
            # Extract key identifiers from metadata
            doc_type = metadata.get('type')
            doc_key = metadata.get('key')
            
            if not doc_key:
                return False
            
            # Build query parameters with more specific criteria
            query_params = {
                'original_filename__icontains': doc_key
            }
            
            logging.info(f"Checking if document exists with filename params: {query_params}")
            
            # Search for document with the specific criteria
            response = self.session.get(
                f"{self.api_url}/documents/",
                params=query_params
            )
            
            if response.status_code != 200:
                logging.error(f"Failed to search documents by filename: {response.status_code}, Response: {response.text}")
                return False
            
            data = response.json()

            exists = data['count'] > 0
            
            if exists:
                logging.info(f"Document with key {doc_key} already exists in Paperless (by filename)")
            else:
                logging.info(f"Document with key {doc_key} does not exist in Paperless (by filename)")
                
            return exists
            
        except Exception as e:
            logging.error(f"Error checking if document exists in paperless-ngx: {str(e)}")
            return False
    
    def store(self, data, metadata):
        """
        Store document in paperless-ngx.
        
        Args:
            data (bytes or dict): The document content
            metadata (dict): Document metadata
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            
            # Only store PDF and text documents
            content_type = metadata.get('content_type', '')
            if content_type not in ['application/pdf', 'text/plain', 'text/html']:
                return True
            
            doc_type = metadata.get('type')
            date = metadata.get('date', 'unknown_date')
            
            # Get correspondent name based on document type
            if doc_type == 'receipt':
                correspondent_name = metadata.get('store_name', 'Unknown Store')
                # Clean up the store name if needed
                if correspondent_name and '/' in correspondent_name:
                    correspondent_name = correspondent_name.split('/')[0].strip()
            else:  # letter
                correspondent_name = metadata.get('sender_name', 'Unknown Sender')
            
            logging.info(f"Using correspondent name: {correspondent_name}")
            
            # Get correspondent ID
            correspondent_id = self._get_correspondent_id(correspondent_name)
            
            # Get document type ID
            document_type_id = self._get_document_type_id(doc_type)
            
            # Create filename
            key = metadata.get('key', 'unknown')
            part_index = metadata.get('part_index')
            part_suffix = f"_part{part_index}" if part_index is not None else ""
            
            if doc_type == 'receipt':
                filename = f"{date}_{correspondent_name}_{key}{part_suffix}"
            else:  # letter
                filename = f"{date}_{correspondent_name}_{key}{part_suffix}"
            
            # Prepare file for upload
            if isinstance(data, dict):
                # Convert JSON to text
                file_data = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
                file_content_type = 'application/json'
            elif isinstance(data, str):
                # For HTML content, we need to convert it to PDF first
                if content_type == 'text/html':
                    # Import here to avoid circular imports
                    from utils.pdf import html_to_pdf
                    pdf_data = html_to_pdf(data)
                    if pdf_data:
                        file_data = pdf_data
                        file_content_type = 'application/pdf'
                    else:
                        # Fallback to text if conversion fails
                        file_data = data.encode('utf-8')
                        file_content_type = 'text/plain'
                elif content_type == 'text/plain':
                    # Convert plain text to HTML with template, then to PDF
                    from utils.pdf import text_to_html, html_to_pdf
                    
                    # Create a title from the filename
                    title = filename
                    
                    # Convert text to HTML with template
                    html_content = text_to_html(data, title=title)
                    
                    # Convert HTML to PDF
                    pdf_data = html_to_pdf(html_content)
                    
                    if pdf_data:
                        file_data = pdf_data
                        file_content_type = 'application/pdf'
                        file_extension = 'pdf'
                    else:
                        # Fallback to original text if conversion fails
                        file_data = data.encode('utf-8')
                        file_content_type = 'text/plain'
                else:
                    # Other text formats
                    file_data = data.encode('utf-8')
                    file_content_type = 'text/plain'
            else:
                # Assume bytes (PDF)
                file_data = data
                file_content_type = content_type
            
            # Prepare file upload
            file_extension = 'pdf' if file_content_type == 'application/pdf' else 'txt'
            files = {
                'document': (f"{filename}.{file_extension}", file_data, file_content_type)
            }
            
            # Prepare metadata
            document_metadata = {
                'title': filename,
                'created': self._format_date_for_paperless(date)
            }
            
            # Only add correspondent and document_type if they are not None
            if correspondent_id is not None:
                document_metadata['correspondent'] = correspondent_id
                
            if document_type_id is not None:
                document_metadata['document_type'] = document_type_id
            
            # Add tags if available
            if self.tag_ids:
                document_metadata['tags'] = self.tag_ids
                logging.info(f"Adding tags to document: {self.tag_ids}")
            
            # Check if this is a dry run
            if self.dry_run:
                logging.info(f"DRY RUN: Would upload document to paperless-ngx: {filename}")
                return True
                
            # Upload document without custom fields
            response = self.session.post(
                f"{self.api_url}/documents/post_document/",
                files=files,
                data=document_metadata
            )
            
            if response.status_code not in [200, 201, 202]:
                logging.error(f"Failed to upload document to paperless-ngx: {response.status_code}")
                logging.error(f"Response: {response.text}")
                return False
            
            logging.info(f"Successfully uploaded document to paperless-ngx: {filename}")
            
            # Document was uploaded successfully
            
            return True
            
        except Exception as e:
            logging.error(f"Error storing document in paperless-ngx: {str(e)}")
            return False
