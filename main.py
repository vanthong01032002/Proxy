from flask import Flask, jsonify, request
import requests
import json
import time
import threading
import re
from datetime import datetime
import logging
import socket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global variable to store proxy data
proxy_data = []
proxy_counter = 0  # Counter for generating proxy IDs

def generate_proxy_id():
    global proxy_counter
    proxy_counter += 1
    return f"PRX{proxy_counter:05d}"

def extract_seconds(message):
    # Extract seconds from message like "proxy nay se die sau 1769s"
    match = re.search(r'(\d+)s', message)
    if match:
        return int(match.group(1))
    return 0

def format_time(seconds):
    # Convert seconds to mm:ss format
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes:02d}:{remaining_seconds:02d}"

def fetch_proxy():
    logger.info("Starting proxy fetch thread")
    while True:
        try:
            logger.info("Fetching new proxy...")
            response = requests.get('https://my-proxy-api.glitch.me/get-proxy?key=bXDwsQColKsxhdBkapdbWw')
            logger.info(f"Response status code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Received data: {data}")
                
                if data.get('status') == 100:
                    # Calculate expiration time
                    seconds = extract_seconds(data['message'])
                    expiration_time = int(time.time()) + seconds
                    
                    # Check if proxy already exists
                    existing_proxy = next((p for p in proxy_data if p['proxyhttp'] == data['proxyhttp']), None)
                    if existing_proxy:
                        # Update existing proxy
                        existing_proxy['expiration_time'] = expiration_time
                        logger.info(f"Updated expiration time for proxy {existing_proxy['id']}")
                    else:
                        # Create new proxy
                        proxy_info = {
                            'id': generate_proxy_id(),
                            'proxyhttp': data['proxyhttp'],
                            'proxysocks5': data['proxysocks5'],
                            'expiration_time': expiration_time,
                            'location': data['Vi Tri'],
                            'provider': data['Nha Mang'],
                            'status': []
                        }
                        proxy_data.append(proxy_info)
                        logger.info(f"Added new proxy: {proxy_info}")
                    
                    # Save to data.txt
                    with open('data.txt', 'w', encoding='utf-8') as f:
                        json.dump(proxy_data, f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"Total proxies in memory: {len(proxy_data)}")
                else:
                    logger.warning(f"Invalid status in response: {data.get('status')}")
            else:
                logger.error(f"Failed to fetch proxy. Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching proxy: {str(e)}")
        
        logger.info("Waiting 60 seconds before next fetch...")
        time.sleep(60)

def cleanup_expired_proxies():
    logger.info("Starting cleanup thread")
    while True:
        try:
            current_time = int(time.time())
            global proxy_data
            initial_count = len(proxy_data)
            proxy_data = [proxy for proxy in proxy_data if proxy['expiration_time'] > current_time]
            
            if len(proxy_data) != initial_count:
                logger.info(f"Removed {initial_count - len(proxy_data)} expired proxies")
            
            # Update data.txt
            with open('data.txt', 'w', encoding='utf-8') as f:
                json.dump(proxy_data, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"Error in cleanup: {str(e)}")
        
        time.sleep(10)

@app.route('/api/get_proxy')
def get_proxy():
    current_time = int(time.time())
    active_proxies = []
    
    logger.info(f"Current proxy count: {len(proxy_data)}")
    
    for proxy in proxy_data:
        if proxy['expiration_time'] > current_time:
            # Generate ID if not exists
            if 'id' not in proxy:
                proxy['id'] = generate_proxy_id()
                logger.info(f"Generated new ID {proxy['id']} for proxy {proxy['proxyhttp']}")
            
            remaining_seconds = proxy['expiration_time'] - current_time
            active_proxies.append({
                'id': proxy['id'],
                'proxy': proxy['proxyhttp'],
                'time': format_time(remaining_seconds),
                'location': proxy['location'],
                'provider': proxy['provider'],
                'status': proxy.get('status', [])
            })
    
    # Save updated data with IDs
    if active_proxies:
        with open('data.txt', 'w', encoding='utf-8') as f:
            json.dump(proxy_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Returning {len(active_proxies)} active proxies")
    return jsonify({
        'status': 'success',
        'proxies': active_proxies
    })

@app.route('/api/update')
def update_proxy():
    proxy = request.args.get('proxy', '')
    status = request.args.get('status', '')
    
    # Remove quotes if present
    proxy = proxy.strip('"')
    
    if not proxy:
        return jsonify({
            'status': 'error',
            'message': 'Proxy parameter is required'
        }), 400
    
    logger.info(f"Looking for proxy: {proxy}")
    logger.info(f"Current proxy data: {proxy_data}")
    
    # Find the proxy in our data
    target_proxy = None
    for p in proxy_data:
        # Check if proxy parameter is an ID or proxy address
        if proxy.startswith('PRX'):
            if p.get('id') == proxy:  # Use get() to safely check for id
                target_proxy = p
                logger.info(f"Found proxy by ID: {proxy}")
                break
        else:
            if p.get('proxyhttp') == proxy:
                target_proxy = p
                logger.info(f"Found proxy by address: {proxy}")
                break
    
    if target_proxy:
        if status:
            # Initialize status list if not exists
            if 'status' not in target_proxy:
                target_proxy['status'] = []
                
            # Update status if provided
            if status not in target_proxy['status']:
                target_proxy['status'].append(status)
            # Save to data.txt
            with open('data.txt', 'w', encoding='utf-8') as f:
                json.dump(proxy_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Updated status for proxy {target_proxy.get('id', 'NO_ID')}: {target_proxy['status']}")
        
        return jsonify({
            'status': 'success',
            'proxy_id': target_proxy.get('id', 'NO_ID'),
            'proxy': target_proxy.get('proxyhttp', 'NO_PROXY'),
            'current_status': target_proxy.get('status', [])
        })
    
    logger.warning(f"Proxy not found: {proxy}")
    return jsonify({
        'status': 'error',
        'message': 'Proxy not found'
    }), 404

if __name__ == '__main__':
    # Load existing proxies from data.txt if exists
    try:
        with open('data.txt', 'r', encoding='utf-8') as f:
            proxy_data = json.load(f)
            # Set proxy counter based on existing data
            if proxy_data:
                try:
                    max_id = max(int(p['id'][3:]) for p in proxy_data if 'id' in p)
                    proxy_counter = max_id
                except ValueError:
                    # If no valid IDs found, start from 0
                    proxy_counter = 0
            logger.info(f"Loaded {len(proxy_data)} existing proxies from data.txt")
    except FileNotFoundError:
        logger.info("No existing data.txt found. Starting fresh.")
        proxy_counter = 0
    
    # Start proxy fetching thread
    fetch_thread = threading.Thread(target=fetch_proxy, daemon=True)
    fetch_thread.start()
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_expired_proxies, daemon=True)
    cleanup_thread.start()
    
    # Get network information
    logger.info("="*50)
    logger.info("Network Information:")
    
    try:
        # Get all IP addresses
        hostname = socket.gethostname()
        ip_list = socket.gethostbyname_ex(hostname)[2]
        
        logger.info(f"Hostname: {hostname}")
        for ip in ip_list:
            if not ip.startswith('127.'):  # Skip localhost
                logger.info(f"IP Address: {ip}")
    except Exception as e:
        logger.error(f"Error getting network info: {str(e)}")
    
    logger.info("="*50)
    logger.info("Server Access URLs:")
    logger.info("  - Local:   http://localhost:8080")
    for ip in ip_list:
        if not ip.startswith('127.'):  # Skip localhost
            logger.info(f"  - Network: http://{ip}:8080")
    logger.info("="*50)
    
    # Run Flask app
    app.run(host='0.0.0.0', port=8080)