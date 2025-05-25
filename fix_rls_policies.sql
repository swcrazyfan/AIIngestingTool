-- =====================================================
-- FIX RLS INFINITE RECURSION ERROR
-- =====================================================

-- Drop existing problematic policies
DROP POLICY IF EXISTS "Users can view own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can insert own profile" ON public.user_profiles;

-- Create simple, non-recursive RLS policies for user_profiles
CREATE POLICY "Enable read access for own profile" ON public.user_profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Enable insert for own profile" ON public.user_profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

CREATE POLICY "Enable update for own profile" ON public.user_profiles
    FOR UPDATE USING (auth.uid() = id);

-- Drop and recreate policies for clips table to be simpler
DROP POLICY IF EXISTS "Users can manage own clips" ON public.clips;
CREATE POLICY "Enable all operations for authenticated users on clips" ON public.clips
    FOR ALL USING (auth.uid() IS NOT NULL);

-- Drop and recreate policies for transcripts table to be simpler  
DROP POLICY IF EXISTS "Users can manage own transcripts" ON public.transcripts;
CREATE POLICY "Enable all operations for authenticated users on transcripts" ON public.transcripts
    FOR ALL USING (auth.uid() IS NOT NULL);

-- Drop and recreate policies for analysis table to be simpler
DROP POLICY IF EXISTS "Users can manage own analysis" ON public.analysis;
CREATE POLICY "Enable all operations for authenticated users on analysis" ON public.analysis
    FOR ALL USING (auth.uid() IS NOT NULL);

-- Verify the policies are working
SELECT schemaname, tablename, policyname, cmd, qual 
FROM pg_policies 
WHERE schemaname = 'public' 
ORDER BY tablename, policyname;