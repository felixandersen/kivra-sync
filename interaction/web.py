#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import json
import shutil
import threading
import logging
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from interaction.base import InteractionProvider

class WebInteractionProvider(InteractionProvider):
    """Web-based interaction provider that serves an HTTP interface."""
    
    def __init__(self, port=8080, host='0.0.0.0'):
        """
        Initialize the web interaction provider.
        
        Args:
            port (int): Port to run the web server on (default: 8080)
            host (str): Host to bind to (default: 0.0.0.0)
        """
        self.port = port
        self.host = host
        self.sse_clients = []
        self.current_state = {"status": "idle", "message": "Ready to sync"}
        self.server = None
        self.server_thread = None
        self.callback = None
        self.static_dir = os.path.join(os.path.dirname(__file__), 'web_static')
        self.temp_dir = None
        self.qr_path = None
        
    @property
    def can_listen(self):
        """
        Indicates if this provider can listen for triggers.
        
        Returns:
            bool: Always True for WebInteractionProvider
        """
        return True
    
    def _send_sse_message(self, data):
        """
        Send a Server-Sent Event message to all connected clients.
        
        Args:
            data (dict): Data to send as JSON
        """
        message = f"data: {json.dumps(data)}\n\n"
        # Store current state
        self.current_state.update(data)
        
        # Send to all connected SSE clients
        clients_to_remove = []
        for client in self.sse_clients:
            try:
                client.wfile.write(message.encode())
                client.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                clients_to_remove.append(client)
        
        # Remove disconnected clients
        for client in clients_to_remove:
            self.sse_clients.remove(client)
    
    def display_qr_code(self, qr_image_path):
        """
        Display a QR code via the web interface.
        
        Args:
            qr_image_path (str): Path to the QR code image file
        """
        try:
            # Copy QR code to web-accessible location
            if self.temp_dir:
                web_qr_path = os.path.join(self.temp_dir, 'qr.png')
                shutil.copy2(qr_image_path, web_qr_path)
                self.qr_path = web_qr_path
                
                # Send SSE update
                self._send_sse_message({
                    "status": "qr_ready",
                    "message": "Please scan the QR code with BankID",
                    "qr_url": "/qr.png"
                })
                
                print(f"QR code available at web interface and saved as: {qr_image_path}")
            else:
                logging.error("Temp directory not set for web provider")
                print(f"QR code saved as: {qr_image_path}")
        except Exception as e:
            logging.error(f"Error serving QR code via web interface: {str(e)}")
            print(f"Error serving QR code via web interface. QR code saved as: {qr_image_path}")
    
    def report_completion(self, stats):
        """
        Report completion statistics via the web interface.
        
        Args:
            stats (dict): Statistics including receipts and letters counts
        """
        receipts_count = stats['receipts_total'] if stats['receipts_fetched'] == stats['receipts_total'] else f"{stats['receipts_fetched']} of {stats['receipts_total']}"
        letters_count = stats['letters_total'] if stats['letters_fetched'] == stats['letters_total'] else f"{stats['letters_fetched']} of {stats['letters_total']}"
        
        message = (
            f"Sync completed successfully!\n"
            f"Receipts: {stats.get('receipts_stored', 0)} new items, {receipts_count} fetched\n"
            f"Letters: {stats.get('letters_stored', 0)} new items, {letters_count} fetched"
        )
        
        # Send SSE update
        self._send_sse_message({
            "status": "complete",
            "message": message,
            "stats": stats
        })
        
        # Also print to console
        print("\nAll done!")
        print(f"Receipts: {stats['receipts_fetched']} of {stats['receipts_total']} fetched, {stats.get('receipts_stored', 0)} stored")
        print(f"Letters: {stats['letters_fetched']} of {stats['letters_total']} fetched, {stats.get('letters_stored', 0)} stored")
        print(f"Web interface available at http://{self.host}:{self.port}")
    
    def report_authentication_success(self):
        """
        Report that BankID authentication was successful and data sync is starting.
        """
        self._send_sse_message({
            "status": "authenticated",
            "message": "BankID authentication successful! \n\nCheck terminal for detailed progress."
        })
    
    def listen(self, callback, **kwargs):
        """
        Start the web server and listen for triggers.
        
        Args:
            callback (callable): Function to call when triggered
            **kwargs: Additional arguments for the callback
        """
        self.callback = callback
        
        # debug logging
        print("Starting web interaction provider...")

        # Set temp directory for QR codes
        self.temp_dir = kwargs.get('temp_dir', '/tmp')
        
        # Create request handler class with access to provider instance
        provider = self
        
        class WebRequestHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # Suppress default HTTP server logging
                pass
            
            def do_GET(self):
                parsed_path = urlparse(self.path)
                path = parsed_path.path
                
                if path == '/':
                    self._serve_file('index.html', 'text/html')
                elif path == '/events':
                    self._handle_sse()
                elif path == '/qr.png':
                    self._serve_qr()
                elif path.startswith('/static/'):
                    filename = path[8:]  # Remove '/static/'
                    if filename == 'style.css':
                        self._serve_file('style.css', 'text/css')
                    elif filename == 'script.js':
                        self._serve_file('script.js', 'application/javascript')
                    else:
                        self._send_404()
                else:
                    self._send_404()
            
            def do_POST(self):
                if self.path == '/trigger':
                    self._handle_trigger()
                else:
                    self._send_404()
            
            def _serve_file(self, filename, content_type):
                file_path = os.path.join(provider.static_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    self.send_response(200)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', str(len(content.encode())))
                    self.end_headers()
                    self.wfile.write(content.encode())
                except FileNotFoundError:
                    self._send_404()
            
            def _serve_qr(self):
                if provider.qr_path and os.path.exists(provider.qr_path):
                    try:
                        with open(provider.qr_path, 'rb') as f:
                            content = f.read()
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'image/png')
                        self.send_header('Content-Length', str(len(content)))
                        self.end_headers()
                        self.wfile.write(content)
                    except Exception:
                        self._send_404()
                else:
                    self._send_404()
            
            def _handle_sse(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'keep-alive')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                # Add client to SSE clients list
                provider.sse_clients.append(self)
                
                # Send current state immediately
                initial_message = f"data: {json.dumps(provider.current_state)}\n\n"
                try:
                    self.wfile.write(initial_message.encode())
                    self.wfile.flush()
                except:
                    pass
                
                # Keep connection alive (client will be removed when connection breaks)
                try:
                    while True:
                        # Send heartbeat every 30 seconds
                        import time
                        time.sleep(30)
                        heartbeat = "data: {\"heartbeat\": true}\n\n"
                        self.wfile.write(heartbeat.encode())
                        self.wfile.flush()
                except:
                    # Connection closed
                    if self in provider.sse_clients:
                        provider.sse_clients.remove(self)
            
            def _handle_trigger(self):
                # Send immediate response FIRST to prevent blocking
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "triggered"}')
                
                # Start sync in background thread with SSE messaging
                def run_sync():
                    try:
                        # Send processing status after HTTP response is sent
                        provider._send_sse_message({
                            "status": "processing",
                            "message": "Starting Kivra sync..."
                        })
                        
                        # Run the actual sync
                        provider.callback()
                    except Exception as e:
                        logging.error(f"Error during sync: {str(e)}")
                        provider._send_sse_message({
                            "status": "error",
                            "message": f"Sync failed: {str(e)}"
                        })
                
                sync_thread = threading.Thread(target=run_sync)
                sync_thread.daemon = True
                sync_thread.start()
            
            def _send_404(self):
                self.send_response(404)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Not Found')
        
        # Start HTTP server with threading support
        try:
            self.server = ThreadingHTTPServer((self.host, self.port), WebRequestHandler)
            print(f"Web interface starting at http://{self.host}:{self.port}")
            
            # Start server in background thread
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            print(f"Web interface ready at http://{self.host}:{self.port}")
            
            # Keep main thread alive
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down web server...")
                self.server.shutdown()
                self.server.server_close()
                
        except Exception as e:
            logging.error(f"Failed to start web server: {str(e)}")
            raise
