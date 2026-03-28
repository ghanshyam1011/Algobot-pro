"""
database/models.py
====================
SQLAlchemy ORM models for AlgoBot Pro.

Maps Python classes to PostgreSQL tables defined in schema.sql.
Use these models to read/write to the database from Python code.

SETUP:
    1. Install PostgreSQL and set DATABASE_URL in .env
    2. Run schema.sql to create tables:
         psql -U postgres -d algobot -f database/schema.sql
    3. Test connection:
         python database/models.py

NOTE FOR DEVELOPMENT:
    If you don't have PostgreSQL set up, the system still works
    using JSON files (data/signal_log.json) as a fallback.
    PostgreSQL is only needed for production multi-user deployment.

DEPENDENCIES:
    pip install sqlalchemy psycopg2-binary
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, List

log = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")


# ── Check if database is configured ───────────────────────────────────────────
def is_db_configured() -> bool:
    """Return True if DATABASE_URL is set and non-empty."""
    return bool(DATABASE_URL and DATABASE_URL.strip())


# ── Only import SQLAlchemy if database is configured ─────────────────────────
if is_db_configured():
    try:
        from sqlalchemy import (
            create_engine, Column, String, Boolean, Numeric,
            Integer, Text, TIMESTAMP, ARRAY, ForeignKey,
            Index, func, text,
        )
        from sqlalchemy.dialects.postgresql import UUID
        from sqlalchemy.orm import DeclarativeBase, relationship, Session
        from sqlalchemy.pool import NullPool

        engine = create_engine(
            DATABASE_URL,
            poolclass=NullPool,      # Don't pool connections (safer for scheduled tasks)
            echo=False,              # Set True to log all SQL queries (debug only)
        )

        class Base(DeclarativeBase):
            pass

        # ── User model ────────────────────────────────────────────────────────
        class User(Base):
            __tablename__ = "users"

            id                = Column(UUID(as_uuid=True), primary_key=True,
                                       server_default=text("uuid_generate_v4()"))
            telegram_id       = Column(String(50), unique=True)
            email             = Column(String(255), unique=True)
            name              = Column(String(100))
            risk_level        = Column(String(10), default="medium")
            capital           = Column(Numeric(15, 2), default=50000.00)
            is_active         = Column(Boolean, default=True)
            is_premium        = Column(Boolean, default=False)
            subscription_tier = Column(String(20), default="free")
            coins_tracked     = Column(ARRAY(String), default=["BTC_USD","ETH_USD","BNB_USD","SOL_USD"])
            alert_telegram    = Column(Boolean, default=True)
            alert_email       = Column(Boolean, default=False)
            created_at        = Column(TIMESTAMP(timezone=True), server_default=func.now())
            updated_at        = Column(TIMESTAMP(timezone=True), server_default=func.now(),
                                       onupdate=func.now())

            # Relationships
            signals       = relationship("Signal", back_populates="user",
                                         foreign_keys="Signal.user_id", uselist=True)
            positions     = relationship("Position", back_populates="user")
            trades        = relationship("Trade", back_populates="user")
            subscriptions = relationship("Subscription", back_populates="user")

            def __repr__(self):
                return f"<User {self.name} ({self.telegram_id}) [{self.subscription_tier}]>"

            def to_dict(self) -> dict:
                return {
                    "id":           str(self.id),
                    "telegram_id":  self.telegram_id,
                    "email":        self.email,
                    "name":         self.name,
                    "risk_level":   self.risk_level,
                    "capital":      float(self.capital or 0),
                    "is_premium":   self.is_premium,
                    "tier":         self.subscription_tier,
                    "coins":        self.coins_tracked or [],
                }

        # ── Signal model ──────────────────────────────────────────────────────
        class Signal(Base):
            __tablename__ = "signals"

            id              = Column(UUID(as_uuid=True), primary_key=True,
                                     server_default=text("uuid_generate_v4()"))
            user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
            coin            = Column(String(20), nullable=False)
            signal_type     = Column(String(10), nullable=False)
            confidence      = Column(Numeric(5, 4), nullable=False)
            price           = Column(Numeric(20, 4), nullable=False)
            entry_low       = Column(Numeric(20, 4))
            entry_high      = Column(Numeric(20, 4))
            target_price    = Column(Numeric(20, 4))
            stop_loss_price = Column(Numeric(20, 4))
            risk_reward     = Column(Numeric(6, 2))
            rsi             = Column(Numeric(6, 2))
            macd_histogram  = Column(Numeric(12, 6))
            volume_ratio    = Column(Numeric(8, 4))
            atr             = Column(Numeric(20, 4))
            reasons         = Column(ARRAY(Text))
            model_version   = Column(String(20), default="v1")
            generated_at    = Column(TIMESTAMP(timezone=True), server_default=func.now())
            created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())

            user = relationship("User", back_populates="signals", foreign_keys=[user_id])

            __table_args__ = (
                Index("idx_signals_coin", "coin"),
                Index("idx_signals_generated_at", "generated_at"),
            )

            def __repr__(self):
                return f"<Signal {self.coin} {self.signal_type} ({float(self.confidence):.0%})>"

            def to_dict(self) -> dict:
                return {
                    "id":           str(self.id),
                    "coin":         self.coin,
                    "signal":       self.signal_type,
                    "confidence":   float(self.confidence or 0),
                    "price":        float(self.price or 0),
                    "target":       float(self.target_price or 0),
                    "stop_loss":    float(self.stop_loss_price or 0),
                    "rsi":          float(self.rsi or 0),
                    "reasons":      self.reasons or [],
                    "generated_at": self.generated_at.isoformat() if self.generated_at else None,
                }

        # ── Position model ────────────────────────────────────────────────────
        class Position(Base):
            __tablename__ = "positions"

            id             = Column(UUID(as_uuid=True), primary_key=True,
                                    server_default=text("uuid_generate_v4()"))
            user_id        = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
            signal_id      = Column(UUID(as_uuid=True), ForeignKey("signals.id"))
            coin           = Column(String(20), nullable=False)
            direction      = Column(String(10), nullable=False)
            entry_price    = Column(Numeric(20, 4), nullable=False)
            quantity       = Column(Numeric(20, 8), nullable=False)
            position_value = Column(Numeric(15, 2), nullable=False)
            stop_loss      = Column(Numeric(20, 4))
            target         = Column(Numeric(20, 4))
            opened_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())
            is_open        = Column(Boolean, default=True)
            notes          = Column(Text)

            user = relationship("User", back_populates="positions")

            def __repr__(self):
                return f"<Position {self.direction} {self.coin} @ {self.entry_price}>"

        # ── Trade model ───────────────────────────────────────────────────────
        class Trade(Base):
            __tablename__ = "trades"

            id             = Column(UUID(as_uuid=True), primary_key=True,
                                    server_default=text("uuid_generate_v4()"))
            user_id        = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
            position_id    = Column(UUID(as_uuid=True), ForeignKey("positions.id"))
            coin           = Column(String(20), nullable=False)
            direction      = Column(String(10), nullable=False)
            entry_price    = Column(Numeric(20, 4), nullable=False)
            exit_price     = Column(Numeric(20, 4), nullable=False)
            quantity       = Column(Numeric(20, 8), nullable=False)
            position_value = Column(Numeric(15, 2), nullable=False)
            gross_pnl      = Column(Numeric(15, 2))
            fee            = Column(Numeric(10, 2))
            net_pnl        = Column(Numeric(15, 2))
            pnl_pct        = Column(Numeric(8, 4))
            result         = Column(String(10))
            hold_duration_h= Column(Integer)
            opened_at      = Column(TIMESTAMP(timezone=True))
            closed_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())
            exit_reason    = Column(String(50))

            user = relationship("User", back_populates="trades")

            def __repr__(self):
                return f"<Trade {self.coin} {self.result} pnl={self.net_pnl}>"

        # ── Subscription model ────────────────────────────────────────────────
        class Subscription(Base):
            __tablename__ = "subscriptions"

            id              = Column(UUID(as_uuid=True), primary_key=True,
                                     server_default=text("uuid_generate_v4()"))
            user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
            tier            = Column(String(20), nullable=False)
            price_per_month = Column(Numeric(10, 2))
            currency        = Column(String(5), default="INR")
            started_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())
            expires_at      = Column(TIMESTAMP(timezone=True))
            is_active       = Column(Boolean, default=True)
            payment_id      = Column(String(100))
            notes           = Column(Text)

            user = relationship("User", back_populates="subscriptions")

        # ── ModelRun model ────────────────────────────────────────────────────
        class ModelRun(Base):
            __tablename__ = "model_runs"

            id            = Column(UUID(as_uuid=True), primary_key=True,
                                   server_default=text("uuid_generate_v4()"))
            coin          = Column(String(20), nullable=False)
            version       = Column(String(20), nullable=False)
            accuracy      = Column(Numeric(6, 4))
            auc_roc       = Column(Numeric(6, 4))
            win_rate      = Column(Numeric(6, 4))
            total_return  = Column(Numeric(8, 4))
            max_drawdown  = Column(Numeric(8, 4))
            sharpe_ratio  = Column(Numeric(8, 4))
            train_rows    = Column(Integer)
            test_rows     = Column(Integer)
            feature_count = Column(Integer)
            is_deployed   = Column(Boolean, default=False)
            trained_at    = Column(TIMESTAMP(timezone=True), server_default=func.now())
            notes         = Column(Text)

            def __repr__(self):
                return f"<ModelRun {self.coin}/{self.version} acc={self.accuracy}>"

        DB_AVAILABLE = True
        log.info("Database models loaded successfully.")

    except ImportError:
        DB_AVAILABLE = False
        log.warning(
            "SQLAlchemy or psycopg2 not installed.\n"
            "Run: pip install sqlalchemy psycopg2-binary\n"
            "Using JSON file storage as fallback."
        )
    except Exception as e:
        DB_AVAILABLE = False
        log.warning(f"Database setup failed: {e}\nUsing JSON file storage as fallback.")

else:
    DB_AVAILABLE = False
    log.debug("DATABASE_URL not set — using JSON file storage.")


# ── Database helper functions ──────────────────────────────────────────────────

def get_session():
    """
    Get a database session.
    Use as a context manager:

        with get_session() as session:
            users = session.query(User).all()

    Returns None if database is not configured.
    """
    if not DB_AVAILABLE:
        return None
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def save_signal_to_db(signal_dict: dict) -> bool:
    """
    Save a formatted signal dict to the signals table.

    Args:
        signal_dict: Output of formatter.format_signal()

    Returns:
        bool: True if saved, False if DB not available
    """
    if not DB_AVAILABLE:
        return False

    try:
        session = get_session()
        record  = Signal(
            coin            = signal_dict.get("coin"),
            signal_type     = signal_dict.get("signal"),
            confidence      = signal_dict.get("confidence"),
            price           = signal_dict.get("price"),
            entry_low       = signal_dict.get("entry_low"),
            entry_high      = signal_dict.get("entry_high"),
            target_price    = signal_dict.get("target_price"),
            stop_loss_price = signal_dict.get("stop_loss_price"),
            risk_reward     = signal_dict.get("risk_reward"),
            rsi             = signal_dict.get("rsi"),
            macd_histogram  = signal_dict.get("macd_histogram"),
            volume_ratio    = signal_dict.get("volume_ratio"),
            atr             = signal_dict.get("atr"),
            reasons         = signal_dict.get("reasons", []),
            model_version   = signal_dict.get("model_version", "v1"),
        )
        session.add(record)
        session.commit()
        session.close()
        return True
    except Exception as e:
        log.error(f"Failed to save signal to DB: {e}")
        return False


def get_user_by_telegram_id(telegram_id: str) -> Optional[dict]:
    """
    Look up a user by their Telegram chat ID.

    Args:
        telegram_id: Telegram chat ID string

    Returns:
        dict or None
    """
    if not DB_AVAILABLE:
        return None

    try:
        session = get_session()
        user    = session.query(User).filter_by(telegram_id=telegram_id).first()
        session.close()
        return user.to_dict() if user else None
    except Exception as e:
        log.error(f"DB query failed: {e}")
        return None


def test_connection() -> bool:
    """
    Test the database connection.

    Returns:
        bool: True if connection works
    """
    if not DB_AVAILABLE:
        print("Database not configured (DATABASE_URL not set).")
        print("System is using JSON file storage — this is fine for development.")
        return False

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database connection OK!")
        return True
    except Exception as e:
        print(f"Database connection FAILED: {e}")
        print("Check DATABASE_URL in .env and make sure PostgreSQL is running.")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    print("Testing database connection ...")
    ok = test_connection()
    if ok:
        print("\nAll database models are ready.")
        print("Run schema.sql if you haven't already:")
        print("  psql -U postgres -d algobot -f database/schema.sql")