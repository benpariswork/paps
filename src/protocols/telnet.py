"""
Telnet Protocol Handler

This module implements the Telnet protocol handler for the Protocol Agnostic Proxy Server.
"""

import logging
import socket
import select

from src.protocols.base import BaseProtocolHandler


class TelnetProtocolHandler(BaseProtocolHandler):
    """Handler for Telnet protocol."""
    
    # Telnet command codes
    IAC = 255  # Interpret As Command
    DONT = 254
    DO = 253
    WONT = 252
    WILL = 251
    SB = 250  # Subnegotiation Begin
    SE = 240  # Subnegotiation End
    
    # Telnet option codes
    OPT_ECHO = 1
    OPT_SGA = 3
    OPT_TERM_TYPE = 24
    OPT_NAWS = 31
    OPT_TERM_SPEED = 32
    OPT_LINEMODE = 34
    OPT_ENV_VARS = 36
    
    def __init__(self, client_socket, client_address, protocol_config, inspection_config):
        """Initialize the Telnet protocol handler."""
        super().__init__(client_socket, client_address, protocol_config, inspection_config)
        self.target_host = None
        self.target_port = 23  # Default Telnet port
    
    def _setup_server_connection(self):
        """Set up the connection to the destination Telnet server."""
        target_config = self.protocol_config.get('target', {})
        self.target_host = target_config.get('host', '127.0.0.1')
        self.target_port = target_config.get('port', 23)
        
        logging.info(f"Telnet connection to {self.target_host}:{self.target_port}")
        
        # Connect to the Telnet server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.connect((self.target_host, self.target_port))
    
    def _proxy_data(self):
        """Proxy data between client and server for Telnet."""
        # Adjust socket timeouts for better interactivity
        self.client_socket.settimeout(0.1)
        self.server_socket.settimeout(0.1)
        
        # Set up for select
        sockets = [self.client_socket, self.server_socket]
        
        # Buffer for telnet command processing
        client_buffer = b''
        server_buffer = b''
        
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
                        
                        # Process telnet commands if any
                        client_buffer += data
                        processed_data, client_buffer = self._process_telnet_commands(
                            client_buffer, 'client_to_server')
                        
                        if processed_data:
                            # Process the packet if inspection is enabled
                            if self.should_inspect_packet(processed_data, 'client_to_server'):
                                packet = self.create_packet(processed_data, 'client_to_server')
                                self.log_packet(packet)
                                
                                # If packet is paused, we'll need a mechanism to wait for resumption
                                if packet.paused:
                                    logging.info(f"Packet {packet.id} paused (client to server)")
                                    # In a real implementation, we would wait here
                            
                            # Forward data to server
                            self.server_socket.sendall(processed_data)
                    
                    elif sock is self.server_socket:
                        # Handle server to client data
                        data = sock.recv(self.buffer_size)
                        if not data:
                            self.running = False
                            break
                        
                        # Process telnet commands if any
                        server_buffer += data
                        processed_data, server_buffer = self._process_telnet_commands(
                            server_buffer, 'server_to_client')
                        
                        if processed_data:
                            # Process the packet if inspection is enabled
                            if self.should_inspect_packet(processed_data, 'server_to_client'):
                                packet = self.create_packet(processed_data, 'server_to_client')
                                self.log_packet(packet)
                                
                                # If packet is paused, we'll need a mechanism to wait for resumption
                                if packet.paused:
                                    logging.info(f"Packet {packet.id} paused (server to client)")
                                    # In a real implementation, we would wait here
                            
                            # Forward data to client
                            self.client_socket.sendall(processed_data)
            
            except socket.timeout:
                # This is expected due to the non-blocking sockets
                continue
            except ConnectionResetError:
                logging.warning("Connection reset")
                break
            except Exception as e:
                logging.error(f"Error in proxy loop: {e}")
                break
    
    def _process_telnet_commands(self, buffer, direction):
        """
        Process Telnet commands in the buffer.
        
        Args:
            buffer (bytes): Buffer containing telnet data
            direction (str): Direction of the data flow
            
        Returns:
            tuple: (processed_data, remaining_buffer)
        """
        # If no IAC byte is found, return the buffer as is
        if self.IAC not in buffer:
            return buffer, b''
        
        # Process Telnet commands
        # This is a simplistic implementation that just identifies command sequences
        # A full implementation would interpret and potentially modify commands
        
        processed_data = b''
        i = 0
        
        while i < len(buffer):
            # If we don't have an IAC or we're at the end of the buffer
            if buffer[i] != self.IAC or i >= len(buffer) - 1:
                processed_data += bytes([buffer[i]])
                i += 1
                continue
            
            # We have an IAC and at least one more byte
            command = buffer[i+1]
            
            # Simple option negotiation (DO, DONT, WILL, WONT)
            if command in [self.DO, self.DONT, self.WILL, self.WONT] and i < len(buffer) - 2:
                option = buffer[i+2]
                logging.debug(f"Telnet command: IAC {command} {option}")
                processed_data += bytes([self.IAC, command, option])
                i += 3
                continue
            
            # Subnegotiation
            if command == self.SB:
                # Look for the end of subnegotiation (IAC SE)
                j = i + 2
                while j < len(buffer) - 1:
                    if buffer[j] == self.IAC and buffer[j+1] == self.SE:
                        break
                    j += 1
                
                if j < len(buffer) - 1:
                    # We found the end of subnegotiation
                    subneg_data = buffer[i:j+2]
                    logging.debug(f"Telnet subnegotiation: {subneg_data}")
                    processed_data += subneg_data
                    i = j + 2
                else:
                    # Incomplete subnegotiation, keep in buffer
                    remaining_buffer = buffer[i:]
                    return processed_data, remaining_buffer
            
            # Other commands (single byte commands like IAC NOP)
            else:
                logging.debug(f"Telnet command: IAC {command}")
                processed_data += bytes([self.IAC, command])
                i += 2
        
        return processed_data, b''
    
    def parse_packet(self, data, direction):
        """
        Parse a Telnet packet.
        
        Args:
            data (bytes): Raw packet data
            direction (str): Direction of the packet
            
        Returns:
            dict: Parsed packet metadata
        """
        metadata = {}
        
        try:
            # Scan for telnet command sequences
            i = 0
            commands = []
            
            while i < len(data):
                if data[i] == self.IAC and i < len(data) - 1:
                    cmd = data[i+1]
                    cmd_name = self._get_command_name(cmd)
                    
                    if cmd in [self.DO, self.DONT, self.WILL, self.WONT] and i < len(data) - 2:
                        opt = data[i+2]
                        opt_name = self._get_option_name(opt)
                        commands.append(f"IAC {cmd_name} {opt_name}")
                        i += 3
                    elif cmd == self.SB and i < len(data) - 2:
                        # Extract subnegotiation data
                        sub_opt = data[i+2]
                        sub_opt_name = self._get_option_name(sub_opt)
                        
                        # Look for end of subnegotiation
                        j = i + 3
                        while j < len(data) - 1:
                            if data[j] == self.IAC and data[j+1] == self.SE:
                                break
                            j += 1
                        
                        if j < len(data) - 1:
                            sub_data = data[i+3:j]
                            commands.append(f"IAC SB {sub_opt_name} {sub_data.hex()} IAC SE")
                            i = j + 2
                        else:
                            commands.append(f"IAC SB {sub_opt_name} [incomplete]")
                            i = len(data)
                    else:
                        commands.append(f"IAC {cmd_name}")
                        i += 2
                else:
                    i += 1
            
            # Count commands
            metadata['command_count'] = len(commands)
            
            # Include command details if any
            if commands:
                metadata['commands'] = commands[:10]  # Limit to 10 for brevity
                if len(commands) > 10:
                    metadata['additional_commands'] = len(commands) - 10
            
            # Basic text content analysis
            # Filter out control characters for display
            displayable = bytes([b for b in data if b >= 32 and b < 127 or b in [9, 10, 13]])
            text = displayable.decode('ascii', errors='ignore')
            
            # Strip excessive whitespace for display
            text = ' '.join(text.split())
            if text:
                metadata['text_preview'] = text[:100]
                if len(text) > 100:
                    metadata['text_preview'] += '...'
        
        except Exception as e:
            logging.error(f"Error parsing Telnet packet: {e}")
            metadata['parse_error'] = str(e)
        
        return metadata
    
    def _get_command_name(self, cmd):
        """Get the name of a Telnet command."""
        cmd_names = {
            self.DO: 'DO',
            self.DONT: 'DONT',
            self.WILL: 'WILL',
            self.WONT: 'WONT',
            self.SB: 'SB',
            self.SE: 'SE'
        }
        return cmd_names.get(cmd, f"{cmd}")
    
    def _get_option_name(self, opt):
        """Get the name of a Telnet option."""
        opt_names = {
            self.OPT_ECHO: 'ECHO',
            self.OPT_SGA: 'SGA',
            self.OPT_TERM_TYPE: 'TERM_TYPE',
            self.OPT_NAWS: 'NAWS',
            self.OPT_TERM_SPEED: 'TERM_SPEED',
            self.OPT_LINEMODE: 'LINEMODE',
            self.OPT_ENV_VARS: 'ENV_VARS'
        }
        return opt_names.get(opt, f"{opt}")
    
    @classmethod
    def get_protocol_name(cls):
        """Get the protocol name."""
        return 'telnet'
