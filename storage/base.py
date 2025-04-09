#!/usr/bin/python3
# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod

class DocumentStoreProvider(ABC):
    """Abstract base class for document storage providers."""

    @abstractmethod
    def report_listing(self, doc_type, listing):
        """
        Report a list of documents for logging or other purposes.
        
        Args:
            doc_type (str): Type of document (receipt/letter)
            listing (dict): Document listing data
        """
        pass
    
    @abstractmethod
    def exists(self, metadata):
        """
        Check if a document already exists in the store.
        
        Args:
            metadata (dict): Document metadata including type (receipt/letter),
                            date, sender/store name, document key, etc.
        
        Returns:
            bool: True if document exists, False otherwise
        """
        pass
    
    @abstractmethod
    def store(self, data, metadata):
        """
        Store document data and metadata.
        
        Args:
            data (bytes or dict): The document content (PDF bytes, text, HTML, or JSON)
            metadata (dict): Document metadata including type (receipt/letter),
                            date, sender/store name, document key, content_type, etc.
        
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def report_metadata(self, data, metadata):
        """
        Report document metadata. This is separate from store() to allow different
        handling of metadata vs. actual document content.
        
        Args:
            data (dict): The document metadata as a dictionary
            metadata (dict): Document metadata including type (receipt/letter),
                            date, sender/store name, document key, etc.
        
        Returns:
            bool: True if successful, False otherwise
        """
        pass
