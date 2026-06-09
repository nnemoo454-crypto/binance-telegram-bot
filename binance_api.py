from binance.client import Client
from binance.exceptions import BinanceAPIException
from config import BINANCE_API_KEY, BINANCE_SECRET_KEY
import logging

logger = logging.getLogger(__name__)

client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)


def get_current_price(symbol):
    """Get current market price"""
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    except BinanceAPIException as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        return None


def get_order_status(symbol, order_id):
    """Get order status"""
    try:
        order = client.get_order(symbol=symbol, orderId=order_id)
        return {
            'status': order['status'],
            'filled_qty': float(order['executedQty']),
            'orig_qty': float(order['origQty'])
        }
    except BinanceAPIException as e:
        logger.error(f"Error getting order {order_id}: {e}")
        return None


def cancel_order(symbol, order_id):
    """Cancel order"""
    try:
        result = client.cancel_order(symbol=symbol, orderId=order_id)
        logger.info(f"Cancelled order {order_id} for {symbol}")
        return result
    except BinanceAPIException as e:
        logger.error(f"Error cancelling order {order_id}: {e}")
        return None


def place_market_order(symbol, side, quantity):
    """Place market order to close position"""
    try:
        order = client.order_market(symbol=symbol, side=side, quantity=quantity)
        logger.info(f"Placed market order: {side} {quantity} {symbol}")
        return order
    except BinanceAPIException as e:
        logger.error(f"Error placing market order: {e}")
        return None


def get_open_orders(symbol):
    """Get all open orders for symbol"""
    try:
        orders = client.get_open_orders(symbol=symbol)
        return orders
    except BinanceAPIException as e:
        logger.error(f"Error getting open orders for {symbol}: {e}")
        return []


def get_account_balance(asset):
    """Get account balance for asset"""
    try:
        account = client.get_account()
        for balance in account['balances']:
            if balance['asset'] == asset:
                return {
                    'free': float(balance['free']),
                    'locked': float(balance['locked'])
                }
        return None
    except BinanceAPIException as e:
        logger.error(f"Error getting balance for {asset}: {e}")
        return None