"""
Elasticsearch Logging Module

This module provides Elasticsearch integration for logging in the 
Protocol Agnostic Proxy Server.
"""

import logging
import datetime
import queue
import threading
import time
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import json


# Global Elasticsearch client
es_client = None

# Batch processing queue
packet_queue = queue.Queue()

# Logger
logger = logging.getLogger(__name__)


def setup_elasticsearch_logging(config):
    """
    Set up Elasticsearch logging.
    
    Args:
        config (dict): Elasticsearch configuration
    """
    global es_client
    
    try:
        hosts = config.get('hosts', ['http://localhost:9200'])
        
        # Initialize Elasticsearch client
        es_client = Elasticsearch(hosts)
        
        # Test connection
        if es_client.ping():
            logger.info("Connected to Elasticsearch")
        else:
            logger.warning("Failed to connect to Elasticsearch, logging will be disabled")
            es_client = None
            return
        
        # Start background thread for batch processing
        batch_size = config.get('batch_size', 100)
        flush_interval = config.get('flush_interval', 5)
        
        batch_thread = threading.Thread(
            target=_batch_processor,
            args=(batch_size, flush_interval, config.get('index_prefix', 'proxy-logs')),
            daemon=True
        )
        batch_thread.start()
        
        logger.info(f"Elasticsearch logging initialized with batch size {batch_size} and flush interval {flush_interval}s")
    
    except Exception as e:
        logger.error(f"Failed to set up Elasticsearch logging: {e}")
        es_client = None


def log_packet_to_elasticsearch(packet):
    """
    Log a packet to Elasticsearch.
    
    Args:
        packet: Packet object to log
    """
    if es_client is None:
        return
    
    try:
        # Add packet to queue for batch processing
        packet_queue.put(packet)
    except Exception as e:
        logger.error(f"Failed to queue packet for Elasticsearch logging: {e}")


def _batch_processor(batch_size, flush_interval, index_prefix):
    """
    Background thread function for batch processing packets.
    
    Args:
        batch_size (int): Maximum number of packets to batch
        flush_interval (int): Maximum time to wait before flushing in seconds
        index_prefix (str): Prefix for Elasticsearch indices
    """
    batch = []
    last_flush = time.time()
    
    while True:
        try:
            # Try to get a packet with timeout
            try:
                packet = packet_queue.get(timeout=0.1)
                
                # Convert packet to Elasticsearch document
                doc = _packet_to_document(packet, index_prefix)
                batch.append(doc)
                
                packet_queue.task_done()
            except queue.Empty:
                # No packet available, check if we need to flush based on time
                pass
            
            # Flush if batch is full or timer expired
            if len(batch) >= batch_size or (time.time() - last_flush > flush_interval and batch):
                _flush_batch(batch)
                batch = []
                last_flush = time.time()
        
        except Exception as e:
            logger.error(f"Error in Elasticsearch batch processor: {e}")
            time.sleep(1)  # Avoid tight loop in case of persistent errors


def _packet_to_document(packet, index_prefix):
    """
    Convert a packet to an Elasticsearch document.
    
    Args:
        packet: Packet object
        index_prefix (str): Prefix for Elasticsearch indices
        
    Returns:
        dict: Elasticsearch document
    """
    # Convert packet to dictionary
    packet_dict = packet.to_dict()
    
    # Format timestamp for index name
    timestamp = datetime.datetime.fromtimestamp(packet.timestamp)
    date_str = timestamp.strftime('%Y.%m.%d')
    
    # Create index name based on protocol and date
    index_name = f"{index_prefix}-{packet.protocol}-{date_str}"
    
    # Create Elasticsearch action
    action = {
        '_index': index_name,
        '_source': packet_dict
    }
    
    return action


def _flush_batch(batch):
    """
    Flush a batch of documents to Elasticsearch.
    
    Args:
        batch (list): List of Elasticsearch actions
    """
    if not batch or es_client is None:
        return
    
    try:
        # Use bulk API to insert documents
        success, errors = bulk(es_client, batch, refresh=True, stats_only=True)
        logger.debug(f"Inserted {success} documents into Elasticsearch, {errors} errors")
    
    except Exception as e:
        logger.error(f"Failed to flush batch to Elasticsearch: {e}")
