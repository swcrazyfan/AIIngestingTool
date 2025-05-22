-- =====================================================
-- COMPLETE RLS POLICY RESET AND FIX
-- =====================================================

-- Disable RLS temporarily to fix the recursion issue
ALTER TABLE public.user_profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.clips DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.transcripts DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis DISABLE ROW LEVEL SECURITY;

-- Drop ALL existing policies to start fresh
DROP POLICY IF EXISTS "Users can view own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can insert own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Enable read access for own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Enable insert for own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Enable update for own profile" ON public.user_profiles;

DROP POLICY IF EXISTS "Users can manage own clips" ON public.clips;
DROP POLICY IF EXISTS "Enable all operations for authenticated users on clips" ON public.clips;

DROP POLICY IF EXISTS "Users can manage own transcripts" ON public.transcripts;
DROP POLICY IF EXISTS "Enable all operations for authenticated users on transcripts" ON public.transcripts;

DROP POLICY IF EXISTS "Users can manage own analysis" ON public.analysis;
DROP POLICY IF EXISTS "Enable all operations for authenticated users on analysis" ON public.analysis;

-- Re-enable RLS
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clips ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis ENABLE ROW LEVEL SECURITY;

-- Create simple, non-recursive policies for user_profiles
CREATE POLICY "user_profiles_select" ON public.user_profiles
    FOR SELECT USING (id = auth.uid());

CREATE POLICY "user_profiles_insert" ON public.user_profiles
    FOR INSERT WITH CHECK (id = auth.uid());

CREATE POLICY "user_profiles_update" ON public.user_profiles
    FOR UPDATE USING (id = auth.uid());

-- Create simple policies for clips (allow all operations for authenticated users)
CREATE POLICY "clips_all" ON public.clips
    FOR ALL USING (auth.uid() IS NOT NULL);

-- Create simple policies for transcripts (allow all operations for authenticated users)
CREATE POLICY "transcripts_all" ON public.transcripts
    FOR ALL USING (auth.uid() IS NOT NULL);

-- Create simple policies for analysis (allow all operations for authenticated users)
CREATE POLICY "analysis_all" ON public.analysis
    FOR ALL USING (auth.uid() IS NOT NULL);

-- Verify policies are in place
SELECT schemaname, tablename, policyname, cmd, qual 
FROM pg_policies 
WHERE schemaname = 'public' 
ORDER BY tablename, policyname;

-- Test that we can query user_profiles without recursion
SELECT count(*) FROM public.user_profiles;