#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import json
import logging
from storage.base import DocumentStoreProvider
from utils.helpers import clean_filename
from utils.pdf import html_to_pdf

class FileSystemStoreProvider(DocumentStoreProvider):
    """Storage provider that stores documents in the file system."""
    
    def __init__(self, base_dir, dry_run=False):
        """
        Initialize with base directory for storage.
        
        Args:
            base_dir (str): Base directory path
            dry_run (bool, optional): If True, don't actually store documents, just simulate
        """
        self.base_dir = base_dir
        self.dry_run = dry_run
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create necessary directory structure."""
        os.makedirs(self.base_dir, exist_ok=True)
        
        # Create directories for receipts
        self.receipts_dir = os.path.join(self.base_dir, "Receipts")
        self.receipts_json_dir = os.path.join(self.receipts_dir, "json")
        os.makedirs(self.receipts_dir, exist_ok=True)
        os.makedirs(self.receipts_json_dir, exist_ok=True)
        
        # Create directories for letters
        self.letters_dir = os.path.join(self.base_dir, "Letters")
        self.letters_json_dir = os.path.join(self.letters_dir, "json")
        os.makedirs(self.letters_dir, exist_ok=True)
        os.makedirs(self.letters_json_dir, exist_ok=True)
    
    def _get_filepath(self, metadata):
        """
        Generate filepath based on metadata.
        
        Args:
            metadata (dict): Document metadata
            
        Returns:
            tuple: (directory_path, json_dir_path, filename_base)
        """
        doc_type = metadata.get('type')
        date = metadata.get('date', 'unknown_date')
        
        if doc_type == 'receipt':
            store_name = metadata.get('store_name', 'unknown_store')
            safe_store = clean_filename(store_name)
            
            # Create store-specific directories if they don't exist
            store_dir = os.path.join(self.receipts_dir, safe_store)
            store_json_dir = os.path.join(self.receipts_json_dir, safe_store)
            os.makedirs(store_dir, exist_ok=True)
            os.makedirs(store_json_dir, exist_ok=True)
            
            filename_base = f"{date}_{safe_store}_{metadata.get('key')}"
            return store_dir, store_json_dir, filename_base
            
        elif doc_type == 'letter':
            sender_name = metadata.get('sender_name', 'unknown_sender')
            safe_sender = clean_filename(sender_name)
            
            # Create sender-specific directories if they don't exist
            sender_dir = os.path.join(self.letters_dir, safe_sender)
            sender_json_dir = os.path.join(self.letters_json_dir, safe_sender)
            os.makedirs(sender_dir, exist_ok=True)
            os.makedirs(sender_json_dir, exist_ok=True)
            
            filename_base = f"{date}_{safe_sender}_{metadata.get('key')}"
            
            # Add part index if specified
            if metadata.get('part_index') is not None:
                filename_base = f"{filename_base}_part{metadata.get('part_index')}"
                
            return sender_dir, sender_json_dir, filename_base
        
        else:
            raise ValueError(f"Unknown document type: {doc_type}")
    
    def report_listing(self, doc_type, listing):
        """
        Report a list of documents for logging or other purposes.
        
        Args:
            doc_type (str): Type of document (receipt/letter)
            listing (dict): Document listing data
        """
        try:
            # Store listing as JSON
            if doc_type == 'receipts':
                store_json_dir = os.path.join(self.receipts_json_dir, 'receipts.json')
            elif doc_type == 'letters':
                store_json_dir = os.path.join(self.letters_json_dir, 'letters.json')

            with open(store_json_dir, 'w', encoding='utf-8') as f:
                json.dump(listing, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Error storing document listing: {str(e)}")

    def exists(self, metadata):
        """
        Check if document already exists based on metadata.
        
        Args:
            metadata (dict): Document metadata
            
        Returns:
            bool: True if exists, False otherwise
        """
        try:
            file_dir, json_dir, filename_base = self._get_filepath(metadata)
            
            # For JSON metadata check
            if metadata.get('content_type') == 'application/json':
                json_path = os.path.join(json_dir, f"{filename_base}.json")
                return os.path.exists(json_path)
            
            # For content files check
            content_type = metadata.get('content_type', '')
            if content_type == 'application/pdf':
                file_path = os.path.join(file_dir, f"{filename_base}.pdf")
                return os.path.exists(file_path)
            elif content_type == 'text/plain':
                file_path = os.path.join(file_dir, f"{filename_base}.txt")
                return os.path.exists(file_path)
            elif content_type == 'text/html':
                file_path = os.path.join(file_dir, f"{filename_base}_html.pdf")
                return os.path.exists(file_path)
            
            return False
        except Exception as e:
            logging.error(f"Error checking if document exists: {str(e)}")
            return False
    
    def report_metadata(self, data, metadata):
        """
        Report document metadata by storing it as a JSON file.
        
        Args:
            data (dict): The document metadata as a dictionary
            metadata (dict): Document metadata
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            dir_path, json_dir, filename_base = self._get_filepath(metadata)
            
            # Store as JSON file
            json_path = os.path.join(json_dir, f"{filename_base}.json")
            
            if self.dry_run:
                logging.info(f"DRY RUN: Would store metadata to {json_path}")
                return True
                
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logging.error(f"Error storing document metadata: {str(e)}")
            return False
    
    def store(self, data, metadata):
        """
        Store document data and metadata in the file system.
        
        Args:
            data (bytes or dict): The document content
            metadata (dict): Document metadata
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            dir_path, json_dir, filename_base = self._get_filepath(metadata)
            content_type = metadata.get('content_type', '')
            
            # Store content files
            if content_type == 'application/pdf':
                file_path = os.path.join(dir_path, f"{filename_base}.pdf")
                if self.dry_run:
                    logging.info(f"DRY RUN: Would store PDF to {file_path}")
                    return True
                with open(file_path, 'wb') as f:
                    f.write(data)
                return True
            elif content_type == 'text/plain':
                file_path = os.path.join(dir_path, f"{filename_base}.txt")
                if self.dry_run:
                    logging.info(f"DRY RUN: Would store text to {file_path}")
                    return True
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(data)
                return True
            elif content_type == 'text/html':
                # Use the extracted HTML to PDF conversion utility
                pdf_data = html_to_pdf(data)
                
                if pdf_data:
                    file_path = os.path.join(dir_path, f"{filename_base}_html.pdf")
                    if self.dry_run:
                        logging.info(f"DRY RUN: Would store HTML as PDF to {file_path}")
                        return True
                    with open(file_path, 'wb') as f:
                        f.write(pdf_data)
                    return True
                else:
                    # Fallback to saving HTML source if conversion fails
                    file_path = os.path.join(dir_path, f"{filename_base}_html.html")
                    if self.dry_run:
                        logging.info(f"DRY RUN: Would store HTML source to {file_path}")
                        return True
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(data)
                    return False
            
            logging.warning(f"Unsupported content type: {content_type}")
            return False
        except Exception as e:
            logging.error(f"Error storing document: {str(e)}")
            return False
