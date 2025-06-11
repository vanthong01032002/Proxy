# Proxy Server API

A Flask-based proxy server that manages and provides proxy information.

## API Endpoints

1. Get all active proxies:
```
GET /api/get_proxy
```

2. Update proxy status:
```
GET /api/update?proxy="PROXY_ID_OR_ADDRESS"&status=STATUS
```

## Deployment

This project is configured for deployment on Render.com

1. Fork this repository
2. Create a new Web Service on Render
3. Connect your GitHub repository
4. Use the following settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn --worker-class eventlet main:app -b 0.0.0.0:10000`
   - Environment Variables:
     - `PYTHON_VERSION`: 3.9.18
     - `PORT`: 10000

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python main.py
```

The server will be available at `http://localhost:8080`

## Production Deployment

For production deployment, make sure to:

1. Set environment variables:
   - `FLASK_ENV=production`
   - `PORT=10000`

2. Use gunicorn with eventlet:
```bash
gunicorn --worker-class eventlet main:app -b 0.0.0.0:10000
``` 