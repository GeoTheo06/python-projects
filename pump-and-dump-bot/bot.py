import os
import time
import hmac
import hashlib
import requests
from telethon import TelegramClient, events
from datetime import datetime, timedelta
import threading
from dotenv import load_dotenv
load_dotenv()

# Load environment variables
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
MEXC_API_KEY = os.getenv('MEXC_API_KEY')
MEXC_API_SECRET = os.getenv('MEXC_API_SECRET')

# Initialize Telegram client
client = TelegramClient('my_user_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)

def place_market_order(symbol, quote_qty=10):
    base_url = "https://api.mexc.com"
    endpoint = "/api/v3/order"
    
    params = {
        "symbol": symbol.upper() + "USDT",  # Assuming USDT pair
        "side": "BUY",
        "type": "MARKET",
        "quoteOrderQty": quote_qty,  # Spend 100 USDT
        "timestamp": int(time.time() * 1000)
    }
    
    query_string = "&".join([f"{key}={value}" for key, value in params.items()])
    
    signature = hmac.new(
        MEXC_API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params["signature"] = signature
    
    headers = {
        "X-MEXC-APIKEY": MEXC_API_KEY
    }
    
    response = requests.post(base_url + endpoint, headers=headers, params=params)
    
    if response.status_code == 200:
        order = response.json()
        print(f"Order placed successfully: {order}")
        return order
    else:
        print(f"Failed to place order: {response.text}")
        return None

def place_sell_order(symbol, quantity):
    base_url = "https://api.mexc.com"
    endpoint = "/api/v3/order"
    
    params = {
        "symbol": symbol.upper() + "USDT",  # Assuming USDT pair
        "side": "SELL",
        "type": "MARKET",
        "quantity": quantity,  # Amount to sell
        "timestamp": int(time.time() * 1000)
    }
    
    query_string = "&".join([f"{key}={value}" for key, value in params.items()])
    
    signature = hmac.new(
        MEXC_API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params["signature"] = signature
    
    headers = {
        "X-MEXC-APIKEY": MEXC_API_KEY
    }
    
    response = requests.post(base_url + endpoint, headers=headers, params=params)
    
    if response.status_code == 200:
        order = response.json()
        print(f"Sell order placed successfully: {order}")
        return order
    else:
        print(f"Failed to place sell order: {response.text}")
        return None

def monitor_and_sell(symbol, buy_price, quantity):
    target_price = buy_price * 1.5  # 50% profit
    print(f"Monitoring {symbol}. Target price: {target_price}")

    while True:
        try:
            price_endpoint = f"https://api.mexc.com/api/v3/ticker/price?symbol={symbol.upper()}USDT"
            response = requests.get(price_endpoint)
            data = response.json()
            current_price = float(data['price'])
            print(f"Current price of {symbol}: {current_price}")

            if current_price >= target_price:
                print(f"Target achieved for {symbol}. Selling now.")
                place_sell_order(symbol, quantity)
                break

            # Sleep for a short interval to avoid hitting API rate limits
            time.sleep(0.02)

        except Exception as e:
            print(f"Error while monitoring price: {e}")
            time.sleep(1)

def get_order_details(symbol, order_id):
    base_url = "https://api.mexc.com"
    endpoint = "/api/v3/order"
    
    params = {
        "symbol": f"{symbol.upper()}USDT",
        "orderId": order_id,
        "timestamp": int(time.time() * 1000)
    }
    
    query_string = "&".join([f"{key}={value}" for key, value in params.items()])
    signature = hmac.new(
        MEXC_API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    headers = {"X-MEXC-APIKEY": MEXC_API_KEY}
    params["signature"] = signature
    
    response = requests.get(base_url + endpoint, headers=headers, params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching order details: {response.text}")
        return None
        

@client.on(events.NewMessage(chats='t.me/thisisacryptotest'))
async def handler(event):
    
    # Fetch the message content directly
    crypto_symbol = event.message.message.strip().upper()  # Get the message text
    print(f"Received crypto symbol to buy: {crypto_symbol}")
    
    # Place buy order
    order = place_market_order(crypto_symbol)
    if order:
        order_id = order.get('orderId')
        if order_id:
            time.sleep(1)  # Give it a moment to ensure execution
            details = get_order_details(crypto_symbol, order_id)
            if details:
                executed_qty = float(details.get('executedQty', 0))
                cummulative_quote_qty = float(details.get('cummulativeQuoteQty', 0))
                
                if executed_qty > 0:
                    buy_price = cummulative_quote_qty / executed_qty
                    # Now start the monitoring thread with executed_qty and buy_price
                    monitor_thread = threading.Thread(
                        target=monitor_and_sell, 
                        args=(crypto_symbol, buy_price, executed_qty)
                    )
                    monitor_thread.start()
                else:
                    print("No executed quantity found. Order may not have filled yet.")
            else:
                print("Failed to retrieve detailed order info.")
        else:
            print("Order placed, but no order_id returned.")
    else:
        print("Buy order was not successful.")

def main():
    with client:
        print("Bot is running...")
        client.run_until_disconnected()

if __name__ == "__main__":
    main()
