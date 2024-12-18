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

def place_market_order(symbol, quote_qty=100):
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
            time.sleep(5)

        except Exception as e:
            print(f"Error while monitoring price: {e}")
            time.sleep(5)

@client.on(events.NewMessage(chats='t.me/cryptoclubpump'))
async def handler(event):
    message_time = datetime.utcnow().replace(tzinfo=None)
    target_time = message_time.replace(hour=17, minute=0, second=0, microsecond=0)
    
    # Calculate wait time until 4:57 AM UTC
    desired_time = target_time - timedelta(minutes=3)
    now = datetime.utcnow()
    wait_time = (desired_time - now).total_seconds()
    if wait_time > 0:
        print(f"Waiting for {wait_time} seconds until 4:57 AM UTC")
        time.sleep(wait_time)
    
    # Fetch the next message after 5 AM
    new_message = await event.get_message()
    crypto_symbol = new_message.text.strip().upper()
    print(f"Received crypto symbol to buy: {crypto_symbol}")
    
    # Place buy order
    order = place_market_order(crypto_symbol)
    if order:
        # Extract the quantity bought
        if 'fills' in order and len(order['fills']) > 0:
            quantity = float(order['fills'][0].get('qty', 0))
        else:
            quantity = float(order.get('executedQty', 0))
        # Fetch the buy price
        if 'fills' in order and len(order['fills']) > 0:
            buy_price = float(order['fills'][0].get('price', 0))
        else:
            buy_price = 0
        if buy_price > 0 and quantity > 0:
            # Start monitoring the price in a separate thread
            monitor_thread = threading.Thread(target=monitor_and_sell, args=(crypto_symbol, buy_price, quantity))
            monitor_thread.start()
        else:
            print("Failed to retrieve buy price or quantity.")
    else:
        print("Buy order was not successful.")

def main():
    with client:
        print("Bot is running...")
        client.run_until_disconnected()

if __name__ == "__main__":
    main()
