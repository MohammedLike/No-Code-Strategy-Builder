-- Excel import tables (no raw_ prefix)

CREATE TABLE IF NOT EXISTS public.algo_bull_strategies (
    id SERIAL PRIMARY KEY,
    strategy_id TEXT,
    strategy_name TEXT NOT NULL,
    strategy_type TEXT,
    underlying_asset TEXT,
    entry_time TEXT,
    exit_time TEXT,
    capital TEXT,
    description TEXT,
    source_file TEXT NOT NULL DEFAULT 'Algo bull.xlsx',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.finstock_strategies (
    id SERIAL PRIMARY KEY,
    row_num INTEGER,
    strategy_name TEXT NOT NULL,
    description TEXT,
    entry_conditions TEXT,
    exit_conditions TEXT,
    risk_management TEXT,
    classification TEXT,
    source_file TEXT NOT NULL DEFAULT 'Finstock Pre Built Strategies.xlsx',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.live_backtesting (
    id SERIAL PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    category TEXT,
    direction TEXT,
    source_file TEXT NOT NULL DEFAULT 'live backtesting.xlsx',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.live_scanners (
    id SERIAL PRIMARY KEY,
    scanner_name TEXT NOT NULL,
    category TEXT,
    direction TEXT,
    source_file TEXT NOT NULL DEFAULT 'Live scanner.xlsx',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.streak_trading_strategies (
    id SERIAL PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    description TEXT,
    entry_conditions TEXT,
    exit_conditions TEXT,
    risk_management TEXT,
    classification TEXT,
    source_file TEXT NOT NULL DEFAULT 'streak_trading_strategies.xlsx',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.streak_indicator_suggestions (
    id SERIAL PRIMARY KEY,
    sheet_name TEXT NOT NULL,
    indicator TEXT,
    bias TEXT,
    suggestion TEXT,
    tag TEXT,
    category TEXT,
    supported_operators TEXT,
    source_file TEXT NOT NULL DEFAULT 'Streak_Indicators_Final_Bullish_Bearish.xlsx',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_finstock_name ON public.finstock_strategies (strategy_name);
CREATE INDEX IF NOT EXISTS ix_streak_trading_name ON public.streak_trading_strategies (strategy_name);
CREATE INDEX IF NOT EXISTS ix_indicator_suggestions_indicator ON public.streak_indicator_suggestions (indicator);
