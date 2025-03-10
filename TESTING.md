# Protocol Agnostic Proxy Server - Testing Guide

This document provides instructions for testing the Protocol Agnostic Proxy Server with the provided Docker testing environments.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.8+ with virtual environment setup
- The Protocol Agnostic Proxy Server code

## Setting Up the Test Environment

1. Start the Docker test environments:

```bash
docker-compose up -d
```

This will start:
- Elasticsearch and Kibana for logging
- HTTP, FTP, DNS, and Telnet test servers and clients

2. Install the proxy server:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure the proxy server:
   
Edit `config/config.yaml` to set appropriate targets for each protocol.

## Testing the HTTP Protocol Handler

### Setup

1. Start the proxy server:

```bash
python src/main.py
```

2. Configure your browser to use the proxy:
   - Host: localhost
   - Port: 8080 (or as configured in config.yaml)

### Test Cases

1. **Basic HTTP GET**
   - Visit `http://localhost:8081/` in your browser
   - The proxy should intercept and display the request and response
   - Check the logs for detailed packet information

2. **HTTP GET with Parameters**
   - Visit `http://localhost:8081/test-get.html`
   - Click "Send GET Request"
   - Verify that the proxy captures the request with query parameters

3. **HTTP POST with Form Data**
   - Visit `http://localhost:8081/test-post.html`
   - Fill in the form and submit
   - Verify that the proxy captures the POST request with form data

## Testing the FTP Protocol Handler

### Setup

1. Ensure the proxy server is running with FTP protocol enabled
2. Connect to the FTP server through the proxy

### Test Cases

1. **FTP Connection and Authentication**
   ```bash
   # Using the proxy at localhost:2121
   ftp -p localhost 2121
   # Login with:
   # Username: testuser
   # Password: testpass
   ```

2. **Directory Listing**
   ```bash
   ls -la
   ```

3. **File Download**
   ```bash
   get test-file.txt
   ```

4. **File Upload**
   ```bash
   put local-file.txt
   ```

## Testing the DNS Protocol Handler

### Setup

1. Ensure the proxy server is running with DNS protocol enabled
2. Configure your system to use the proxy as DNS server:
   - Temporary: Use specific commands with the proxy address
   - Permanent: Modify system DNS settings

### Test Cases

1. **Simple DNS Query**
   ```bash
   # Using the proxy at localhost:5353
   dig @localhost -p 5353 example.com
   ```

2. **Different Record Types**
   ```bash
   dig @localhost -p 5353 test-txt.example.com TXT
   dig @localhost -p 5353 test-aaaa.example.com AAAA
   dig @localhost -p 5353 test-srv.example.com SRV
   ```

3. **Reverse Lookup**
   ```bash
   dig @localhost -p 5353 -x 127.0.0.1
   ```

## Testing the Telnet Protocol Handler

### Setup

1. Ensure the proxy server is running with Telnet protocol enabled
2. Connect to the Telnet server through the proxy

### Test Cases

1. **Basic Telnet Connection**
   ```bash
   # Using the proxy at localhost:2323
   telnet localhost 2323
   ```

2. **Command Sending**
   - Once connected, send various commands
   - Verify the proxy captures and parses the commands correctly

3. **Protocol Negotiation**
   - Observe the initial telnet negotiation process
   - Check that the proxy handles the telnet control sequences

## Using Elasticsearch for Log Analysis

The Docker environment includes Elasticsearch and Kibana for log analysis.

1. Access Kibana at http://localhost:5601

2. Configure an index pattern:
   - Go to Management > Stack Management > Kibana > Index Patterns
   - Create a new index pattern: `proxy-logs-*`
   - Select `timestamp` as the time field

3. View logs:
   - Go to Discover
   - Select the `proxy-logs-*` index pattern
   - Filter and search for specific protocol logs

## Automated Testing

The project includes basic test scripts for automated testing:

```bash
# Run all tests
pytest

# Run tests for a specific protocol
pytest tests/test_http.py
pytest tests/test_ftp.py
pytest tests/test_dns.py
pytest tests/test_telnet.py

# Run with coverage report
pytest --cov=src
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure the Docker containers are running
   - Check the proxy server is listening on the expected ports
   - Verify no firewall is blocking connections

2. **Protocol Handler Not Working**
   - Ensure the protocol is enabled in the configuration
   - Check for errors in the proxy server logs
   - Verify the target server address in the configuration

3. **Elasticsearch Connection Issues**
   - Ensure Elasticsearch container is running
   - Check the Elasticsearch URL in the configuration
   - Verify Elasticsearch logs for any errors

### Viewing Logs

- Proxy server logs: Check the console output or log file
- Docker container logs:
  ```bash
  docker logs http_server
  docker logs ftp_server
  docker logs dns_server
  docker logs telnet_server
  ```

## Testing Packet Inspection Features

1. **Raw Packet Inspection**
   - Configure `inspection_mode: raw` in config.yaml
   - Run tests and verify raw packet data is captured

2. **Parsed Packet Inspection**
   - Configure `inspection_mode: parsed` in config.yaml
   - Run tests and verify protocol-specific metadata is extracted

3. **Both Modes**
   - Configure `inspection_mode: both` in config.yaml
   - Run tests and verify both raw and parsed data are available

4. **Pause Packets**
   - Configure `pause_by_default: true` in config.yaml
   - Run tests and observe packet flow control
