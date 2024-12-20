import os
import time
import hmac
import hashlib
import requests
import json
from telethon import TelegramClient, events
from datetime import datetime
import threading
from dotenv import load_dotenv
import websocket
from queue import Queue

load_dotenv()

TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
MEXC_API_KEY = os.getenv('MEXC_API_KEY')
MEXC_API_SECRET = os.getenv('MEXC_API_SECRET')

client = TelegramClient('my_user_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)
WEBSOCKET_URL = "wss://wbs.mexc.com/ws"

GAIN = 1.5
QUANTITY = 100

def place_market_order(symbol, quote_qty=QUANTITY):
    base_url = "https://api.mexc.com"
    endpoint = "/api/v3/order"
    
    params = {
        "symbol": symbol.upper() + "USDT",
        "side": "BUY",
        "type": "MARKET",
        "quoteOrderQty": quote_qty,
        "timestamp": int(time.time() * 1000)
    }
    
    query_string = "&".join([f"{key}={value}" for key, value in params.items()])
    signature = hmac.new(
        MEXC_API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params["signature"] = signature
    headers = {"X-MEXC-APIKEY": MEXC_API_KEY}
    
    response = requests.post(base_url + endpoint, headers=headers, params=params)
    if response.status_code == 200:
        order = response.json()
        print(f"\nBuy Order successful: {order}\n")
        return order
    else:
        print(f"\nFailed to place order: {response.text}")
        return None

def place_sell_order(symbol, quantity):
    base_url = "https://api.mexc.com"
    endpoint = "/api/v3/order"
    
    params = {
        "symbol": symbol.upper() + "USDT",
        "side": "SELL",
        "type": "MARKET",
        "quantity": quantity,
        "timestamp": int(time.time() * 1000)
    }
    
    query_string = "&".join([f"{key}={value}" for key, value in params.items()])
    signature = hmac.new(
        MEXC_API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params["signature"] = signature
    headers = {"X-MEXC-APIKEY": MEXC_API_KEY}
    
    response = requests.post(base_url + endpoint, headers=headers, params=params)
    if response.status_code == 200:
        order = response.json()
        print(f"Sell order successful: {order}\n")
        return order
    else:
        print(f"\nFailed to place sell order: {response.text}\n")
        return None

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
        print(f"\n\nError fetching order details: {response.text}\n\n")
        return None

def monitor_and_sell_ws(symbol, buy_price, quantity):
    target_price = buy_price * GAIN

    message_queue = Queue()

    # This thread will process messages from the queue
    def processing_thread():
        while True:
            deals = message_queue.get()
            if deals is None:
                break  # Exit loop if None is sent (clean shutdown)
            
            for deal in deals:
                current_price = float(deal['p'])
                print(f"{symbol} @ {current_price}")
                
                if current_price >= target_price:
                    print(f"\n!!!!!!!!!!\nTarget achieved for {symbol} @ {current_price}\n")

                    # Continuously try placing the sell order until it succeeds
                    while True:
                        sell_order = place_sell_order(symbol, quantity)
                        if sell_order is not None:
                            # Sell order placed successfully
                            break
                        else:
                            print("\nSell order failed. Retrying...")
                            time.sleep(0.1)  # wait a bit before retrying

                    return  # Stop processing after successful sell
                
            # Delay after processing each set of deals
            time.sleep(0.01)

    # Start the processing thread
    processor = threading.Thread(target=processing_thread, daemon=True)
    processor.start()

    def on_message(ws, message):
        try:
            data = json.loads(message)
            if 'd' in data and 'deals' in data['d']:
                # Put the deals in the queue for the processing thread
                message_queue.put(data['d']['deals'])
        except Exception as e:
            print(f"Error processing WebSocket message: {e}")

    def on_error(ws, error):
        print(f"WebSocket error: {error}")

    def on_close(ws, close_status_code, close_msg):
        print(f"WebSocket closed for {symbol}")
        # Signal processor thread to stop
        message_queue.put(None)

    def on_open(ws):
        subscription_message = {
            "method": "SUBSCRIPTION",
            "params": [
                f"spot@public.deals.v3.api@{symbol.upper()}USDT"
            ]
        }
        ws.send(json.dumps(subscription_message))
        print(f"Subscribed to WebSocket trade stream for {symbol}")

    ws = websocket.WebSocketApp(
        WEBSOCKET_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    ws.run_forever()

@client.on(events.NewMessage(chats='t.me/cryptoclubpump'))
async def handler(event):
    crypto_symbol = event.message.message.strip().upper()
    print(f"Received symbol to buy: {crypto_symbol}")
    
    order = place_market_order(crypto_symbol)
    if order:
        order_id = order.get('orderId')
        if order_id:
            time.sleep(0.005)  # Give it a moment to ensure execution
            details = get_order_details(crypto_symbol, order_id)
            if details:
                executed_qty = float(details.get('executedQty', 0))
                cummulative_quote_qty = float(details.get('cummulativeQuoteQty', 0))
                
                if executed_qty > 0:
                    buy_price = cummulative_quote_qty / executed_qty
                    print(f"Buy details: Quantity={executed_qty} @ {buy_price}. Target: {buy_price * GAIN}\n")
                    
                    monitor_thread = threading.Thread(
                        target=monitor_and_sell_ws, 
                        args=(crypto_symbol, buy_price, executed_qty),
                        daemon=True
                    )
                    monitor_thread.start()
                else:
                    print("No executed quantity found. Order may not have filled yet.")
            else:
                print("Failed to retrieve detailed order info.")
        else:
            print("Order placed, but no order_id returned.")
    else:
        print("Buy order was not successful.\n\n")

def main():
    with client:
        print("Bot is running...")
        client.run_until_disconnected()

if __name__ == "__main__":
    main()
