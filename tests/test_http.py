"""
Unit tests for the HTTP protocol handler.
"""

import unittest
import socket
import threading
import time
import sys
import os
from unittest.mock import MagicMock, patch

# Add the parent directory to sys.path to allow for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.protocols.http import HTTPProtocolHandler
from src.protocols.base import Packet


class TestHTTPProtocolHandler(unittest.TestCase):
    """Test cases for the HTTP protocol handler."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock sockets
        self.client_socket = MagicMock(spec=socket.socket)
        self.server_socket = MagicMock(spec=socket.socket)
        
        # Mock client address
        self.client_address = ('127.0.0.1', 12345)
        
        # Create protocol config
        self.protocol_config = {
            'port': 8080,
            'inspection_mode': 'both',
            'buffer_size': 4096
        }
        
        # Create inspection config
        self.inspection_config = {
            'pause_by_default': False,
            'save_captured_packets': True,
            'packet_storage_path': 'data/packets'
        }
        
        # Create HTTP handler with mocked sockets
        self.http_handler = HTTPProtocolHandler(
            self.client_socket,
            self.client_address,
            self.protocol_config,
            self.inspection_config
        )
        
        # Replace server socket creation method
        self.http_handler._setup_server_connection = MagicMock()
        self.http_handler.server_socket = self.server_socket
        
        # Sample HTTP request and response
        self.sample_request = (
            b'GET /index.html HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'User-Agent: Mozilla/5.0\r\n'
            b'Accept: text/html\r\n'
            b'\r\n'
        )
        
        self.sample_response = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/html\r\n'
            b'Content-Length: 13\r\n'
            b'\r\n'
            b'Hello, World!'
        )
    
    def test_parse_request(self):
        """Test parsing an HTTP request."""
        metadata = self.http_handler.parse_packet(self.sample_request, 'client_to_server')
        
        # Verify parsed metadata
        self.assertEqual(metadata.get('method'), 'GET')
        self.assertEqual(metadata.get('path'), '/index.html')
        self.assertEqual(metadata.get('version'), 'HTTP/1.1')
        self.assertEqual(metadata.get('headers', {}).get('Host'), 'example.com')
        self.assertEqual(metadata.get('headers', {}).get('User-Agent'), 'Mozilla/5.0')
        self.assertEqual(metadata.get('headers', {}).get('Accept'), 'text/html')
    
    def test_parse_response(self):
        """Test parsing an HTTP response."""
        metadata = self.http_handler.parse_packet(self.sample_response, 'server_to_client')
        
        # Verify parsed metadata
        self.assertEqual(metadata.get('version'), 'HTTP/1.1')
        self.assertEqual(metadata.get('status_code'), '200')
        self.assertEqual(metadata.get('status_message'), 'OK')
        self.assertEqual(metadata.get('headers', {}).get('Content-Type'), 'text/html')
        self.assertEqual(metadata.get('headers', {}).get('Content-Length'), '13')
        self.assertEqual(metadata.get('body_length'), 13)
    
    def test_get_protocol_name(self):
        """Test getting the protocol name."""
        self.assertEqual(self.http_handler.get_protocol_name(), 'http')
    
    @patch('src.protocols.base.Packet')
    def test_create_packet(self, mock_packet):
        """Test creating a packet."""
        # Setup mock
        mock_packet.return_value = MagicMock(spec=Packet)
        
        # Test client to server
        self.server_socket.getpeername.return_value = ('example.com', 80)
        packet = self.http_handler.create_packet(self.sample_request, 'client_to_server')
        
        # Verify
        mock_packet.assert_called()
        self.assertEqual(packet.metadata.get('method'), 'GET')
    
    def test_should_inspect_packet(self):
        """Test the should_inspect_packet method."""
        # By default, all packets should be inspected
        self.assertTrue(self.http_handler.should_inspect_packet(self.sample_request, 'client_to_server'))
        self.assertTrue(self.http_handler.should_inspect_packet(self.sample_response, 'server_to_client'))


if __name__ == '__main__':
    unittest.main()
