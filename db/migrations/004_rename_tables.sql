-- Rename legacy raw_* tables to final names

ALTER TABLE IF EXISTS public.raw_algo_bull_strategies RENAME TO algo_bull_strategies;
ALTER TABLE IF EXISTS public.raw_finstock_strategies RENAME TO finstock_strategies;
ALTER TABLE IF EXISTS public.raw_live_backtesting RENAME TO live_backtesting;
ALTER TABLE IF EXISTS public.raw_live_scanners RENAME TO live_scanners;
ALTER TABLE IF EXISTS public.raw_streak_trading_strategies RENAME TO streak_trading_strategies;
ALTER TABLE IF EXISTS public.raw_streak_indicator_suggestions RENAME TO streak_indicator_suggestions;

ALTER INDEX IF EXISTS ix_raw_finstock_name RENAME TO ix_finstock_name;
ALTER INDEX IF EXISTS ix_raw_streak_trading_name RENAME TO ix_streak_trading_name;
ALTER INDEX IF EXISTS ix_raw_indicator_suggestions_indicator RENAME TO ix_indicator_suggestions_indicator;
