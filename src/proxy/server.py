"""
Protocol Agnostic Proxy Server

This module implements the core proxy server functionality,
handling multiple protocol connections and managing protocol handlers.
"""

import logging
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from src.protocols.base import ProtocolHandlerRegistry
from src.protocols.http import HTTPProtocolHandler
from src.protocols.ftp import FTPProtocolHandler
from src.protocols.dns import DNSProtocolHandler
from src.protocols.telnet import TelnetProtocolHandler


class ProxyServer:
    """Main proxy server class that manages connections and protocol handlers."""
    
    def __init__(self, config):
        """
        Initialize the proxy server with the provided configuration.
        
        Args:
            config (dict): Server configuration dictionary
        """
        self.config = config
        self.server_config = config.get('server', {})
        self.protocol_configs = config.get('protocols', {})
        
        self.host = self.server_config.get('host', '0.0.0.0')
        self.port = self.server_config.get('port', 8080)
        self.max_connections = self.server_config.get('max_connections', 100)
        self.buffer_size = self.server_config.get('buffer_size', 4096)
        self.timeout = self.server_config.get('timeout', 30)
        
        self.running = False
        self.protocol_servers = {}
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_connections)
        
        # Register protocol handlers
        self._register_protocol_handlers()
    
    def _register_protocol_handlers(self):
        """Register all supported protocol handlers."""
        # HTTP
        if self.protocol_configs.get('http', {}).get('enabled', False):
            ProtocolHandlerRegistry.register('http', HTTPProtocolHandler)
            logging.info("Registered HTTP protocol handler")
        
        # FTP
        if self.protocol_configs.get('ftp', {}).get('enabled', False):
            ProtocolHandlerRegistry.register('ftp', FTPProtocolHandler)
            logging.info("Registered FTP protocol handler")
        
        # DNS
        if self.protocol_configs.get('dns', {}).get('enabled', False):
            ProtocolHandlerRegistry.register('dns', DNSProtocolHandler)
            logging.info("Registered DNS protocol handler")
        
        # Telnet
        if self.protocol_configs.get('telnet', {}).get('enabled', False):
            ProtocolHandlerRegistry.register('telnet', TelnetProtocolHandler)
            logging.info("Registered Telnet protocol handler")
    
    def _setup_protocol_servers(self):
        """Set up protocol-specific server sockets."""
        for protocol, config in self.protocol_configs.items():
            if not config.get('enabled', False):
                continue
            
            port = config.get('port')
            if not port:
                logging.warning(f"No port specified for {protocol}, skipping")
                continue
            
            try:
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind((self.host, port))
                server_socket.listen(5)
                server_socket.settimeout(1.0)  # Non-blocking accept for clean shutdown
                
                self.protocol_servers[protocol] = {
                    'socket': server_socket,
                    'config': config,
                    'thread': threading.Thread(
                        target=self._protocol_server_loop,
                        args=(protocol, server_socket, config),
                        daemon=True
                    )
                }
                
                logging.info(f"Created server for {protocol} protocol on port {port}")
            except Exception as e:
                logging.error(f"Failed to set up {protocol} server on port {port}: {e}")
    
    def _protocol_server_loop(self, protocol_name, server_socket, protocol_config):
        """
        Main loop for each protocol-specific server.
        
        Args:
            protocol_name (str): Name of the protocol
            server_socket (socket.socket): Server socket for the protocol
            protocol_config (dict): Protocol-specific configuration
        """
        logging.info(f"Starting server loop for {protocol_name} protocol")
        
        while self.running:
            try:
                client_socket, client_address = server_socket.accept()
                logging.info(f"Accepted {protocol_name} connection from {client_address}")
                
                # Get the protocol handler class
                handler_class = ProtocolHandlerRegistry.get_handler(protocol_name)
                if not handler_class:
                    logging.error(f"No handler registered for {protocol_name} protocol")
                    client_socket.close()
                    continue
                
                # Create a handler instance and handle the connection in the thread pool
                handler = handler_class(
                    client_socket, 
                    client_address,
                    protocol_config,
                    self.config.get('inspection', {})
                )
                
                self.thread_pool.submit(handler.handle_connection)
            
            except socket.timeout:
                # This is expected due to the non-blocking socket
                continue
            except Exception as e:
                if self.running:  # Only log if not shutting down
                    logging.error(f"Error in {protocol_name} server loop: {e}")
    
    def start(self):
        """Start the proxy server."""
        logging.info("Starting proxy server...")
        self.running = True
        
        # Set up protocol servers
        self._setup_protocol_servers()
        
        # Start protocol server threads
        for protocol, server_info in self.protocol_servers.items():
            server_info['thread'].start()
            logging.info(f"Started {protocol} protocol server")
        
        logging.info(f"Proxy server running on {self.host}")
        
        # Keep the main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        """Shutdown the proxy server gracefully."""
        logging.info("Shutting down proxy server...")
        self.running = False
        
        # Close all protocol server sockets
        for protocol, server_info in self.protocol_servers.items():
            try:
                server_info['socket'].close()
                logging.info(f"Closed {protocol} server socket")
            except Exception as e:
                logging.error(f"Error closing {protocol} server socket: {e}")
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=False)
        logging.info("Proxy server shutdown complete")
