from sqlalchemy import create_engine, Column, String, Float, DateTime, Boolean, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Block(Base):
    """Trading block (A, B, C, D, E)"""
    __tablename__ = "blocks"

    id = Column(Integer, primary_key=True, index=True)
    block_name = Column(String, unique=True, index=True)  # A, B, C, D, E
    status = Column(String, default="inactive")  # active, closed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    stop_line = Column(Float, nullable=True)
    tp_price = Column(Float, nullable=True)
    initial_pnl = Column(Float, default=0.0)
    final_pnl = Column(Float, default=0.0)
    close_reason = Column(String, nullable=True)  # stop_line, tp, manual
    notes = Column(Text, nullable=True)


class Position(Base):
    """Position in a block"""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    block_name = Column(String, index=True)  # Reference to Block
    side = Column(String)  # LONG, SHORT
    entry_price = Column(Float)
    quantity = Column(Float)
    status = Column(String, default="open")  # open, closed
    close_price = Column(Float, nullable=True)
    pnl = Column(Float, default=0.0)
    pnl_percent = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    binance_position_id = Column(String, nullable=True)


class Event(Base):
    """Event log for channel"""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String)  # block_created, position_added, block_closed, etc
    block_name = Column(String, nullable=True)
    symbol = Column(String, nullable=True)
    message = Column(Text)
    data = Column(Text, nullable=True)  # JSON for additional data
    telegram_message_id = Column(Integer, nullable=True)


class Statistics(Base):
    """Daily/Weekly/Monthly statistics"""
    __tablename__ = "statistics"

    id = Column(Integer, primary_key=True, index=True)
    period = Column(String)  # daily, weekly, monthly
    date = Column(String, unique=True)  # YYYY-MM-DD or YYYY-W or YYYY-M
    total_pnl = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    closed_blocks = Column(Integer, default=0)
    win_count = Column(Integer, default=0)
    loss_count = Column(Integer, default=0)
    winrate = Column(Float, default=0.0)
    best_block = Column(String, nullable=True)
    worst_block = Column(String, nullable=True)


# Create tables
Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_block(block_name, stop_line=None, tp_price=None):
    """Create new block"""
    db = SessionLocal()
    block = Block(
        block_name=block_name,
        status="active",
        stop_line=stop_line,
        tp_price=tp_price
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    db.close()
    return block


def get_active_block(block_name):
    """Get active block"""
    db = SessionLocal()
    block = db.query(Block).filter(
        Block.block_name == block_name,
        Block.status == "active"
    ).first()
    db.close()
    return block


def get_all_blocks():
    """Get all blocks"""
    db = SessionLocal()
    blocks = db.query(Block).all()
    db.close()
    return blocks


def add_position_to_block(block_name, symbol, side, entry_price, quantity):
    """Add position to block"""
    db = SessionLocal()
    position = Position(
        symbol=symbol,
        block_name=block_name,
        side=side,
        entry_price=entry_price,
        quantity=quantity
    )
    db.add(position)
    db.commit()
    db.refresh(position)
    db.close()
    return position


def get_block_positions(block_name):
    """Get all positions in block"""
    db = SessionLocal()
    positions = db.query(Position).filter(
        Position.block_name == block_name,
        Position.status == "open"
    ).all()
    db.close()
    return positions


def close_block(block_name, close_reason, final_pnl):
    """Close block"""
    db = SessionLocal()
    block = db.query(Block).filter(Block.block_name == block_name).first()
    if block:
        block.status = "closed"
        block.closed_at = datetime.utcnow()
        block.close_reason = close_reason
        block.final_pnl = final_pnl
        db.commit()
    db.close()


def log_event(event_type, message, block_name=None, symbol=None, data=None):
    """Log event"""
    db = SessionLocal()
    event = Event(
        event_type=event_type,
        block_name=block_name,
        symbol=symbol,
        message=message,
        data=data
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    db.close()
    return event


def get_block_history(limit=10):
    """Get closed blocks"""
    db = SessionLocal()
    blocks = db.query(Block).filter(Block.status == "closed").order_by(
        Block.closed_at.desc()
    ).limit(limit).all()
    db.close()
    return blocks


def get_statistics(period="daily", date=None):
    """Get statistics"""
    db = SessionLocal()
    stats = db.query(Statistics).filter(
        Statistics.period == period,
        Statistics.date == date
    ).first()
    db.close()
    return stats