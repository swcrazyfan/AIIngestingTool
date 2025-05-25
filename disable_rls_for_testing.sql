-- =====================================================
-- DISABLE RLS COMPLETELY FOR TESTING
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

-- Test insert into clips table directly
INSERT INTO public.clips (
    id,
    user_id, 
    filename,
    original_path,
    file_size,
    duration,
    checksum,
    created_at
) VALUES (
    gen_random_uuid(),
    auth.uid(),
    'test_video.mov',
    '/test/path.mov', 
    1000000,
    17.0,
    'test_checksum_123',
    now()
) RETURNING id;