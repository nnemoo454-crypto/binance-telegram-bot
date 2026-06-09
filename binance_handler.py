from binance.client import Client
from binance.exceptions import BinanceAPIException
from config import BINANCE_API_KEY, BINANCE_SECRET_KEY
import logging

logger = logging.getLogger(__name__)

client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)


def get_open_positions():
    """Get all open positions from Binance Futures"""
    try:
        account = client.futures_account()
        positions = []
        
        for pos in account['positions']:
            amt = float(pos['positionAmt'])
            if amt != 0:  # Only open positions
                positions.append({
                    'symbol': pos['symbol'],
                    'positionAmt': amt,
                    'entryPrice': float(pos['entryPrice']),
                    'markPrice': float(pos['markPrice']),
                    'unRealizedProfit': float(pos['unRealizedProfit']),
                    'side': 'LONG' if amt > 0 else 'SHORT'
                })
        
        logger.info(f"Found {len(positions)} open positions")
        return positions
    except BinanceAPIException as e:
        logger.error(f"Binance API Error: {e}")
        return []


def get_position_by_symbol(symbol):
    """Get specific position"""
    try:
        account = client.futures_account()
        for pos in account['positions']:
            if pos['symbol'] == symbol:
                amt = float(pos['positionAmt'])
                if amt != 0:
                    return {
                        'symbol': symbol,
                        'positionAmt': amt,
                        'entryPrice': float(pos['entryPrice']),
                        'markPrice': float(pos['markPrice']),
                        'unRealizedProfit': float(pos['unRealizedProfit']),
                        'side': 'LONG' if amt > 0 else 'SHORT'
                    }
        return None
    except BinanceAPIException as e:
        logger.error(f"Error getting position {symbol}: {e}")
        return None


def get_price(symbol):
    """Get current price"""
    try:
        ticker = client.futures_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    except BinanceAPIException as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        return None


def close_position_by_symbol(symbol):
    """Close position by symbol"""
    try:
        position = get_position_by_symbol(symbol)
        if not position:
            logger.warning(f"Position {symbol} not found")
            return None
        
        side = 'SELL' if position['side'] == 'LONG' else 'BUY'
        qty = abs(position['positionAmt'])
        
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type='MARKET',
            quantity=qty
        )
        
        logger.info(f"Closed position {symbol}")
        return order
    except Exception as e:
        logger.error(f"Error closing position {symbol}: {e}")
        return None


def close_multiple_positions(symbols):
    """Close multiple positions"""
    results = {}
    for symbol in symbols:
        result = close_position_by_symbol(symbol)
        results[symbol] = result
    return results