-- Additional tables not in streak_ai_backup_full.sql

CREATE TABLE IF NOT EXISTS public.company_profiles (
    ticker TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    industry TEXT,
    description TEXT,
    source TEXT
);

CREATE INDEX IF NOT EXISTS ix_company_profiles_sector ON public.company_profiles (sector);
CREATE INDEX IF NOT EXISTS ix_company_profiles_industry ON public.company_profiles (industry);
