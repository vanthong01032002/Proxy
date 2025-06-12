from flask import Flask, jsonify, request
import requests
import json
import time
import threading
import re
from datetime import datetime
import logging
import socket
from pymongo import MongoClient
from bson.objectid import ObjectId
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# MongoDB connection
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGODB_URI)
db = client['proxy_database']
proxy_collection = db['proxies']

# Global variable to store proxy counter
proxy_counter = 0  # Counter for generating proxy IDs
key_status = "valid"  # Track key status

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
                    
                    # Check if proxy already exists
                    existing_proxy = proxy_collection.find_one({'proxyhttp': data['proxyhttp']})
                    if existing_proxy:
                        # Update existing proxy
                        proxy_collection.update_one(
                            {'_id': existing_proxy['_id']},
                            {'$set': {'expiration_time': expiration_time}}
                        )
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
                        proxy_collection.insert_one(proxy_info)
                        logger.info(f"Added new proxy: {proxy_info}")
                    
                    logger.info(f"Total proxies in database: {proxy_collection.count_documents({})}")
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
            result = proxy_collection.delete_many({'expiration_time': {'$lt': current_time}})
            
            if result.deleted_count > 0:
                logger.info(f"Removed {result.deleted_count} expired proxies")
            
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
    
    current_time = int(time.time())
    active_proxies = []
    
    try:
        logger.info(f"Current proxy count: {proxy_collection.count_documents({})}")
        
        for proxy in proxy_collection.find({'expiration_time': {'$gt': current_time}}):
            # Generate ID if not exists
            if 'id' not in proxy:
                proxy['id'] = generate_proxy_id()
                proxy_collection.update_one(
                    {'_id': proxy['_id']},
                    {'$set': {'id': proxy['id']}}
                )
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
        
        logger.info(f"Returning {len(active_proxies)} active proxies")
        return jsonify({
            'status': 'success',
            'proxies': active_proxies
        })
    except Exception as e:
        logger.error(f"Error getting proxies: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Lỗi kết nối database'
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
        # Find the proxy in our database
        target_proxy = None
        if proxy.startswith('PRX'):
            target_proxy = proxy_collection.find_one({'id': proxy})
        else:
            target_proxy = proxy_collection.find_one({'proxyhttp': proxy})
        
        if target_proxy:
            if status:
                # Initialize status list if not exists
                if 'status' not in target_proxy:
                    target_proxy['status'] = []
                    
                # Update status if provided
                if status not in target_proxy['status']:
                    proxy_collection.update_one(
                        {'_id': target_proxy['_id']},
                        {'$push': {'status': status}}
                    )
                    target_proxy['status'].append(status)
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
            'message': 'Lỗi kết nối database'
        }), 500

# Initialize the application
def init_app():
    global proxy_counter
    
    # Set proxy counter based on existing data
    try:
        max_proxy = proxy_collection.find_one(sort=[('id', -1)])
        if max_proxy and 'id' in max_proxy:
            proxy_counter = int(max_proxy['id'][3:])
        logger.info(f"Loaded existing proxies from database. Current counter: {proxy_counter}")
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

