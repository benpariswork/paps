"""
Protocol Handlers Package

This package contains protocol-specific handlers for the Protocol Agnostic Proxy Server.
"""

from src.protocols.base import BaseProtocolHandler, ProtocolHandlerRegistry
from src.protocols.http import HTTPProtocolHandler
from src.protocols.ftp import FTPProtocolHandler
from src.protocols.dns import DNSProtocolHandler
from src.protocols.telnet import TelnetProtocolHandler

__all__ = [
    'BaseProtocolHandler',
    'ProtocolHandlerRegistry',
    'HTTPProtocolHandler',
    'FTPProtocolHandler',
    'DNSProtocolHandler',
    'TelnetProtocolHandler'
]
