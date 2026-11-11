-- ==============================================================================
-- AMQUANT: Supabase Authentication, Profiles, Scenarios, and Research History
-- Migration: 20261111000000_auth_and_workspaces.sql
-- ==============================================================================

-- 1. PROFILES TABLE
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Constraint: reasonable display name length
ALTER TABLE public.profiles 
    ADD CONSTRAINT check_display_name_length 
    CHECK (display_name IS NULL OR (char_length(display_name) >= 1 AND char_length(display_name) <= 100));

-- 2. SAVED SCENARIOS TABLE
CREATE TABLE IF NOT EXISTS public.saved_scenarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    module_name TEXT NOT NULL,
    scenario_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT check_scenario_title_length CHECK (char_length(title) >= 1 AND char_length(title) <= 120),
    CONSTRAINT check_module_name CHECK (module_name IN ('foundations', 'bayesian', 'stochastic', 'options', 'intelligence'))
);

-- 3. RESEARCH HISTORY TABLE
CREATE TABLE IF NOT EXISTS public.research_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    module_name TEXT NOT NULL,
    scenario_id UUID REFERENCES public.saved_scenarios(id) ON DELETE SET NULL,
    summary JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT check_history_module_name CHECK (module_name IN ('foundations', 'bayesian', 'stochastic', 'options', 'intelligence'))
);

-- 4. PERFORMANCE INDEXES
CREATE INDEX IF NOT EXISTS idx_saved_scenarios_user_created 
    ON public.saved_scenarios (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_saved_scenarios_user_module 
    ON public.saved_scenarios (user_id, module_name);

CREATE INDEX IF NOT EXISTS idx_research_history_user_created 
    ON public.research_history (user_id, created_at DESC);

-- 5. AUTOMATIC TIMESTAMP TRIGGER
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trigger_profiles_updated_at ON public.profiles;
CREATE TRIGGER trigger_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS trigger_saved_scenarios_updated_at ON public.saved_scenarios;
CREATE TRIGGER trigger_saved_scenarios_updated_at
    BEFORE UPDATE ON public.saved_scenarios
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- 6. AUTOMATIC USER PROFILE CREATION TRIGGER
-- Securely creates a profile row when a new user registers in auth.users
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
    raw_name TEXT;
BEGIN
    -- Extract display_name safely from user metadata if provided, otherwise default to email username
    raw_name := NULLIF(trim(NEW.raw_user_meta_data->>'display_name'), '');
    IF raw_name IS NULL AND NEW.email IS NOT NULL THEN
        raw_name := split_part(NEW.email, '@', 1);
    END IF;

    -- Enforce safe max length
    IF raw_name IS NOT NULL AND length(raw_name) > 100 THEN
        raw_name := substring(raw_name FROM 1 FOR 100);
    END IF;

    INSERT INTO public.profiles (id, display_name, created_at, updated_at)
    VALUES (NEW.id, raw_name, now(), now())
    ON CONFLICT (id) DO UPDATE
    SET display_name = EXCLUDED.display_name,
        updated_at = now();
        
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 7. ROW LEVEL SECURITY (RLS) POLICIES
-- Strict isolation: users can ONLY access their own rows

-- Profiles RLS
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
CREATE POLICY "Users can view own profile"
    ON public.profiles FOR SELECT
    TO authenticated
    USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    TO authenticated
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

DROP POLICY IF EXISTS "Users can insert own profile" ON public.profiles;
CREATE POLICY "Users can insert own profile"
    ON public.profiles FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = id);

-- Saved Scenarios RLS
ALTER TABLE public.saved_scenarios ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own saved scenarios" ON public.saved_scenarios;
CREATE POLICY "Users can view own saved scenarios"
    ON public.saved_scenarios FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own saved scenarios" ON public.saved_scenarios;
CREATE POLICY "Users can insert own saved scenarios"
    ON public.saved_scenarios FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own saved scenarios" ON public.saved_scenarios;
CREATE POLICY "Users can update own saved scenarios"
    ON public.saved_scenarios FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own saved scenarios" ON public.saved_scenarios;
CREATE POLICY "Users can delete own saved scenarios"
    ON public.saved_scenarios FOR DELETE
    TO authenticated
    USING (auth.uid() = user_id);

-- Research History RLS
ALTER TABLE public.research_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own research history" ON public.research_history;
CREATE POLICY "Users can view own research history"
    ON public.research_history FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own research history" ON public.research_history;
CREATE POLICY "Users can insert own research history"
    ON public.research_history FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own research history" ON public.research_history;
CREATE POLICY "Users can delete own research history"
    ON public.research_history FOR DELETE
    TO authenticated
    USING (auth.uid() = user_id);

