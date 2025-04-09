#!/usr/bin/python3
# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod

class InteractionProvider(ABC):
    """Abstract base class for interaction providers."""
    
    @property
    def can_listen(self):
        """
        Indicates if this provider can listen for triggers.
        
        Returns:
            bool: True if the provider can listen, False otherwise
        """
        return False
    
    def listen(self, callback, **kwargs):
        """
        Listen for triggers and call the callback function when triggered.
        
        Args:
            callback (callable): Function to call when triggered
            **kwargs: Additional arguments for the listener
        
        Raises:
            NotImplementedError: If the provider does not support listening
        """
        raise NotImplementedError("This interaction provider does not support listening")
    
    @abstractmethod
    def display_qr_code(self, qr_image_path):
        """
        Display a QR code for BankID authentication.
        
        Args:
            qr_image_path (str): Path to the QR code image file
        """
        pass
    
    @abstractmethod
    def report_completion(self, stats):
        """
        Report completion statistics.
        
        Args:
            stats (dict): Statistics including:
                - receipts_total (int): Total number of receipts found
                - receipts_fetched (int): Number of receipts fetched
                - receipts_stored (int): Number of receipts stored (didn't already exist)
                - letters_total (int): Total number of letters found
                - letters_fetched (int): Number of letters fetched
                - letters_stored (int): Number of letters stored (didn't already exist)
        """
        pass
