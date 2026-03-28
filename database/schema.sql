-- ═══════════════════════════════════════════════════════════════
-- database/schema.sql
-- AlgoBot Pro — PostgreSQL Database Schema
--
-- HOW TO CREATE THE DATABASE:
--   1. Install PostgreSQL
--   2. Create database:
--        psql -U postgres -c "CREATE DATABASE algobot;"
--   3. Run this schema:
--        psql -U postgres -d algobot -f database/schema.sql
--   4. Update .env:
--        DATABASE_URL=postgresql://postgres:password@localhost:5432/algobot
--
-- TABLES:
--   users         — registered subscribers
--   signals       — every generated signal (permanent log)
--   positions     — paper trade positions
--   trades        — completed paper trades with P&L
--   subscriptions — user subscription/billing records
--   model_runs    — log of every model training run
-- ═══════════════════════════════════════════════════════════════

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- For UUID generation

-- ── users ─────────────────────────────────────────────────────────────────────
-- Every person who signs up for AlgoBot Pro
CREATE TABLE IF NOT EXISTS users (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id     VARCHAR(50) UNIQUE,                   -- Telegram chat ID
    email           VARCHAR(255) UNIQUE,                  -- Email address
    name            VARCHAR(100),                         -- Display name
    risk_level      VARCHAR(10)  DEFAULT 'medium'
                    CHECK (risk_level IN ('low', 'medium', 'high')),
    capital         NUMERIC(15,2) DEFAULT 50000.00,       -- Trading capital in Rs
    is_active       BOOLEAN      DEFAULT TRUE,
    is_premium      BOOLEAN      DEFAULT FALSE,           -- Paid subscriber?
    subscription_tier VARCHAR(20) DEFAULT 'free'
                    CHECK (subscription_tier IN ('free', 'premium', 'pro', 'enterprise')),
    coins_tracked   TEXT[]       DEFAULT ARRAY['BTC_USD', 'ETH_USD', 'BNB_USD', 'SOL_USD'],
    alert_telegram  BOOLEAN      DEFAULT TRUE,
    alert_email     BOOLEAN      DEFAULT FALSE,
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- ── signals ───────────────────────────────────────────────────────────────────
-- Permanent log of every signal ever generated
-- This is the source of truth for the dashboard history page
CREATE TABLE IF NOT EXISTS signals (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    coin            VARCHAR(20) NOT NULL,                 -- e.g. BTC_USD
    signal_type     VARCHAR(10) NOT NULL
                    CHECK (signal_type IN ('BUY', 'SELL', 'HOLD')),
    confidence      NUMERIC(5,4) NOT NULL,                -- 0.0000 to 1.0000
    price           NUMERIC(20,4) NOT NULL,               -- Asset price at signal time
    entry_low       NUMERIC(20,4),
    entry_high      NUMERIC(20,4),
    target_price    NUMERIC(20,4),
    stop_loss_price NUMERIC(20,4),
    risk_reward     NUMERIC(6,2),
    rsi             NUMERIC(6,2),
    macd_histogram  NUMERIC(12,6),
    volume_ratio    NUMERIC(8,4),
    atr             NUMERIC(20,4),
    reasons         TEXT[],                               -- Array of reason strings
    model_version   VARCHAR(20) DEFAULT 'v1',
    generated_at    TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast dashboard queries
CREATE INDEX IF NOT EXISTS idx_signals_coin ON signals(coin);
CREATE INDEX IF NOT EXISTS idx_signals_generated_at ON signals(generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_signal_type ON signals(signal_type);

-- ── positions ─────────────────────────────────────────────────────────────────
-- Currently open paper trading positions
CREATE TABLE IF NOT EXISTS positions (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID        REFERENCES users(id) ON DELETE CASCADE,
    signal_id       UUID        REFERENCES signals(id),
    coin            VARCHAR(20) NOT NULL,
    direction       VARCHAR(10) NOT NULL
                    CHECK (direction IN ('LONG', 'SHORT')),
    entry_price     NUMERIC(20,4) NOT NULL,
    quantity        NUMERIC(20,8) NOT NULL,
    position_value  NUMERIC(15,2) NOT NULL,              -- Rs invested
    stop_loss       NUMERIC(20,4),
    target          NUMERIC(20,4),
    opened_at       TIMESTAMPTZ DEFAULT NOW(),
    is_open         BOOLEAN DEFAULT TRUE,
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_positions_user ON positions(user_id);
CREATE INDEX IF NOT EXISTS idx_positions_open  ON positions(is_open) WHERE is_open = TRUE;

-- ── trades ────────────────────────────────────────────────────────────────────
-- Completed paper trades — positions that have been closed
CREATE TABLE IF NOT EXISTS trades (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID        REFERENCES users(id) ON DELETE CASCADE,
    position_id     UUID        REFERENCES positions(id),
    coin            VARCHAR(20) NOT NULL,
    direction       VARCHAR(10) NOT NULL,
    entry_price     NUMERIC(20,4) NOT NULL,
    exit_price      NUMERIC(20,4) NOT NULL,
    quantity        NUMERIC(20,8) NOT NULL,
    position_value  NUMERIC(15,2) NOT NULL,
    gross_pnl       NUMERIC(15,2),                       -- Profit/loss before fees
    fee             NUMERIC(10,2),                       -- Trading fee
    net_pnl         NUMERIC(15,2),                       -- Profit/loss after fees
    pnl_pct         NUMERIC(8,4),                        -- % return on position
    result          VARCHAR(10)
                    CHECK (result IN ('WIN', 'LOSS', 'BREAKEVEN')),
    hold_duration_h INTEGER,                             -- Hours position was held
    opened_at       TIMESTAMPTZ,
    closed_at       TIMESTAMPTZ DEFAULT NOW(),
    exit_reason     VARCHAR(50)                          -- 'SELL_SIGNAL', 'STOP_LOSS', 'TIMEOUT'
);

CREATE INDEX IF NOT EXISTS idx_trades_user    ON trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_coin    ON trades(coin);
CREATE INDEX IF NOT EXISTS idx_trades_closed  ON trades(closed_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_result  ON trades(result);

-- ── subscriptions ─────────────────────────────────────────────────────────────
-- User subscription and billing records
CREATE TABLE IF NOT EXISTS subscriptions (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID        REFERENCES users(id) ON DELETE CASCADE,
    tier            VARCHAR(20) NOT NULL
                    CHECK (tier IN ('free', 'premium', 'pro', 'enterprise')),
    price_per_month NUMERIC(10,2),
    currency        VARCHAR(5)  DEFAULT 'INR',
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    is_active       BOOLEAN     DEFAULT TRUE,
    payment_id      VARCHAR(100),                        -- Razorpay payment ID
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_subs_user   ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subs_active ON subscriptions(is_active) WHERE is_active = TRUE;

-- ── model_runs ────────────────────────────────────────────────────────────────
-- Log every model training run — for tracking model performance over time
CREATE TABLE IF NOT EXISTS model_runs (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    coin            VARCHAR(20) NOT NULL,
    version         VARCHAR(20) NOT NULL,
    accuracy        NUMERIC(6,4),
    auc_roc         NUMERIC(6,4),
    win_rate        NUMERIC(6,4),
    total_return    NUMERIC(8,4),
    max_drawdown    NUMERIC(8,4),
    sharpe_ratio    NUMERIC(8,4),
    train_rows      INTEGER,
    test_rows       INTEGER,
    feature_count   INTEGER,
    is_deployed     BOOLEAN     DEFAULT FALSE,
    trained_at      TIMESTAMPTZ DEFAULT NOW(),
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_coin ON model_runs(coin);
CREATE INDEX IF NOT EXISTS idx_runs_date ON model_runs(trained_at DESC);

-- ── Trigger: auto-update updated_at on users ──────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS users_updated_at ON users;
CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Default free tier user (for testing) ──────────────────────────────────────
-- Remove or modify before production deployment
INSERT INTO users (
    telegram_id, name, risk_level, capital,
    subscription_tier, is_premium
)
VALUES (
    'YOUR_TELEGRAM_CHAT_ID', 'Admin User', 'medium', 50000.00,
    'pro', TRUE
)
ON CONFLICT (telegram_id) DO NOTHING;

-- ── Views for dashboard ───────────────────────────────────────────────────────

-- View: latest signal per coin
CREATE OR REPLACE VIEW latest_signals AS
SELECT DISTINCT ON (coin)
    id, coin, signal_type, confidence, price,
    target_price, stop_loss_price, rsi, generated_at
FROM signals
ORDER BY coin, generated_at DESC;

-- View: user portfolio summary
CREATE OR REPLACE VIEW portfolio_summary AS
SELECT
    u.id         AS user_id,
    u.name,
    u.capital    AS initial_capital,
    COUNT(t.id)  AS total_trades,
    SUM(CASE WHEN t.result = 'WIN'  THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) AS losses,
    COALESCE(SUM(t.net_pnl), 0)  AS total_pnl,
    COALESCE(AVG(t.pnl_pct), 0)  AS avg_return_pct
FROM users u
LEFT JOIN trades t ON t.user_id = u.id
GROUP BY u.id, u.name, u.capital;

-- ── Done ──────────────────────────────────────────────────────────────────────
-- Schema created successfully.
-- Run: python database/models.py  to verify connection and ORM models.