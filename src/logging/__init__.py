"""
Logging Package

This package contains logging functionality for the Protocol Agnostic Proxy Server.
"""

from src.logging.elasticsearch import setup_elasticsearch_logging, log_packet_to_elasticsearch

__all__ = [
    'setup_elasticsearch_logging',
    'log_packet_to_elasticsearch'
]
