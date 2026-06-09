from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from config import BINANCE_API_KEY, BINANCE_SECRET_KEY
import logging

logger = logging.getLogger(__name__)

client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)


def get_open_positions():
    """Get all open positions from Binance Futures"""
    try:
        account = client.futures_account()
        positions = []
        for position in account['positions']:
            if float(position['positionAmt']) != 0:
                positions.append({
                    'symbol': position['symbol'],
                    'positionAmt': float(position['positionAmt']),
                    'entryPrice': float(position['entryPrice']),
                    'markPrice': float(position['markPrice']),
                    'unRealizedProfit': float(position['unRealizedProfit']),
                    'percentage': float(position['percentage'])
                })
        return positions
    except BinanceAPIException as e:
        logger.error(f"Error getting positions: {e}")
        return []


def get_current_price(symbol):
    """Get current market price"""
    try:
        ticker = client.futures_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    except BinanceAPIException as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        return None


def close_position(symbol, quantity):
    """Close position"""
    try:
        # Get current position to determine side
        account = client.futures_account()
        for pos in account['positions']:
            if pos['symbol'] == symbol:
                position_amt = float(pos['positionAmt'])
                if position_amt > 0:
                    # Long position, sell to close
                    order = client.futures_create_order(
                        symbol=symbol,
                        side='SELL',
                        type='MARKET',
                        quantity=abs(quantity)
                    )
                else:
                    # Short position, buy to close
                    order = client.futures_create_order(
                        symbol=symbol,
                        side='BUY',
                        type='MARKET',
                        quantity=abs(quantity)
                    )
                logger.info(f"Closed position {symbol}: {order}")
                return order
        return None
    except BinanceOrderException as e:
        logger.error(f"Error closing position {symbol}: {e}")
        return None


def close_all_positions_by_symbols(symbols):
    """Close all positions for given symbols"""
    results = {}
    for symbol in symbols:
        result = close_position(symbol, None)
        results[symbol] = result
    return results


def get_position_info(symbol):
    """Get detailed position info"""
    try:
        account = client.futures_account()
        for pos in account['positions']:
            if pos['symbol'] == symbol:
                return {
                    'symbol': symbol,
                    'positionAmt': float(pos['positionAmt']),
                    'entryPrice': float(pos['entryPrice']),
                    'markPrice': float(pos['markPrice']),
                    'unRealizedProfit': float(pos['unRealizedProfit']),
                    'percentage': float(pos['percentage']),
                    'side': 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT'
                }
        return None
    except BinanceAPIException as e:
        logger.error(f"Error getting position info: {e}")
        return None


def set_stop_loss(symbol, stop_price, quantity):
    """Set stop loss order"""
    try:
        account = client.futures_account()
        for pos in account['positions']:
            if pos['symbol'] == symbol:
                position_amt = float(pos['positionAmt'])
                side = 'SELL' if position_amt > 0 else 'BUY'
                
                order = client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type='STOP_MARKET',
                    stopPrice=stop_price,
                    quantity=abs(quantity)
                )
                logger.info(f"Set stop loss for {symbol} at {stop_price}")
                return order
        return None
    except BinanceOrderException as e:
        logger.error(f"Error setting stop loss: {e}")
        return None