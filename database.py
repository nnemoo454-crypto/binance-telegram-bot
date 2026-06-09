from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class TradingBlock(Base):
    """Model for trading blocks"""
    __tablename__ = "trading_blocks"

    id = Column(Integer, primary_key=True, index=True)
    block_id = Column(String, unique=True, index=True)
    pair = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    entry_price = Column(Float)
    stop_line = Column(Float)
    tp = Column(Float)
    volume = Column(Float)
    status = Column(String, default="active")  # active, closed, cancelled
    pnl = Column(Float, default=0.0)
    closed_at = Column(DateTime, nullable=True)
    reason = Column(String, nullable=True)  # tp_hit, stop_line, manual_cancel


class OrderRecord(Base):
    """Model for individual orders in block"""
    __tablename__ = "order_records"

    id = Column(Integer, primary_key=True, index=True)
    block_id = Column(String, index=True)
    order_id = Column(String)
    pair = Column(String)
    price = Column(Float)
    volume = Column(Float)
    status = Column(String)  # pending, filled, cancelled
    filled_at = Column(DateTime, nullable=True)


# Create tables
Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_block(block_id, pair, entry_price, stop_line, tp, volume):
    """Create new trading block"""
    db = SessionLocal()
    block = TradingBlock(
        block_id=block_id,
        pair=pair,
        entry_price=entry_price,
        stop_line=stop_line,
        tp=tp,
        volume=volume
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    db.close()
    return block


def get_active_blocks():
    """Get all active blocks"""
    db = SessionLocal()
    blocks = db.query(TradingBlock).filter(TradingBlock.status == "active").all()
    db.close()
    return blocks


def update_block_status(block_id, status, pnl=None, reason=None):
    """Update block status"""
    db = SessionLocal()
    block = db.query(TradingBlock).filter(TradingBlock.block_id == block_id).first()
    if block:
        block.status = status
        block.closed_at = datetime.utcnow()
        if pnl is not None:
            block.pnl = pnl
        if reason:
            block.reason = reason
        db.commit()
    db.close()


def add_order_record(block_id, order_id, pair, price, volume):
    """Add order record"""
    db = SessionLocal()
    record = OrderRecord(
        block_id=block_id,
        order_id=order_id,
        pair=pair,
        price=price,
        volume=volume,
        status="pending"
    )
    db.add(record)
    db.commit()
    db.close()


def get_block_history(limit=10):
    """Get closed blocks"""
    db = SessionLocal()
    blocks = db.query(TradingBlock).filter(
        TradingBlock.status.in_(["closed", "cancelled"])
    ).order_by(TradingBlock.closed_at.desc()).limit(limit).all()
    db.close()
    return blocks


def get_statistics():
    """Get trading statistics"""
    db = SessionLocal()
    
    total_blocks = db.query(TradingBlock).count()
    closed_blocks = db.query(TradingBlock).filter(TradingBlock.status == "closed").count()
    total_pnl = db.query(TradingBlock).with_entities(
        db.func.sum(TradingBlock.pnl)
    ).scalar() or 0.0
    
    db.close()
    
    return {
        "total_blocks": total_blocks,
        "closed_blocks": closed_blocks,
        "total_pnl": total_pnl,
        "win_rate": (closed_blocks / total_blocks * 100) if total_blocks > 0 else 0
    }