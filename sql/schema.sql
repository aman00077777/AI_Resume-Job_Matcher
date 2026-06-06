-- =============================================================================
-- CLEAN RESET + RECREATE — Run this in Supabase SQL Editor
-- =============================================================================

-- ─── Drop triggers ───────────────────────────────────────────────────────────
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP TRIGGER IF EXISTS set_updated_at_users ON public.users;
DROP TRIGGER IF EXISTS set_updated_at_sources ON public.company_sources;
DROP TRIGGER IF EXISTS set_updated_at_matches ON public.job_matches;

-- ─── Drop functions ───────────────────────────────────────────────────────────
DROP FUNCTION IF EXISTS public.handle_new_user() CASCADE;
DROP FUNCTION IF EXISTS public.update_updated_at() CASCADE;

-- ─── Drop tables (order matters due to foreign keys) ─────────────────────────
DROP TABLE IF EXISTS public.scrape_runs CASCADE;
DROP TABLE IF EXISTS public.job_matches CASCADE;
DROP TABLE IF EXISTS public.job_listings CASCADE;
DROP TABLE IF EXISTS public.company_sources CASCADE;
DROP TABLE IF EXISTS public.resumes CASCADE;
DROP TABLE IF EXISTS public.users CASCADE;

-- ─── Drop custom types ────────────────────────────────────────────────────────
DROP TYPE IF EXISTS match_status CASCADE;

-- =============================================================================
-- RECREATE EVERYTHING
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Users
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL DEFAULT '',
    location_preference TEXT NOT NULL DEFAULT '',
    discord_webhook_url TEXT NOT NULL DEFAULT '',
    match_threshold INTEGER NOT NULL DEFAULT 80 CHECK (match_threshold BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile"
    ON public.users FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.users FOR UPDATE
    USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile"
    ON public.users FOR INSERT
    WITH CHECK (auth.uid() = id);

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.users (id, full_name)
    VALUES (NEW.id, COALESCE(NEW.raw_user_meta_data->>'full_name', ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Resumes
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE public.resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    raw_text TEXT NOT NULL DEFAULT '',
    skills TEXT[] NOT NULL DEFAULT '{}',
    experience_years INTEGER NOT NULL DEFAULT 0,
    education JSONB NOT NULL DEFAULT '[]',
    job_titles TEXT[] NOT NULL DEFAULT '{}',
    summary TEXT NOT NULL DEFAULT '',
    parsed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_resumes_user_id ON public.resumes(user_id);

ALTER TABLE public.resumes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own resumes"
    ON public.resumes FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Company Sources
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE public.company_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    company_name TEXT NOT NULL,
    career_url TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sources_user_id ON public.company_sources(user_id);

ALTER TABLE public.company_sources ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own sources"
    ON public.company_sources FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Job Listings
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE public.job_listings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES public.company_sources(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_listings_source_id ON public.job_listings(source_id);
CREATE INDEX idx_listings_content_hash ON public.job_listings(content_hash);

ALTER TABLE public.job_listings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own job listings"
    ON public.job_listings FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.company_sources cs
            WHERE cs.id = source_id AND cs.user_id = auth.uid()
        )
    );

CREATE POLICY "Service can insert job listings"
    ON public.job_listings FOR INSERT
    WITH CHECK (TRUE);


-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Job Matches
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE match_status AS ENUM ('new', 'applied', 'not_interested', 'saved');

CREATE TABLE public.job_matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES public.job_listings(id) ON DELETE CASCADE,
    resume_id UUID NOT NULL REFERENCES public.resumes(id) ON DELETE CASCADE,
    overall_score INTEGER NOT NULL DEFAULT 0 CHECK (overall_score BETWEEN 0 AND 100),
    skills_score INTEGER NOT NULL DEFAULT 0 CHECK (skills_score BETWEEN 0 AND 100),
    experience_score INTEGER NOT NULL DEFAULT 0 CHECK (experience_score BETWEEN 0 AND 100),
    title_score INTEGER NOT NULL DEFAULT 0 CHECK (title_score BETWEEN 0 AND 100),
    location_score INTEGER NOT NULL DEFAULT 0 CHECK (location_score BETWEEN 0 AND 100),
    matching_skills TEXT[] NOT NULL DEFAULT '{}',
    missing_skills TEXT[] NOT NULL DEFAULT '{}',
    summary TEXT NOT NULL DEFAULT '',
    status match_status NOT NULL DEFAULT 'new',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(job_id, resume_id)
);

CREATE INDEX idx_matches_resume_id ON public.job_matches(resume_id);
CREATE INDEX idx_matches_overall_score ON public.job_matches(overall_score DESC);
CREATE INDEX idx_matches_status ON public.job_matches(status);

ALTER TABLE public.job_matches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own matches"
    ON public.job_matches FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.resumes r
            WHERE r.id = resume_id AND r.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update own match status"
    ON public.job_matches FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM public.resumes r
            WHERE r.id = resume_id AND r.user_id = auth.uid()
        )
    );

CREATE POLICY "Service can insert matches"
    ON public.job_matches FOR INSERT
    WITH CHECK (TRUE);


-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Scrape Runs
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE public.scrape_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    jobs_found INTEGER NOT NULL DEFAULT 0,
    new_jobs INTEGER NOT NULL DEFAULT 0,
    matches_found INTEGER NOT NULL DEFAULT 0,
    alerts_sent INTEGER NOT NULL DEFAULT 0,
    errors JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scrape_runs_user_id ON public.scrape_runs(user_id);

ALTER TABLE public.scrape_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own scrape runs"
    ON public.scrape_runs FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- Updated-at trigger
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at_users
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

CREATE TRIGGER set_updated_at_sources
    BEFORE UPDATE ON public.company_sources
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

CREATE TRIGGER set_updated_at_matches
    BEFORE UPDATE ON public.job_matches
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();