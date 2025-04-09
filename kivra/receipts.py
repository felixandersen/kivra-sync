#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
from utils.helpers import format_date
from kivra.models import RECEIPTS_QUERY, RECEIPT_DETAILS_QUERY, KivraReceipt

class ReceiptFetcher:
    """Class for fetching receipts from Kivra."""
    
    def __init__(self, api_client, document_store):
        """
        Initialize the receipt fetcher.
        
        Args:
            api_client (KivraApiClient): Kivra API client
            document_store (DocumentStoreProvider): Document store provider
        """
        self.api_client = api_client
        self.document_store = document_store
    
    def fetch_receipts(self, max_count=None):
        """
        Fetch receipts from Kivra.
        
        Args:
            max_count (int, optional): Maximum number of receipts to fetch
            
        Returns:
            dict: Statistics about fetched receipts
        """
        print("\nFetching receipts...")
        
        # Fetch receipt list
        variables = {
            "limit": 20000,
            "offset": 0,
            "search": None
        }
        
        try:
            data = self.api_client.graphql_query("Receipts", RECEIPTS_QUERY, variables)
            
            receipts = data.get('data', {}).get('receiptsV2', {})
            receipt_list = receipts.get('list', [])
            total_receipts = receipts.get('total', 0)
            
            print(f"\nFound {total_receipts} receipts")
            
            # Report receipt list for storage
            self.document_store.report_listing('receipts', receipts)
            
            # Limit the number of receipts if max_count is set
            if max_count is not None:
                print(f"\nLimiting to {max_count} receipts (of {len(receipt_list)} available)")
                receipt_list = receipt_list[:max_count]
            
            # Add a counter for stored receipts
            receipts_stored = 0
            
            # Process each receipt
            print("\nFetching detailed information and PDF for each receipt...")
            for receipt_data in receipt_list:
                # Pass the counter to _process_receipt and get the updated value
                receipts_stored = self._process_receipt(receipt_data, receipts_stored)
                
            print("\nFinished processing all receipts!")
            
            # Return statistics
            return {
                'receipts_total': total_receipts,
                'receipts_fetched': len(receipt_list),
                'receipts_stored': receipts_stored
            }
            
        except Exception as e:
            logging.error(f"Error fetching receipts: {str(e)}")
            raise
    
    def _process_receipt(self, receipt_data, receipts_stored):
        """
        Process a single receipt.
        
        Args:
            receipt_data (dict): Receipt data from the list
            receipts_stored (int): Counter for stored receipts
            
        Returns:
            int: Updated counter for stored receipts
        """
        receipt_key = receipt_data.get('key')
        if not receipt_key:
            logging.warning("Receipt missing key, skipping")
            return
        
        # Create metadata based on date and store name
        date = format_date(receipt_data.get('purchaseDate', 'unknown_date'))
        store = receipt_data.get('store', {}).get('name', 'unknown_store')
        
        # Create receipt object
        receipt = KivraReceipt(receipt_key, date, store)
        
        # Check if JSON metadata already exists
        json_metadata = receipt.get_metadata()
        if self.document_store.exists(json_metadata):
            print(f"Skipping receipt {receipt_key} - already fetched")
            return receipts_stored
        
        print(f"\nProcessing receipt: {receipt_key}")
        
        try:
            # 1. Fetch detailed receipt information
            variables = {"key": receipt_key}
            detail_data = self.api_client.graphql_query("ReceiptDetails", RECEIPT_DETAILS_QUERY, variables)
            receipt_details = detail_data.get('data', {}).get('receiptV2', {})
            
            # 2. Store metadata
            self.document_store.report_metadata(receipt_details, json_metadata)
            print(f"Saved metadata for receipt {receipt_key}")
            
            # 3. Fetch and store PDF
            if self._fetch_and_store_pdf(receipt):
                receipts_stored += 1
            
        except Exception as e:
            logging.error(f"Error processing receipt {receipt_key}: {str(e)}")
        
        return receipts_stored
    
    def _fetch_and_store_pdf(self, receipt):
        """
        Fetch and store PDF for a receipt.
        
        Args:
            receipt (KivraReceipt): Receipt object
            
        Returns:
            bool: True if PDF was stored, False otherwise
        """
        try:
            # Construct PDF URL
            pdf_url = f"https://app.api.kivra.com/v1/user/{self.api_client.actor_key}/receipts/{receipt.key}"
            
            # Fetch PDF
            pdf_content = self.api_client.get_pdf(pdf_url)
            
            # Store PDF
            pdf_metadata = receipt.get_metadata(content_type='application/pdf')
            result = self.document_store.store(pdf_content, pdf_metadata)
            print(f"Saved PDF for receipt {receipt.key}")
            return result
            
        except Exception as e:
            logging.error(f"Error fetching PDF for receipt {receipt.key}: {str(e)}")
            raise
