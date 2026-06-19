-- Ensure indicator column is NOT NULL with a DEFAULT 'UNKNOWN'
-- Run update/backfill to convert any existing NULLs to 'UNKNOWN'

-- For public.strategies
ALTER TABLE public.strategies ADD COLUMN IF NOT EXISTS indicator TEXT;
UPDATE public.strategies SET indicator = 'UNKNOWN' WHERE indicator IS NULL OR TRIM(indicator) = '';
ALTER TABLE public.strategies ALTER COLUMN indicator SET DEFAULT 'UNKNOWN';
ALTER TABLE public.strategies ALTER COLUMN indicator SET NOT NULL;

-- For public.independent_strategies
ALTER TABLE public.independent_strategies ADD COLUMN IF NOT EXISTS indicator TEXT;
UPDATE public.independent_strategies SET indicator = 'UNKNOWN' WHERE indicator IS NULL OR TRIM(indicator) = '';
ALTER TABLE public.independent_strategies ALTER COLUMN indicator SET DEFAULT 'UNKNOWN';
ALTER TABLE public.independent_strategies ALTER COLUMN indicator SET NOT NULL;
