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
   - Start Command: `gunicorn main:app -c gunicorn_config.py`
   - Environment Variables:
     - `PYTHON_VERSION`: 3.9.0

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