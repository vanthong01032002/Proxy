from flask import Flask, jsonify, request
import requests
import json
import time
import threading
import re
from datetime import datetime
import logging
import socket
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# File storage configuration
DATA_FILE = 'proxy_data.json'
LOCK = threading.Lock()

# Global variable to store proxy counter
proxy_counter = 0  # Counter for generating proxy IDs
key_status = "valid"  # Track key status

def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Error loading data: {str(e)}")
        return []

def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving data: {str(e)}")

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
    global key_status
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
                    key_status = "valid"
                    # Calculate expiration time
                    seconds = extract_seconds(data['message'])
                    expiration_time = int(time.time()) + seconds
                    
                    with LOCK:
                        proxy_data = load_data()
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
                        
                        save_data(proxy_data)
                        logger.info(f"Total proxies in storage: {len(proxy_data)}")
                else:
                    key_status = "expired"
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
            with LOCK:
                proxy_data = load_data()
                initial_count = len(proxy_data)
                proxy_data = [p for p in proxy_data if p['expiration_time'] > current_time]
                
                if len(proxy_data) != initial_count:
                    save_data(proxy_data)
                    logger.info(f"Removed {initial_count - len(proxy_data)} expired proxies")
            
        except Exception as e:
            logger.error(f"Error in cleanup: {str(e)}")
        
        time.sleep(10)

@app.route('/api/get_proxy')
def get_proxy():
    global key_status
    
    if key_status == "expired":
        return jsonify({
            'status': 'error',
            'message': 'Key đã hết hạn hoặc không tồn tại'
        }), 403
    
    try:
        current_time = int(time.time())
        with LOCK:
            proxy_data = load_data()
            active_proxies = []
            
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
            
            if active_proxies:
                save_data(proxy_data)
            
            logger.info(f"Returning {len(active_proxies)} active proxies")
            return jsonify({
                'status': 'success',
                'proxies': active_proxies
            })
    except Exception as e:
        logger.error(f"Error getting proxies: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Lỗi khi đọc dữ liệu'
        }), 500

@app.route('/api/update')
def update_proxy():
    global key_status
    
    if key_status == "expired":
        return jsonify({
            'status': 'error',
            'message': 'Key đã hết hạn hoặc không tồn tại'
        }), 403
        
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
    
    try:
        with LOCK:
            proxy_data = load_data()
            # Find the proxy in our data
            target_proxy = None
            if proxy.startswith('PRX'):
                target_proxy = next((p for p in proxy_data if p.get('id') == proxy), None)
            else:
                target_proxy = next((p for p in proxy_data if p.get('proxyhttp') == proxy), None)
            
            if target_proxy:
                if status:
                    # Initialize status list if not exists
                    if 'status' not in target_proxy:
                        target_proxy['status'] = []
                        
                    # Update status if provided
                    if status not in target_proxy['status']:
                        target_proxy['status'].append(status)
                        save_data(proxy_data)
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
    except Exception as e:
        logger.error(f"Error updating proxy: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Lỗi khi cập nhật dữ liệu'
        }), 500

@app.route('/api/status')
def check_status():
    try:
        with LOCK:
            proxy_data = load_data()
            current_time = int(time.time())
            
            total_proxies = len(proxy_data)
            active_proxies = len([p for p in proxy_data if p['expiration_time'] > current_time])
            
            # Get 5 most recent proxies
            recent_proxies = sorted(proxy_data, key=lambda x: x.get('expiration_time', 0), reverse=True)[:5]
            
            return jsonify({
                'status': 'success',
                'storage': {
                    'file': DATA_FILE,
                    'exists': os.path.exists(DATA_FILE),
                    'size': os.path.getsize(DATA_FILE) if os.path.exists(DATA_FILE) else 0
                },
                'proxies': {
                    'total': total_proxies,
                    'active': active_proxies,
                    'expired': total_proxies - active_proxies
                },
                'key_status': key_status,
                'recent_proxies': recent_proxies
            })
    except Exception as e:
        logger.error(f"Error checking status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Lỗi khi kiểm tra trạng thái: {str(e)}'
        }), 500

# Initialize the application
def init_app():
    global proxy_counter
    
    # Set proxy counter based on existing data
    try:
        proxy_data = load_data()
        if proxy_data:
            try:
                max_id = max(int(p['id'][3:]) for p in proxy_data if 'id' in p)
                proxy_counter = max_id
            except ValueError:
                proxy_counter = 0
        logger.info(f"Loaded existing proxies from {DATA_FILE}. Current counter: {proxy_counter}")
    except Exception as e:
        logger.error(f"Error loading proxy counter: {str(e)}")
        proxy_counter = 0
    
    # Start proxy fetching thread
    fetch_thread = threading.Thread(target=fetch_proxy, daemon=True)
    fetch_thread.start()
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_expired_proxies, daemon=True)
    cleanup_thread.start()

# Initialize the application when the module is imported
init_app()

