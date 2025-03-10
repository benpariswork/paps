"""
HTTP Protocol Handler

This module implements the HTTP protocol handler for the Protocol Agnostic Proxy Server.
"""

import logging
import socket
import select
import re
from urllib.parse import urlparse

from src.protocols.base import BaseProtocolHandler


class HTTPProtocolHandler(BaseProtocolHandler):
    """Handler for HTTP protocol."""
    
    def __init__(self, client_socket, client_address, protocol_config, inspection_config):
        """Initialize the HTTP protocol handler."""
        super().__init__(client_socket, client_address, protocol_config, inspection_config)
        self.target_host = None
        self.target_port = None
    
    def _setup_server_connection(self):
        """Set up the connection to the destination server based on the HTTP request."""
        # First, we need to read the client's request to determine the target server
        # We'll read just the headers to extract the Host or the CONNECT information
        header_data = b''
        while b'\r\n\r\n' not in header_data:
            chunk = self.client_socket.recv(self.buffer_size)
            if not chunk:
                raise Exception("Client closed connection before sending complete headers")
            header_data += chunk
            if len(header_data) > 65536:  # Limit to avoid memory issues
                raise Exception("Headers too large")
        
        # Store the initial request data to replay later
        self.initial_request = header_data
        
        # Determine if this is a CONNECT request (for HTTPS) or a regular HTTP request
        if header_data.startswith(b'CONNECT '):
            # Extract target from CONNECT request
            connect_line = header_data.split(b'\r\n')[0].decode('utf-8', 'ignore')
            connect_parts = connect_line.split(' ')
            if len(connect_parts) >= 2:
                host_port = connect_parts[1]
                host_parts = host_port.split(':')
                self.target_host = host_parts[0]
                self.target_port = int(host_parts[1]) if len(host_parts) > 1 else 443
        else:
            # Extract target from Host header
            host_match = re.search(rb'Host: ([^\r\n]+)', header_data)
            if host_match:
                host_header = host_match.group(1).decode('utf-8', 'ignore')
                host_parts = host_header.split(':')
                self.target_host = host_parts[0]
                self.target_port = int(host_parts[1]) if len(host_parts) > 1 else 80
            else:
                # Try to extract from absolute URL in request line
                request_line = header_data.split(b'\r\n')[0].decode('utf-8', 'ignore')
                url_match = re.search(r'^[A-Z]+ (http[s]?://[^/\s]+)', request_line)
                if url_match:
                    url = urlparse(url_match.group(1))
                    self.target_host = url.hostname
                    self.target_port = url.port or (443 if url.scheme == 'https' else 80)
        
        if not self.target_host or not self.target_port:
            raise Exception("Could not determine target server from HTTP request")
        
        logging.info(f"HTTP connection to {self.target_host}:{self.target_port}")
        
        # Now connect to the target server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.connect((self.target_host, self.target_port))
        
        # For CONNECT requests, we need to send a 200 Connection Established response
        if header_data.startswith(b'CONNECT '):
            self.client_socket.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        else:
            # For regular HTTP requests, we need to send the initial request to the server
            self.server_socket.sendall(self.initial_request)
    
    def _proxy_data(self):
        """Proxy data between client and server."""
        # Adjust socket timeouts for better interactivity
        self.client_socket.settimeout(0.1)
        self.server_socket.settimeout(0.1)
        
        # Set up for select
        sockets = [self.client_socket, self.server_socket]
        
        # If we have a regular HTTP request (not CONNECT), we've already sent the
        # initial request to the server, so we should skip forwarding it again
        skip_client_first = hasattr(self, 'initial_request') and not self.initial_request.startswith(b'CONNECT ')
        
        while self.running:
            try:
                # Use select to wait for readable sockets
                readable, _, exceptional = select.select(sockets, [], sockets, 0.1)
                
                if exceptional:
                    # Handle exceptional conditions
                    break
                
                for sock in readable:
                    if sock is self.client_socket and not skip_client_first:
                        # Handle client to server data
                        data = sock.recv(self.buffer_size)
                        if not data:
                            self.running = False
                            break
                        
                        # Process the packet if inspection is enabled
                        if self.should_inspect_packet(data, 'client_to_server'):
                            packet = self.create_packet(data, 'client_to_server')
                            self.log_packet(packet)
                            
                            # If packet is paused, we'll need a mechanism to wait for resumption
                            # For now, we'll just log it and continue
                            if packet.paused:
                                logging.info(f"Packet {packet.id} paused (client to server)")
                                # In a real implementation, we would wait here until the packet is resumed
                        
                        # Forward data to server
                        self.server_socket.sendall(data)
                    
                    elif sock is self.server_socket:
                        # Handle server to client data
                        data = sock.recv(self.buffer_size)
                        if not data:
                            self.running = False
                            break
                        
                        # Process the packet if inspection is enabled
                        if self.should_inspect_packet(data, 'server_to_client'):
                            packet = self.create_packet(data, 'server_to_client')
                            self.log_packet(packet)
                            
                            # If packet is paused, we'll need a mechanism to wait for resumption
                            # For now, we'll just log it and continue
                            if packet.paused:
                                logging.info(f"Packet {packet.id} paused (server to client)")
                                # In a real implementation, we would wait here until the packet is resumed
                        
                        # Forward data to client
                        self.client_socket.sendall(data)
                
                # If this was the first client data and we're skipping it,
                # we should no longer skip after the first iteration
                if skip_client_first:
                    skip_client_first = False
            
            except socket.timeout:
                # This is expected due to the non-blocking sockets
                continue
            except ConnectionResetError:
                logging.warning("Connection reset")
                break
            except Exception as e:
                logging.error(f"Error in proxy loop: {e}")
                break
    
    def parse_packet(self, data, direction):
        """
        Parse an HTTP packet.
        
        Args:
            data (bytes): Raw packet data
            direction (str): Direction of the packet
            
        Returns:
            dict: Parsed packet metadata
        """
        metadata = {}
        
        try:
            # Basic HTTP parsing - this could be enhanced with a proper HTTP parser
            if direction == 'client_to_server':
                # Parse request
                lines = data.split(b'\r\n')
                if lines:
                    # Parse request line
                    request_line = lines[0].decode('utf-8', 'ignore')
                    parts = request_line.split(' ')
                    if len(parts) >= 3:
                        metadata['method'] = parts[0]
                        metadata['path'] = parts[1]
                        metadata['version'] = parts[2]
                
                # Parse headers
                metadata['headers'] = {}
                for line in lines[1:]:
                    if not line or line == b'\r\n':
                        break
                    try:
                        header_line = line.decode('utf-8', 'ignore')
                        if ':' in header_line:
                            name, value = header_line.split(':', 1)
                            metadata['headers'][name.strip()] = value.strip()
                    except:
                        pass
            
            else:  # server_to_client
                # Parse response
                lines = data.split(b'\r\n')
                if lines:
                    # Parse status line
                    status_line = lines[0].decode('utf-8', 'ignore')
                    parts = status_line.split(' ', 2)
                    if len(parts) >= 3:
                        metadata['version'] = parts[0]
                        metadata['status_code'] = parts[1]
                        metadata['status_message'] = parts[2]
                
                # Parse headers
                metadata['headers'] = {}
                for line in lines[1:]:
                    if not line or line == b'\r\n':
                        break
                    try:
                        header_line = line.decode('utf-8', 'ignore')
                        if ':' in header_line:
                            name, value = header_line.split(':', 1)
                            metadata['headers'][name.strip()] = value.strip()
                    except:
                        pass
            
            # Determine content type
            content_type = metadata.get('headers', {}).get('Content-Type', '')
            metadata['content_type'] = content_type
            
            # Attempt to parse body based on Content-Type
            if b'\r\n\r\n' in data:
                body = data.split(b'\r\n\r\n', 1)[1]
                metadata['body_length'] = len(body)
                
                # For text-based content types, include a preview
                if content_type.startswith(('text/', 'application/json', 'application/xml')):
                    try:
                        preview = body[:100].decode('utf-8', 'ignore')
                        metadata['body_preview'] = preview
                    except:
                        pass
        
        except Exception as e:
            logging.error(f"Error parsing HTTP packet: {e}")
            metadata['parse_error'] = str(e)
        
        return metadata
    
    @classmethod
    def get_protocol_name(cls):
        """Get the protocol name."""
        return 'http'
