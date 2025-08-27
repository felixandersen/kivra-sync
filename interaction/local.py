#!/usr/bin/python3
# -*- coding: utf-8 -*-

from PIL import Image
import logging
from interaction.base import InteractionProvider

class LocalInteractionProvider(InteractionProvider):
    """Default interaction provider that displays QR codes locally and reports to console."""
    
    def display_qr_code(self, qr_image_path):
        """
        Display a QR code for BankID authentication.
        
        Args:
            qr_image_path (str): Path to the QR code image file
        """
        # Open the image with the system's default image viewer
        try:
            Image.open(qr_image_path).show()
            print(f"QR code has been saved as: {qr_image_path}")
        except Exception as e:
            logging.error(f"Could not display QR code: {e}")
            print(f"QR code saved as '{qr_image_path}'")
    
    def report_completion(self, stats):
        """
        Report completion statistics to console.
        
        Args:
            stats (dict): Statistics including receipts and letters counts
        """
        print("\nAll done!")
        receipts_count = stats['receipts_total'] if stats['receipts_fetched'] == stats['receipts_total'] else f"{stats['receipts_fetched']} of {stats['receipts_total']}"
        letters_count = stats['letters_total'] if stats['letters_fetched'] == stats['letters_total'] else f"{stats['letters_fetched']} of {stats['letters_total']}"
        print(f"Receipts: {stats.get('receipts_stored', 0)} new items, {receipts_count} fetched")
        print(f"Letters: {stats.get('letters_stored', 0)} new items, {letters_count} fetched")
    
    def report_authentication_success(self):
        """
        Report that BankID authentication was successful and data sync is starting.
        """
        print("BankID authentication successful! Starting data sync...")
