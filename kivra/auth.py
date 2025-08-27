#!/usr/bin/python3
# -*- coding: utf-8 -*-

import requests
import hashlib
import base64
import secrets
import time
import qrcode
import os
import logging
import json
import sys

class KivraAuth:
    """Class for handling Kivra authentication via BankID."""
    
    def __init__(self, temp_dir, interaction_provider):
        """
        Initialize the Kivra authentication handler.
        
        Args:
            temp_dir (str): Directory for temporary files like QR codes
            interaction_provider (InteractionProvider): Provider for user interaction
        """
        self.temp_dir = temp_dir
        self.interaction_provider = interaction_provider
        self.session = requests.Session()
        self.client_id = "14085255171411300228f14dceae786da5a00285fe"
        
    def authenticate(self, ssn):
        """
        Authenticate with Kivra using BankID.
        
        Args:
            ssn (str): Social security number in format YYYYMMDDXXXX
            
        Returns:
            dict: Authentication tokens and user information
        """
        # Initialize session
        self.session.get("https://app.kivra.com/")
        
        # Generate code verifier and challenge
        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)
        
        # Initialize OAuth2
        auth_data = self._initialize_oauth2(code_challenge)
        
        # Display QR code and wait for authentication
        qr_code = auth_data.get('qr_code')
        next_poll_url = auth_data.get('next_poll_url')
        auth_code = auth_data.get('code')
        
        if not qr_code or not auth_code:
            logging.error("Missing QR code or auth code in response")
            sys.exit("Authentication initialization failed")
        
        # Generate and save QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_code)
        qr.make(fit=True)
        
        # Create and save QR code as a temporary image
        img = qr.make_image(fill_color="black", back_color="white")
        temp_path = os.path.join(self.temp_dir, "kivra_qr.png")
        img.save(temp_path)
        
        # Display QR code using the interaction provider
        self.interaction_provider.display_qr_code(temp_path)
        print("\nQR-kod visas nu. Skanna den med BankID-appen.")
        
        # Poll for authentication completion
        token_info = self._poll_for_auth(next_poll_url, auth_code, code_verifier)
        
        # Clean up temporary QR code file
        try:
            os.remove(temp_path)
        except:
            pass
            
        return token_info
    
    def _generate_code_verifier(self):
        """Generate a code verifier for PKCE."""
        return secrets.token_urlsafe(32)
    
    def _generate_code_challenge(self, code_verifier):
        """Generate a code challenge from the code verifier using SHA-256."""
        code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8').rstrip('=')
        return code_challenge
    
    def _initialize_oauth2(self, code_challenge):
        """
        Initialize OAuth2 authorization with Kivra.
        
        Args:
            code_challenge (str): PKCE code challenge
            
        Returns:
            dict: Authorization data including QR code and polling URL
        """
        auth_url = "https://app.api.kivra.com/v2/oauth2/authorize"
        auth_params = {
            'response_type': 'bankid_all',
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'scope': 'openid profile',
            'client_id': self.client_id,
            'redirect_uri': 'https://inbox.kivra.com/auth/kivra/return'
        }
        
        logging.info("Initializing OAuth2 authorization")
        
        r = self.session.post(auth_url, 
                             json=auth_params,
                             headers={
                                 'Content-Type': 'application/json',
                                 'Accept': 'application/json',
                                 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                             })
        
        if r.status_code not in [201, 202]:
            logging.error(f"OAuth2 authorization failed. Status: {r.status_code}, Response: {r.text}")
            sys.exit("Could not initialize OAuth2")
        
        return r.json()
    
    
    def _poll_for_auth(self, next_poll_url, auth_code, code_verifier):
        """
        Poll for BankID authentication completion.
        
        Args:
            next_poll_url (str): URL to poll for authentication status
            auth_code (str): Authorization code
            code_verifier (str): PKCE code verifier
            
        Returns:
            dict: Token information including access_token and actor_key
        """
        print("\nWaiting for BankID authentication...")
        
        while True:
            time.sleep(5)
            poll_response = self.session.get(f"https://app.api.kivra.com{next_poll_url}")
            poll_data = poll_response.json()
            
            if poll_data.get('status') == 'complete':
                print("\nBankID authentication successful!")
                
                # Notify interaction provider that authentication succeeded
                self.interaction_provider.report_authentication_success()
                
                # Exchange authorization code for tokens
                token_url = "https://app.api.kivra.com/v2/oauth2/token"
                token_data = {
                    "grant_type": "authorization_code",
                    "code": auth_code,
                    "client_id": self.client_id,
                    "redirect_uri": "https://inbox.kivra.com/auth/kivra/return",
                    "code_verifier": code_verifier
                }
                
                print("Fetching OAuth token...")
                token_response = self.session.post(token_url, 
                                                 json=token_data,
                                                 headers={'Content-Type': 'application/json'})
                
                if token_response.status_code != 200:
                    logging.error(f"Failed to fetch token. Status: {token_response.status_code}, Response: {token_response.text}")
                    sys.exit("Token retrieval failed")
                
                token_info = token_response.json()
                access_token = token_info.get('access_token')
                id_token = token_info.get('id_token')
                
                # Decode JWT to get user information
                id_token_parts = id_token.split('.')
                if len(id_token_parts) < 2:
                    logging.error("Invalid id_token structure")
                    sys.exit("Could not parse id_token")
                
                # Decode base64
                padding = '=' * (4 - len(id_token_parts[1]) % 4)
                jwt_payload = base64.b64decode(id_token_parts[1] + padding)
                jwt_data = json.loads(jwt_payload)
                
                # Get kivra_user_id from JWT
                actor_key = jwt_data.get('kivra_user_id')
                
                if not actor_key:
                    logging.error(f"Could not find kivra_user_id in token: {jwt_data}")
                    sys.exit("Missing kivra_user_id")
                
                # Return token information
                return {
                    'access_token': access_token,
                    'actor_key': actor_key,
                    'jwt_data': jwt_data
                }
            
            elif poll_data.get('status') == 'pending':
                print(".", end="", flush=True)  # Show progress
            else:
                logging.error(f"Error during polling. Status: {poll_data.get('status')}, Response: {poll_data}")
                sys.exit("BankID authentication failed")
