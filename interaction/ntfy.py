#!/usr/bin/python3
# -*- coding: utf-8 -*-

import requests
import logging
import os
import base64
import json
import time
import signal
import sys
from interaction.base import InteractionProvider

class NtfyInteractionProvider(InteractionProvider):
    """Interaction provider that uses ntfy.sh for notifications."""
    
    def __init__(self, topic, server="https://ntfy.sh", headers=None, trigger_message="run now"):
        """
        Initialize the ntfy interaction provider.
        
        Args:
            topic (str): ntfy topic to send notifications to
            server (str, optional): ntfy server URL. Defaults to "https://ntfy.sh".
            headers (dict, optional): Additional headers for ntfy requests.
            trigger_message (str, optional): Message that triggers the listener. Defaults to "run now".
        """
        self.ntfy_topic = topic
        self.ntfy_server = server.rstrip('/')
        self.ntfy_headers = headers or {}
        self.trigger_message = trigger_message
        
    @property
    def can_listen(self):
        """
        Indicates if this provider can listen for triggers.
        
        Returns:
            bool: Always True for NtfyInteractionProvider
        """
        return True
    
    def display_qr_code(self, qr_image_path):
        """
        Send a QR code via ntfy.
        
        Args:
            qr_image_path (str): Path to the QR code image file
        """
        # Read the image file
        try:
            with open(qr_image_path, 'rb') as f:
                image_data = f.read()
            
            # Send notification with QR code
            headers = {
                "Title": "Kivra authentication",
                "Priority": "urgent",
                "Filename": os.path.basename(qr_image_path),
                "Content-Type": "application/octet-stream",
                **self.ntfy_headers
            }
            
            response = requests.post(
                f"{self.ntfy_server}/{self.ntfy_topic}",
                data=image_data,
                headers=headers
            )
            
            if response.status_code != 200:
                logging.error(f"Failed to send QR code via ntfy: {response.status_code}, {response.text}")
                print(f"Failed to send QR code via ntfy. QR code saved as '{qr_image_path}'")
            else:
                print(f"QR code sent via ntfy to topic '{self.ntfy_topic}'")
                print(f"QR code also saved as: {qr_image_path}")
        except Exception as e:
            logging.error(f"Error sending QR code via ntfy: {str(e)}")
            print(f"Error sending QR code via ntfy. QR code saved as '{qr_image_path}'")
    
    def listen(self, callback, **kwargs):
        """
        Listen for messages on the ntfy topic and call the callback when triggered.
        
        Args:
            callback (callable): Function to call when triggered
            **kwargs: Additional arguments for the callback
        """
        url = f"{self.ntfy_server}/{self.ntfy_topic}/json"
        
        logging.info(f"Listening for messages on {url}")
        logging.info(f"Trigger message: '{self.trigger_message}'")
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            logging.info("Received signal to terminate, shutting down...")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start listening
        while True:
            try:
                with requests.get(url, headers=self.ntfy_headers, stream=True) as response:
                    if response.status_code != 200:
                        logging.error(f"Failed to connect to ntfy server: {response.status_code}, {response.text}")
                        time.sleep(10)  # Wait before retrying
                        continue
                    
                    for line in response.iter_lines():
                        if not line:
                            continue
                        
                        try:
                            message = json.loads(line.decode('utf-8'))
                            message_text = message.get('message', '')
                            if message_text != '':
                                logging.info(f"Received message: {message_text}")
                            
                            if message_text.lower() == self.trigger_message.lower():
                                logging.info("Trigger message received, running callback")
                                callback()
                        except json.JSONDecodeError:
                            logging.error(f"Failed to parse message: {line.decode('utf-8')}")
                        except Exception as e:
                            logging.error(f"Error processing message: {str(e)}")
            
            except requests.exceptions.RequestException as e:
                logging.error(f"Connection error: {str(e)}")
                time.sleep(10)  # Wait before retrying
            except Exception as e:
                logging.error(f"Unexpected error: {str(e)}")
                time.sleep(10)  # Wait before retrying
    
    def report_completion(self, stats):
        """
        Report completion statistics via ntfy.
        
        Args:
            stats (dict): Statistics including receipts and letters counts
        """
        receipts_count = stats['receipts_total'] if stats['receipts_fetched'] == stats['receipts_total'] else f"{stats['receipts_fetched']} of {stats['receipts_total']}"
        letters_count = stats['letters_total'] if stats['letters_fetched'] == stats['letters_total'] else f"{stats['letters_fetched']} of {stats['letters_total']}"
        message = (
            f"Kivra sync completed\n"
            f"Receipts: {stats.get('receipts_stored', 0)} new items, {receipts_count} fetched\n"
            f"Letters: {stats.get('letters_stored', 0)} new items, {letters_count} fetched"
        )
        
        headers = {
            "Title": "Kivra sync completed",
            "Priority": "default",
            **self.ntfy_headers
        }
        
        try:
            response = requests.post(
                f"{self.ntfy_server}/{self.ntfy_topic}",
                data=message,
                headers=headers
            )
            
            if response.status_code != 200:
                logging.error(f"Failed to send completion report via ntfy: {response.status_code}, {response.text}")
                print("\nFailed to send completion report via ntfy.")
            else:
                print("\nCompletion report sent via ntfy.")
        except Exception as e:
            logging.error(f"Error sending completion report via ntfy: {str(e)}")
            print("\nError sending completion report via ntfy.")
        
        # Also print to console
        print("\nAll done!")
        print(f"Receipts: {stats['receipts_fetched']} of {stats['receipts_total']} fetched, {stats.get('receipts_stored', 0)} stored")
        print(f"Letters: {stats['letters_fetched']} of {stats['letters_total']} fetched, {stats.get('letters_stored', 0)} stored")
    
    def report_authentication_success(self):
        """
        Report that BankID authentication was successful and data sync is starting.
        """
        message = "BankID authentication successful! Starting data sync..."
        
        headers = {
            "Title": "Kivra authentication successful",
            "Priority": "default",
            **self.ntfy_headers
        }
        
        try:
            response = requests.post(
                f"{self.ntfy_server}/{self.ntfy_topic}",
                data=message,
                headers=headers
            )
            
            if response.status_code != 200:
                logging.error(f"Failed to send authentication success via ntfy: {response.status_code}, {response.text}")
                print("Failed to send authentication success via ntfy.")
            else:
                print("Authentication success sent via ntfy.")
        except Exception as e:
            logging.error(f"Error sending authentication success via ntfy: {str(e)}")
            print("Error sending authentication success via ntfy.")
        
        # Also print to console
        print("BankID authentication successful! Starting data sync...")
