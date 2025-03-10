"""
Packet Module

This module defines the Packet class for handling network packets
in the Protocol Agnostic Proxy Server.
"""

import uuid
import time
import json
import os
import logging
from pathlib import Path


class Packet:
    """Class representing a network packet."""
    
    def __init__(self, data, source, destination, protocol, direction):
        """
        Initialize a packet.
        
        Args:
            data (bytes): Raw packet data
            source (tuple): Source address (IP, port)
            destination (tuple): Destination address (IP, port)
            protocol (str): Protocol name
            direction (str): Direction of the packet ('client_to_server' or 'server_to_client')
        """
        self.id = str(uuid.uuid4())
        self.timestamp = time.time()
        self.data = data
        self.source = source
        self.destination = destination
        self.protocol = protocol
        self.direction = direction
        self.paused = False
        self.modified = False
        self.metadata = {}
    
    def to_dict(self):
        """
        Convert packet to dictionary representation.
        
        Returns:
            dict: Dictionary representation of the packet
        """
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'source': self.source,
            'destination': self.destination,
            'protocol': self.protocol,
            'direction': self.direction,
            'data_hex': self.data.hex(),
            'data_length': len(self.data),
            'paused': self.paused,
            'modified': self.modified,
            'metadata': self.metadata
        }
    
    def save(self, storage_path):
        """
        Save the packet to disk.
        
        Args:
            storage_path (str): Path to save the packet
            
        Returns:
            str: Path to the saved packet file
        """
        try:
            # Create a unique filename based on timestamp and ID
            filename = f"{int(self.timestamp)}_{self.protocol}_{self.id}.packet"
            full_path = os.path.join(storage_path, filename)
            
            # Create directory if it doesn't exist
            os.makedirs(storage_path, exist_ok=True)
            
            # Save packet metadata as JSON
            metadata = self.to_dict()
            
            with open(full_path + '.json', 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Save raw packet data as binary file
            with open(full_path + '.bin', 'wb') as f:
                f.write(self.data)
            
            logging.debug(f"Saved packet {self.id} to {full_path}")
            return full_path
        
        except Exception as e:
            logging.error(f"Failed to save packet {self.id}: {e}")
            return None
    
    @classmethod
    def load(cls, packet_path):
        """
        Load a packet from disk.
        
        Args:
            packet_path (str): Path to the packet JSON file
            
        Returns:
            Packet: Loaded packet or None if loading fails
        """
        try:
            # Load packet metadata
            with open(packet_path + '.json', 'r') as f:
                metadata = json.load(f)
            
            # Load raw packet data
            with open(packet_path + '.bin', 'rb') as f:
                data = f.read()
            
            # Create a new packet
            packet = cls(
                data=data,
                source=tuple(metadata['source']),
                destination=tuple(metadata['destination']),
                protocol=metadata['protocol'],
                direction=metadata['direction']
            )
            
            # Restore other attributes
            packet.id = metadata['id']
            packet.timestamp = metadata['timestamp']
            packet.paused = metadata['paused']
            packet.modified = metadata.get('modified', False)
            packet.metadata = metadata['metadata']
            
            return packet
        
        except Exception as e:
            logging.error(f"Failed to load packet from {packet_path}: {e}")
            return None
    
    def set_pause(self, paused=True):
        """
        Set the pause state of the packet.
        
        Args:
            paused (bool): True to pause, False to resume
            
        Returns:
            bool: New pause state
        """
        self.paused = paused
        return self.paused
    
    def modify_data(self, new_data):
        """
        Modify the packet data.
        
        Args:
            new_data (bytes): New packet data
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not isinstance(new_data, bytes):
            return False
        
        self.data = new_data
        self.modified = True
        return True
