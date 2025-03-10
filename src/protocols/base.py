"""
Base Protocol Handler Module

This module defines the base protocol handler class and registry for
the Protocol Agnostic Proxy Server.
"""

import logging
import socket
import time
import uuid
from abc import ABC, abstractmethod


class ProtocolHandlerRegistry:
    """Registry for protocol handlers."""
    
    _handlers = {}
    
    @classmethod
    def register(cls, protocol_name, handler_class):
        """
        Register a protocol handler class.
        
        Args:
            protocol_name (str): Name of the protocol
            handler_class (class): Protocol handler class
        """
        cls._handlers[protocol_name] = handler_class
    
    @classmethod
    def get_handler(cls, protocol_name):
        """
        Get a protocol handler class by name.
        
        Args:
            protocol_name (str): Name of the protocol
            
        Returns:
            class: Protocol handler class or None if not found
        """
        return cls._handlers.get(protocol_name)


class Packet:
    """Class representing a network packet."""
    
    def __init__(self, data, source, destination, protocol):
        """
        Initialize a packet.
        
        Args:
            data (bytes): Raw packet data
            source (tuple): Source address (IP, port)
            destination (tuple): Destination address (IP, port)
            protocol (str): Protocol name
        """
        self.id = str(uuid.uuid4())
        self.timestamp = time.time()
        self.data = data
        self.source = source
        self.destination = destination
        self.protocol = protocol
        self.paused = False
        self.metadata = {}
    
    def to_dict(self):
        """Convert packet to dictionary representation."""
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'source': self.source,
            'destination': self.destination,
            'protocol': self.protocol,
            'data_hex': self.data.hex(),
            'data_length': len(self.data),
            'paused': self.paused,
            'metadata': self.metadata
        }


class BaseProtocolHandler(ABC):
    """Base class for all protocol handlers."""
    
    def __init__(self, client_socket, client_address, protocol_config, inspection_config):
        """
        Initialize the protocol handler.
        
        Args:
            client_socket (socket.socket): Client socket
            client_address (tuple): Client address (IP, port)
            protocol_config (dict): Protocol-specific configuration
            inspection_config (dict): Inspection configuration
        """
        self.client_socket = client_socket
        self.client_address = client_address
        self.protocol_config = protocol_config
        self.inspection_config = inspection_config
        
        self.buffer_size = protocol_config.get('buffer_size', 4096)
        self.inspection_mode = protocol_config.get('inspection_mode', 'both')
        self.pause_by_default = inspection_config.get('pause_by_default', False)
        
        self.server_socket = None
        self.running = False
    
    def handle_connection(self):
        """Handle the client connection."""
        try:
            self.running = True
            self._setup_server_connection()
            self._proxy_data()
        except Exception as e:
            logging.error(f"Error handling connection: {e}")
        finally:
            self._cleanup()
    
    def _setup_server_connection(self):
        """Set up the connection to the destination server."""
        # This is a simple implementation that needs to be overridden
        # by protocol-specific handlers
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    def _proxy_data(self):
        """Proxy data between client and server."""
        # This method should be implemented by subclasses
        pass
    
    def _cleanup(self):
        """Clean up resources."""
        logging.info(f"Cleaning up connection from {self.client_address}")
        self.running = False
        
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
    
    @abstractmethod
    def parse_packet(self, data, direction):
        """
        Parse a packet according to the protocol.
        
        Args:
            data (bytes): Raw packet data
            direction (str): Direction of the packet ('client_to_server' or 'server_to_client')
            
        Returns:
            dict: Parsed packet metadata
        """
        pass
    
    def should_inspect_packet(self, data, direction):
        """
        Determine if a packet should be inspected.
        
        Args:
            data (bytes): Raw packet data
            direction (str): Direction of the packet
            
        Returns:
            bool: True if the packet should be inspected, False otherwise
        """
        # This method can be overridden by subclasses to implement
        # protocol-specific inspection rules
        return True
    
    def create_packet(self, data, direction):
        """
        Create a Packet object.
        
        Args:
            data (bytes): Raw packet data
            direction (str): Direction of the packet
            
        Returns:
            Packet: Packet object
        """
        if direction == 'client_to_server':
            source = self.client_address
            destination = self.server_socket.getpeername()
        else:
            source = self.server_socket.getpeername()
            destination = self.client_address
        
        packet = Packet(data, source, destination, self.get_protocol_name())
        
        # Add parsed metadata if inspection mode includes 'parsed'
        if self.inspection_mode in ['parsed', 'both']:
            packet.metadata = self.parse_packet(data, direction)
        
        # Set paused state based on configuration
        packet.paused = self.pause_by_default
        
        return packet
    
    def log_packet(self, packet):
        """
        Log a packet.
        
        Args:
            packet (Packet): Packet to log
        """
        # Basic logging - subclasses may enhance this
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f"Packet: {packet.to_dict()}")
        else:
            logging.info(
                f"Packet: {packet.protocol} {packet.source} -> {packet.destination} "
                f"Length: {len(packet.data)} bytes"
            )
    
    @classmethod
    def get_protocol_name(cls):
        """Get the name of the protocol handled by this handler."""
        # Default implementation uses the class name
        return cls.__name__.replace('ProtocolHandler', '').lower()
