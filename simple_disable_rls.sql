-- =====================================================
-- SIMPLE RLS DISABLE FOR TESTING
-- =====================================================

-- Disable RLS entirely on all tables for testing
ALTER TABLE public.user_profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.clips DISABLE ROW LEVEL SECURITY;  
ALTER TABLE public.transcripts DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis DISABLE ROW LEVEL SECURITY;

-- Drop all policies entirely
DROP POLICY IF EXISTS "user_profiles_select" ON public.user_profiles;
DROP POLICY IF EXISTS "user_profiles_insert" ON public.user_profiles;
DROP POLICY IF EXISTS "user_profiles_update" ON public.user_profiles;
DROP POLICY IF EXISTS "clips_all" ON public.clips;
DROP POLICY IF EXISTS "transcripts_all" ON public.transcripts;
DROP POLICY IF EXISTS "analysis_all" ON public.analysis;

-- Drop any other existing policies
DROP POLICY IF EXISTS "Users can view own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;
DROP POLICY IF EXISTS "Admins can view all profiles" ON user_profiles;
DROP POLICY IF EXISTS "Users can view own clips" ON clips;
DROP POLICY IF EXISTS "Users can insert own clips" ON clips;
DROP POLICY IF EXISTS "Users can update own clips" ON clips;
DROP POLICY IF EXISTS "Users can delete own clips" ON clips;
DROP POLICY IF EXISTS "Admins can view all clips" ON clips;
DROP POLICY IF EXISTS "Users can view own segments" ON segments;
DROP POLICY IF EXISTS "Users can insert own segments" ON segments;
DROP POLICY IF EXISTS "Users can update own segments" ON segments;
DROP POLICY IF EXISTS "Users can delete own segments" ON segments;
DROP POLICY IF EXISTS "Users can view own analysis" ON analysis;
DROP POLICY IF EXISTS "Users can insert own analysis" ON analysis;
DROP POLICY IF EXISTS "Users can view own vectors" ON vectors;
DROP POLICY IF EXISTS "Users can insert own vectors" ON vectors;
DROP POLICY IF EXISTS "Users can view own transcripts" ON transcripts;
DROP POLICY IF EXISTS "Users can insert own transcripts" ON transcripts;

-- Test simple query to confirm no recursion errors
SELECT count(*) as user_profile_count FROM public.user_profiles;