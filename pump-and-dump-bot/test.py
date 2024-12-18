import os
import time
import hmac
import hashlib
import requests
import random
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# MEXC API credentials
MEXC_API_KEY = os.getenv('MEXC_API_KEY')
MEXC_API_SECRET = os.getenv('MEXC_API_SECRET')

# Base URL for MEXC API
BASE_URL = "https://api.mexc.com"

def get_server_time():
    """
    Fetch the server time from MEXC to synchronize requests.
    """
    endpoint = "/api/v3/time"
    url = BASE_URL + endpoint
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()['serverTime']
    else:
        raise Exception(f"Failed to get server time: {response.text}")

def create_signature(query_string, secret):
    """
    Create HMAC SHA256 signature required by MEXC API.
    """
    return hmac.new(
        secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def place_market_order(symbol, quote_qty=100):
    """
    Place a market buy order on MEXC for the specified symbol and quote amount.
    
    Parameters:
        symbol (str): Trading pair symbol (e.g., 'BTCUSDT')
        quote_qty (float): Amount in USDT to spend (default is 100 USDT)
        
    Returns:
        dict: Response from MEXC API
    """
    endpoint = "/api/v3/order"
    url = BASE_URL + endpoint

    # Get server time
    timestamp = get_server_time()

    # Parameters for the order
    params = {
        "symbol": symbol,
        "side": "BUY",
        "type": "MARKET",
        "quoteOrderQty": quote_qty,
        "timestamp": timestamp
    }

    # Create query string
    query_string = "&".join([f"{key}={value}" for key, value in params.items()])

    # Generate signature
    signature = create_signature(query_string, MEXC_API_SECRET)
    params["signature"] = signature

    # Headers
    headers = {
        "X-MEXC-APIKEY": MEXC_API_KEY
    }

    # Send POST request
    response = requests.post(url, headers=headers, params=params)

    if response.status_code == 200:
        order = response.json()
        print(f"Order placed successfully: {order}")
        return order
    else:
        print(f"Failed to place order: {response.text}")
        return None

def main():
    try:
        # Place a market buy order
        order_response = place_market_order('MXUSDT', quote_qty=100)
        
        if order_response:
            # Extract order details
            order_id = order_response.get('orderId')
            executed_qty = float(order_response.get('executedQty', 0))
            buy_price = float(order_response.get('fills')[0].get('price', 0)) if 'fills' in order_response and order_response['fills'] else 0
            print(f"Order ID: {order_id}")
            print(f"Executed Quantity: {executed_qty}")
            print(f"Buy Price: {buy_price}")
        else:
            print("No order was placed.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
