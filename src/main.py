#!/usr/bin/env python3
"""
Protocol Agnostic Proxy Server - Entry Point

This module serves as the main entry point for the Protocol Agnostic Proxy Server.
It initializes the configuration, sets up the logging system, and starts the proxy server.
"""

import os
import sys
import yaml
import argparse
import logging
import signal
from pathlib import Path

# Add the parent directory to sys.path to allow for imports from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.proxy.server import ProxyServer
from src.logging.elasticsearch import setup_elasticsearch_logging


def load_config(config_path):
    """Load configuration from a YAML file."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        sys.exit(1)


def setup_logging(config):
    """Set up the logging system based on the configuration."""
    logging_config = config.get('logging', {})
    
    # Set up file logging
    file_config = logging_config.get('file', {})
    if file_config.get('enabled', False):
        log_path = file_config.get('path', 'logs/proxy.log')
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        level = getattr(logging, file_config.get('level', 'INFO'))
        logging.basicConfig(
            filename=log_path,
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Set up Elasticsearch logging
    es_config = logging_config.get('elasticsearch', {})
    if es_config.get('enabled', False):
        setup_elasticsearch_logging(es_config)
    
    logging.info("Logging system initialized")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Protocol Agnostic Proxy Server')
    parser.add_argument(
        '-c', '--config',
        default='config/config.yaml',
        help='Path to the configuration file'
    )
    return parser.parse_args()


def handle_signals(proxy_server):
    """Set up signal handlers for graceful shutdown."""
    def signal_handler(sig, frame):
        logging.info(f"Received signal {sig}, shutting down...")
        proxy_server.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def main():
    """Main entry point for the application."""
    args = parse_args()
    config = load_config(args.config)
    setup_logging(config)
    
    logging.info("Starting Protocol Agnostic Proxy Server...")
    
    # Ensure packet storage directory exists
    packet_storage_path = config.get('inspection', {}).get('packet_storage_path', 'data/packets')
    os.makedirs(packet_storage_path, exist_ok=True)
    
    # Initialize and start the proxy server
    proxy_server = ProxyServer(config)
    handle_signals(proxy_server)
    
    try:
        proxy_server.start()
    except Exception as e:
        logging.error(f"Error starting proxy server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
