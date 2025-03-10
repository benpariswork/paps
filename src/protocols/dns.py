"""
DNS Protocol Handler

This module implements the DNS protocol handler for the Protocol Agnostic Proxy Server.
"""

import logging
import socket
import struct
import time

from src.protocols.base import BaseProtocolHandler


class DNSProtocolHandler(BaseProtocolHandler):
    """Handler for DNS protocol."""
    
    def __init__(self, client_socket, client_address, protocol_config, inspection_config):
        """Initialize the DNS protocol handler."""
        super().__init__(client_socket, client_address, protocol_config, inspection_config)
        self.target_host = None
        self.target_port = 53  # Default DNS port
    
    def _setup_server_connection(self):
        """Set up the connection to the destination DNS server."""
        target_config = self.protocol_config.get('target', {})
        self.target_host = target_config.get('host', '8.8.8.8')  # Default to Google DNS
        self.target_port = target_config.get('port', 53)
        
        logging.info(f"DNS connection to {self.target_host}:{self.target_port}")
        
        # For DNS, we use UDP by default
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    def _proxy_data(self):
        """Proxy data between client and server for DNS."""
        # For DNS, we don't need to keep the connection open like TCP
        # Instead, we handle individual requests and responses
        
        while self.running:
            try:
                # Set a timeout to allow for clean shutdown
                self.client_socket.settimeout(0.1)
                
                # Receive data from client
                data, client_addr = self.client_socket.recvfrom(self.buffer_size)
                if not data:
                    break
                
                # Process the packet if inspection is enabled
                if self.should_inspect_packet(data, 'client_to_server'):
                    packet = self.create_packet(data, 'client_to_server')
                    self.log_packet(packet)
                    
                    # If packet is paused, we'll need a mechanism to wait for resumption
                    # For now, we'll just log it and continue
                    if packet.paused:
                        logging.info(f"Packet {packet.id} paused (client to server)")
                        # In a real implementation, we would wait here
                
                # Forward to DNS server
                self.server_socket.sendto(data, (self.target_host, self.target_port))
                
                # Receive response from DNS server
                self.server_socket.settimeout(5.0)  # DNS response timeout
                response, _ = self.server_socket.recvfrom(self.buffer_size)
                
                # Process the packet if inspection is enabled
                if self.should_inspect_packet(response, 'server_to_client'):
                    packet = self.create_packet(response, 'server_to_client')
                    self.log_packet(packet)
                    
                    # If packet is paused, we'll need a mechanism to wait for resumption
                    # For now, we'll just log it and continue
                    if packet.paused:
                        logging.info(f"Packet {packet.id} paused (server to client)")
                        # In a real implementation, we would wait here
                
                # Forward response to client
                self.client_socket.sendto(response, client_addr)
            
            except socket.timeout:
                # This is expected due to the non-blocking socket
                continue
            except ConnectionResetError:
                logging.warning("Connection reset")
                break
            except Exception as e:
                logging.error(f"Error in DNS proxy loop: {e}")
                break
    
    def parse_packet(self, data, direction):
        """
        Parse a DNS packet.
        
        Args:
            data (bytes): Raw packet data
            direction (str): Direction of the packet
            
        Returns:
            dict: Parsed packet metadata
        """
        metadata = {}
        
        try:
            # Parse DNS header
            if len(data) < 12:
                metadata['error'] = 'Packet too short for DNS header'
                return metadata
            
            # Extract header fields
            (id, flags, qdcount, ancount, nscount, arcount) = struct.unpack('!HHHHHH', data[:12])
            
            metadata['transaction_id'] = id
            metadata['query_count'] = qdcount
            metadata['answer_count'] = ancount
            metadata['authority_count'] = nscount
            metadata['additional_count'] = arcount
            
            # Decode flags
            qr = (flags >> 15) & 0x1
            opcode = (flags >> 11) & 0xF
            aa = (flags >> 10) & 0x1
            tc = (flags >> 9) & 0x1
            rd = (flags >> 8) & 0x1
            ra = (flags >> 7) & 0x1
            z = (flags >> 4) & 0x7
            rcode = flags & 0xF
            
            metadata['is_response'] = bool(qr)
            metadata['opcode'] = opcode
            metadata['authoritative'] = bool(aa)
            metadata['truncated'] = bool(tc)
            metadata['recursion_desired'] = bool(rd)
            metadata['recursion_available'] = bool(ra)
            metadata['response_code'] = rcode
            
            # Map opcode to readable name
            opcode_map = {
                0: 'QUERY',
                1: 'IQUERY',
                2: 'STATUS',
                3: 'NOTIFY',
                4: 'UPDATE'
            }
            metadata['opcode_name'] = opcode_map.get(opcode, f'UNKNOWN ({opcode})')
            
            # Map response code to readable name
            rcode_map = {
                0: 'NOERROR',
                1: 'FORMERR',
                2: 'SERVFAIL',
                3: 'NXDOMAIN',
                4: 'NOTIMP',
                5: 'REFUSED'
            }
            metadata['response_code_name'] = rcode_map.get(rcode, f'UNKNOWN ({rcode})')
            
            # Attempt to extract the query name for queries
            if qdcount > 0:
                # Parse the domain name
                offset = 12  # Start after the header
                domain_parts = []
                
                while True:
                    length = data[offset]
                    offset += 1
                    
                    if length == 0:
                        break
                    
                    domain_part = data[offset:offset+length].decode('utf-8', errors='ignore')
                    domain_parts.append(domain_part)
                    offset += length
                
                domain_name = '.'.join(domain_parts)
                metadata['query_name'] = domain_name
                
                # Extract query type and class
                if offset + 4 <= len(data):
                    qtype, qclass = struct.unpack('!HH', data[offset:offset+4])
                    offset += 4
                    
                    # Map query type to readable name
                    qtype_map = {
                        1: 'A',
                        2: 'NS',
                        5: 'CNAME',
                        6: 'SOA',
                        12: 'PTR',
                        15: 'MX',
                        16: 'TXT',
                        28: 'AAAA',
                        33: 'SRV',
                        255: 'ANY'
                    }
                    metadata['query_type'] = qtype_map.get(qtype, f'TYPE{qtype}')
                    
                    # Map query class to readable name
                    qclass_map = {
                        1: 'IN',
                        2: 'CS',
                        3: 'CH',
                        4: 'HS',
                        255: 'ANY'
                    }
                    metadata['query_class'] = qclass_map.get(qclass, f'CLASS{qclass}')
            
            # For responses, try to extract answer records
            if qr and ancount > 0:
                metadata['answers'] = []
                # Parsing answer records is more complex due to DNS name compression
                # This is a simplified implementation
                
                # Skip the question section
                offset = 12  # Start after the header
                
                # Skip over questions
                for _ in range(qdcount):
                    # Skip the domain name
                    while offset < len(data):
                        length = data[offset]
                        offset += 1
                        
                        if length == 0:
                            break
                        
                        if (length & 0xC0) == 0xC0:
                            # Compressed name, skip one more byte
                            offset += 1
                            break
                        
                        offset += length
                    
                    # Skip type and class
                    offset += 4
                
                # Now we're at the answer section
                # This is a simplified implementation that just counts the answers
                metadata['answers_parsed'] = min(ancount, 10)  # Limit to 10 answers for brevity
        
        except Exception as e:
            logging.error(f"Error parsing DNS packet: {e}")
            metadata['parse_error'] = str(e)
        
        return metadata
    
    @classmethod
    def get_protocol_name(cls):
        """Get the protocol name."""
        return 'dns'
