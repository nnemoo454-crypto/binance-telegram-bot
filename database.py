from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import DATABASE_URL
import logging

logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Block(Base):
    """Trading block (A, B, C, D, E)"""
    __tablename__ = "blocks"

    id = Column(Integer, primary_key=True)
    name = Column(String(1), unique=True, index=True)  # A, B, C, D, E
    status = Column(String, default="inactive")  # active, closed
    stop_line = Column(Float, nullable=True)
    tp_value = Column(Float, nullable=True)  # TP in dollars
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    close_reason = Column(String, nullable=True)  # stop_line, tp, manual
    final_pnl = Column(Float, default=0.0)


class Position(Base):
    """Position in a block"""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True)
    block_name = Column(String(1), index=True)  # A, B, C, D, E
    symbol = Column(String, index=True)  # BTCUSDT, ETHUSDT, etc
    side = Column(String)  # LONG or SHORT
    entry_price = Column(Float)
    quantity = Column(Float)
    status = Column(String, default="open")  # open, closed
    close_price = Column(Float, nullable=True)
    pnl = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)


class Event(Base):
    """Event log"""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_type = Column(String, index=True)  # block_created, tp_hit, sl_hit, etc
    block_name = Column(String(1), nullable=True)
    message = Column(Text)
    data = Column(Text, nullable=True)  # JSON


class Statistics(Base):
    """Daily statistics"""
    __tablename__ = "statistics"

    id = Column(Integer, primary_key=True)
    date = Column(String, unique=True, index=True)  # YYYY-MM-DD
    total_pnl = Column(Float, default=0.0)
    total_blocks = Column(Integer, default=0)
    winning_blocks = Column(Integer, default=0)
    losing_blocks = Column(Integer, default=0)
    total_positions = Column(Integer, default=0)


# Create tables
Base.metadata.create_all(bind=engine)
logger.info("✅ Database initialized")


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_block(name, stop_line=None, tp_value=None):
    """Create new block"""
    db = SessionLocal()
    try:
        block = Block(
            name=name,
            status="active",
            stop_line=stop_line,
            tp_value=tp_value
        )
        db.add(block)
        db.commit()
        db.refresh(block)
        logger.info(f"Block {name} created with SL={stop_line}, TP={tp_value}")
        return block
    finally:
        db.close()


def get_block(name):
    """Get block by name"""
    db = SessionLocal()
    try:
        block = db.query(Block).filter(Block.name == name).first()
        return block
    finally:
        db.close()


def get_active_blocks():
    """Get all active blocks"""
    db = SessionLocal()
    try:
        blocks = db.query(Block).filter(Block.status == "active").all()
        return blocks
    finally:
        db.close()


def add_position(block_name, symbol, side, entry_price, quantity):
    """Add position to block"""
    db = SessionLocal()
    try:
        position = Position(
            block_name=block_name,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity
        )
        db.add(position)
        db.commit()
        db.refresh(position)
        logger.info(f"Position {symbol} added to block {block_name}")
        return position
    finally:
        db.close()


def get_block_positions(block_name):
    """Get all open positions in block"""
    db = SessionLocal()
    try:
        positions = db.query(Position).filter(
            Position.block_name == block_name,
            Position.status == "open"
        ).all()
        return positions
    finally:
        db.close()


def close_position(position_id, close_price, pnl):
    """Close position"""
    db = SessionLocal()
    try:
        position = db.query(Position).filter(Position.id == position_id).first()
        if position:
            position.status = "closed"
            position.close_price = close_price
            position.pnl = pnl
            position.closed_at = datetime.utcnow()
            db.commit()
            logger.info(f"Position {position.symbol} closed with PnL={pnl}")
    finally:
        db.close()


def close_block(block_name, close_reason, final_pnl):
    """Close block"""
    db = SessionLocal()
    try:
        block = db.query(Block).filter(Block.name == block_name).first()
        if block:
            block.status = "closed"
            block.closed_at = datetime.utcnow()
            block.close_reason = close_reason
            block.final_pnl = final_pnl
            db.commit()
            logger.info(f"Block {block_name} closed: {close_reason}, PnL={final_pnl}")
    finally:
        db.close()


def log_event(event_type, message, block_name=None, data=None):
    """Log event"""
    db = SessionLocal()
    try:
        event = Event(
            event_type=event_type,
            block_name=block_name,
            message=message,
            data=data
        )
        db.add(event)
        db.commit()
        logger.info(f"Event: {event_type} - {message}")
    finally:
        db.close()


def update_block_sl(block_name, new_sl):
    """Update block stop line"""
    db = SessionLocal()
    try:
        block = db.query(Block).filter(Block.name == block_name).first()
        if block:
            block.stop_line = new_sl
            db.commit()
            logger.info(f"Block {block_name} SL updated to {new_sl}")
    finally:
        db.close()


def update_block_tp(block_name, new_tp):
    """Update block take profit"""
    db = SessionLocal()
    try:
        block = db.query(Block).filter(Block.name == block_name).first()
        if block:
            block.tp_value = new_tp
            db.commit()
            logger.info(f"Block {block_name} TP updated to {new_tp}")
    finally:
        db.close()


def get_block_pnl(block_name):
    """Calculate total PnL for block"""
    db = SessionLocal()
    try:
        positions = db.query(Position).filter(
            Position.block_name == block_name,
            Position.status == "open"
        ).all()
        total_pnl = sum(pos.pnl for pos in positions)
        return total_pnl
    finally:
        db.close()


def get_daily_stats(date):
    """Get daily statistics"""
    db = SessionLocal()
    try:
        stats = db.query(Statistics).filter(Statistics.date == date).first()
        return stats
    finally:
        db.close()


def update_daily_stats(date, total_pnl, total_blocks, winning_blocks, losing_blocks, total_positions):
    """Update daily statistics"""
    db = SessionLocal()
    try:
        stats = db.query(Statistics).filter(Statistics.date == date).first()
        if stats:
            stats.total_pnl = total_pnl
            stats.total_blocks = total_blocks
            stats.winning_blocks = winning_blocks
            stats.losing_blocks = losing_blocks
            stats.total_positions = total_positions
        else:
            stats = Statistics(
                date=date,
                total_pnl=total_pnl,
                total_blocks=total_blocks,
                winning_blocks=winning_blocks,
                losing_blocks=losing_blocks,
                total_positions=total_positions
            )
            db.add(stats)
        db.commit()
    finally:
        db.close()