#!/usr/bin/python3
# -*- coding: utf-8 -*-

import requests
import logging
import sys
from kivra.models import INBOXES_QUERY, CONTENT_DETAILS_QUERY

class KivraApiClient:
    """Client for interacting with Kivra's API."""
    
    def __init__(self, access_token, actor_key, actor_type='user', user_id=None):
        """
        Initialize the Kivra API client.
        
        Args:
            access_token (str): OAuth access token
            actor_key (str): Key of the inbox to act on (user ID or company key)
            actor_type (str, optional): 'user' or 'company' (default: 'user')
            user_id (str, optional): Kivra user ID of the logged in user (default: actor_key)
        """
        self.access_token = access_token
        self.actor_key = actor_key
        self.actor_type = actor_type
        self.user_id = user_id or actor_key
        self.graphql_url = "https://bff.kivra.com/graphql"
        self.session = requests.Session()
    
    def get_headers(self):
        """
        Get common headers for API requests.
        
        Returns:
            dict: Headers for API requests
        """
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Origin': 'https://inbox.kivra.com',
            'Referer': 'https://inbox.kivra.com/',
            'Authorization': f'Bearer {self.access_token}',
            'X-Actor-Key': self.actor_key,
            'X-Actor-Type': self.actor_type,
            'X-Session-Actor': f'user_{self.user_id}',
            'X-Kivra-Environment': 'production',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
            'Accept-Language': 'sv',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
    
    def graphql_query(self, operation_name, query, variables):
        """
        Execute a GraphQL query.
        
        Args:
            operation_name (str): Name of the GraphQL operation
            query (str): GraphQL query string
            variables (dict): Variables for the query
            
        Returns:
            dict: Query response data
        """
        payload = {
            "operationName": operation_name,
            "query": query,
            "variables": variables
        }
        
        logging.debug(f"GraphQL query: {operation_name}")
        logging.debug(f"Variables: {variables}")
        
        response = self.session.post(
            self.graphql_url,
            json=payload,
            headers=self.get_headers()
        )
        
        if response.status_code != 200:
            logging.error(f"GraphQL error: {response.status_code}, {response.text}")
            raise Exception(f"GraphQL query failed: {response.status_code}")
            
        data = response.json()
        if 'errors' in data:
            logging.error(f"GraphQL errors: {data['errors']}")
            raise Exception(f"GraphQL query returned errors: {data['errors']}")
            
        return data
    
    def for_actor(self, actor_key, actor_type):
        """
        Create a client acting on another inbox (e.g. a business account) with the same session.
        
        Args:
            actor_key (str): Key of the inbox to act on
            actor_type (str): 'user' or 'company'
            
        Returns:
            KivraApiClient: New API client
        """
        return KivraApiClient(self.access_token, actor_key, actor_type, user_id=self.user_id)
    
    def get_inboxes(self):
        """
        Get all inboxes the logged in user has access to (own, shared and business accounts).
        
        Returns:
            list: Inboxes with key, name, type, role, isShared and isShareAccepted
        """
        data = self.graphql_query("Inboxes", INBOXES_QUERY, {})
        return data.get('data', {}).get('inboxes', []) or []
    
    def get_pdf(self, url):
        """
        Get a PDF document from Kivra.
        
        Args:
            url (str): URL to the PDF document
            
        Returns:
            bytes: PDF content
        """
        headers = {
            'Authorization': f'token {self.access_token}',
            'Accept': 'application/pdf'
        }
        
        response = self.session.get(url, headers=headers)
        
        if response.status_code != 200:
            logging.error(f"Failed to get PDF. Status: {response.status_code}")
            logging.error(f"URL: {url}")
            logging.error(f"Headers: {headers}")
            logging.error(f"Response headers: {dict(response.headers)}")
            logging.error(f"Response body: {response.text}")
            raise Exception(f"Failed to get PDF: {response.status_code}")
        
        return response.content
    
    def get_content_details(self, content_key):
        """
        Get details for a content item (letter).
        
        Args:
            content_key (str): Content key
            
        Returns:
            dict: Content details
        """
        content_url = f"https://app.api.kivra.com/v1/content/{content_key}"
        headers = {
            'Authorization': f'token {self.access_token}',
            'Accept': 'application/json'
        }
        
        response = self.session.get(content_url, headers=headers)
        
        if response.status_code != 200:
            logging.error(f"Failed to get content details. Status: {response.status_code}")
            logging.error(f"URL: {content_url}")
            logging.error(f"Response: {response.text}")
            raise Exception(f"Failed to get content details: {response.status_code}")
        
        return response.json()
    
    def get_content_details_v2(self, content_key):
        """
        Get details for a content item (letter) via GraphQL, scoped to the current actor.
        
        Args:
            content_key (str): Content key
            
        Returns:
            dict: Content details with 'parts', each having 'content_type' and 'path'
        """
        data = self.graphql_query("ContentDetails", CONTENT_DETAILS_QUERY, {"key": content_key})
        content = data.get('data', {}).get('content') or {}
        parts = [
            {'content_type': part.get('mimeType'), 'name': part.get('name'), 'path': part.get('path')}
            for part in content.get('parts') or []
        ]
        return {**content, 'parts': parts}
    
    def get_core_path(self, path):
        """
        Get a raw file from Kivra's core API by path (as returned by get_content_details_v2).
        
        Args:
            path (str): Path relative to the core API origin
            
        Returns:
            bytes: File content
        """
        file_url = f"https://app.api.kivra.com{path}"
        headers = {
            'Authorization': f'token {self.access_token}'
        }
        
        response = self.session.get(file_url, headers=headers)
        
        if response.status_code != 200:
            logging.error(f"Failed to get file. Status: {response.status_code}")
            logging.error(f"URL: {file_url}")
            logging.error(f"Response: {response.text}")
            raise Exception(f"Failed to get file: {response.status_code}")
        
        return response.content
    
    def get_content_file(self, content_key, file_key):
        """
        Get a file from a content item (letter).
        
        Args:
            content_key (str): Content key
            file_key (str): File key
            
        Returns:
            bytes: File content
        """
        file_url = f"https://app.api.kivra.com/v1/content/{content_key}/file/{file_key}/raw"
        headers = {
            'Authorization': f'token {self.access_token}'
        }
        
        response = self.session.get(file_url, headers=headers)
        
        if response.status_code != 200:
            logging.error(f"Failed to get content file. Status: {response.status_code}")
            logging.error(f"URL: {file_url}")
            logging.error(f"Response: {response.text}")
            raise Exception(f"Failed to get content file: {response.status_code}")
        
        return response.content
