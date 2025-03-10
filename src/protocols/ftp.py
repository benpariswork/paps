"""
FTP Protocol Handler

This module implements the FTP protocol handler for the Protocol Agnostic Proxy Server.
"""

import logging
import socket
import select
import re

from src.protocols.base import BaseProtocolHandler


class FTPProtocolHandler(BaseProtocolHandler):
    """Handler for FTP protocol."""
    
    def __init__(self, client_socket, client_address, protocol_config, inspection_config):
        """Initialize the FTP protocol handler."""
        super().__init__(client_socket, client_address, protocol_config, inspection_config)
        self.target_host = None
        self.target_port = 21  # Default FTP port
        self.data_channel_socket = None
        self.passive_mode = False
        self.data_connection = None
    
    def _setup_server_connection(self):
        """Set up the connection to the destination FTP server."""
        # For FTP, we might receive a user's target in the USER command
        # But initially, we can use a default or configured target
        target_config = self.protocol_config.get('target', {})
        self.target_host = target_config.get('host', '127.0.0.1')
        self.target_port = target_config.get('port', 21)
        
        logging.info(f"FTP connection to {self.target_host}:{self.target_port}")
        
        # Connect to the FTP server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.connect((self.target_host, self.target_port))
        
        # Receive the welcome message from the server
        welcome_data = self.server_socket.recv(self.buffer_size)
        if welcome_data:
            # Forward the welcome message to the client
            self.client_socket.sendall(welcome_data)
            
            # Log the welcome message
            if self.should_inspect_packet(welcome_data, 'server_to_client'):
                packet = self.create_packet(welcome_data, 'server_to_client')
                self.log_packet(packet)
    
    def _handle_data_connection(self, passive_ip, passive_port):
        """
        Handle the data connection for FTP in passive mode.
        
        Args:
            passive_ip (str): IP address for passive mode connection
            passive_port (int): Port for passive mode connection
        """
        try:
            # Create a data socket to connect to the server's data port
            data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            data_socket.connect((passive_ip, passive_port))
            
            logging.info(f"Established FTP data connection to {passive_ip}:{passive_port}")
            self.data_connection = {
                'client_socket': None,  # Will be set when client connects
                'server_socket': data_socket
            }
        except Exception as e:
            logging.error(f"Error setting up FTP data connection: {e}")
    
    def _handle_port_command(self, command_line):
        """
        Handle the PORT command in FTP (active mode).
        
        Args:
            command_line (str): The PORT command line
        """
        # Extract the address and port from the PORT command
        # Format: PORT h1,h2,h3,h4,p1,p2
        match = re.search(r'PORT\s+(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)', command_line)
        if match:
            h1, h2, h3, h4, p1, p2 = map(int, match.groups())
            client_ip = f"{h1}.{h2}.{h3}.{h4}"
            client_port = (p1 * 256) + p2
            
            logging.info(f"FTP PORT command: {client_ip}:{client_port}")
            
            # For active mode, we would need to set up a server socket to accept connections
            # from the client, and then connect to the FTP server's data port when the server
            # sends a response. This is more complex and not fully implemented here.
            # 
            # For simplicity, we'll just log the command and continue with the regular proxy.
    
    def _handle_pasv_response(self, response_line):
        """
        Handle the response to the PASV command in FTP.
        
        Args:
            response_line (str): The response to the PASV command
        """
        # Extract the address and port from the PASV response
        # Format: 227 Entering Passive Mode (h1,h2,h3,h4,p1,p2)
        match = re.search(r'\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)', response_line)
        if match:
            h1, h2, h3, h4, p1, p2 = map(int, match.groups())
            passive_ip = f"{h1}.{h2}.{h3}.{h4}"
            passive_port = (p1 * 256) + p2
            
            logging.info(f"FTP passive mode: {passive_ip}:{passive_port}")
            self.passive_mode = True
            
            # Set up the data connection for passive mode
            self._handle_data_connection(passive_ip, passive_port)
    
    def _proxy_data(self):
        """Proxy data between client and server for FTP."""
        # Adjust socket timeouts for better interactivity
        self.client_socket.settimeout(0.1)
        self.server_socket.settimeout(0.1)
        
        # Set up for select
        sockets = [self.client_socket, self.server_socket]
        
        while self.running:
            try:
                # Use select to wait for readable sockets
                readable, _, exceptional = select.select(sockets, [], sockets, 0.1)
                
                if exceptional:
                    # Handle exceptional conditions
                    break
                
                for sock in readable:
                    if sock is self.client_socket:
                        # Handle client to server data
                        data = sock.recv(self.buffer_size)
                        if not data:
                            self.running = False
                            break
                        
                        # Process the packet if inspection is enabled
                        if self.should_inspect_packet(data, 'client_to_server'):
                            packet = self.create_packet(data, 'client_to_server')
                            self.log_packet(packet)
                            
                            # Check for FTP commands
                            try:
                                command_line = data.decode('utf-8', 'ignore').strip()
                                
                                # Handle PORT command (active mode)
                                if command_line.startswith('PORT '):
                                    self._handle_port_command(command_line)
                                
                                # Handle USER command to potentially change target
                                elif command_line.startswith('USER '):
                                    # In a real implementation, we might want to handle this
                                    # to support virtual hosting or different FTP servers
                                    pass
                            except:
                                pass
                        
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
                            
                            # Check for PASV response
                            try:
                                response_line = data.decode('utf-8', 'ignore').strip()
                                
                                # Handle PASV response (passive mode)
                                if '227 Entering Passive Mode' in response_line:
                                    self._handle_pasv_response(response_line)
                            except:
                                pass
                        
                        # Forward data to client
                        self.client_socket.sendall(data)
                
                # Handle data connection if it exists
                if self.data_connection:
                    # TODO: Implement data connection handling
                    # This would involve proxying data between the client's data connection
                    # and the server's data connection, similar to the control connection.
                    pass
            
            except socket.timeout:
                # This is expected due to the non-blocking sockets
                continue
            except ConnectionResetError:
                logging.warning("Connection reset")
                break
            except Exception as e:
                logging.error(f"Error in proxy loop: {e}")
                break
    
    def _cleanup(self):
        """Clean up resources."""
        super()._cleanup()
        
        # Clean up data connection if it exists
        if hasattr(self, 'data_connection') and self.data_connection:
            try:
                if self.data_connection.get('client_socket'):
                    self.data_connection['client_socket'].close()
                if self.data_connection.get('server_socket'):
                    self.data_connection['server_socket'].close()
            except:
                pass
    
    def parse_packet(self, data, direction):
        """
        Parse an FTP packet.
        
        Args:
            data (bytes): Raw packet data
            direction (str): Direction of the packet
            
        Returns:
            dict: Parsed packet metadata
        """
        metadata = {}
        
        try:
            # Decode the data as text
            text = data.decode('utf-8', 'ignore').strip()
            
            if direction == 'client_to_server':
                # Parse FTP command
                parts = text.split(' ', 1)
                command = parts[0].upper()
                metadata['command'] = command
                
                if len(parts) > 1:
                    metadata['argument'] = parts[1]
                
                # Special handling for specific commands
                if command == 'USER':
                    metadata['username'] = parts[1] if len(parts) > 1 else ''
                elif command == 'PASS':
                    metadata['password'] = '********'  # Mask the password
                elif command in ['CWD', 'CDUP', 'PWD']:
                    metadata['directory_operation'] = True
                elif command in ['RETR', 'STOR', 'LIST', 'NLST']:
                    metadata['data_channel_operation'] = True
                    if command in ['RETR', 'STOR'] and len(parts) > 1:
                        metadata['filename'] = parts[1]
            else:  # server_to_client
                # Parse FTP response
                parts = text.split(' ', 1)
                if parts and parts[0].isdigit():
                    code = parts[0]
                    metadata['response_code'] = code
                    
                    if len(parts) > 1:
                        metadata['response_message'] = parts[1]
                    
                    # Categorize response
                    code_category = code[0]
                    if code_category == '1':
                        metadata['response_type'] = 'preliminary'
                    elif code_category == '2':
                        metadata['response_type'] = 'completion'
                    elif code_category == '3':
                        metadata['response_type'] = 'intermediate'
                    elif code_category == '4':
                        metadata['response_type'] = 'transient_negative'
                    elif code_category == '5':
                        metadata['response_type'] = 'permanent_negative'
                    
                    # Special handling for specific responses
                    if code == '227':  # Entering Passive Mode
                        match = re.search(r'\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)', text)
                        if match:
                            h1, h2, h3, h4, p1, p2 = map(int, match.groups())
                            passive_ip = f"{h1}.{h2}.{h3}.{h4}"
                            passive_port = (p1 * 256) + p2
                            metadata['passive_ip'] = passive_ip
                            metadata['passive_port'] = passive_port
        
        except Exception as e:
            logging.error(f"Error parsing FTP packet: {e}")
            metadata['parse_error'] = str(e)
        
        return metadata
    
    @classmethod
    def get_protocol_name(cls):
        """Get the protocol name."""
        return 'ftp'
