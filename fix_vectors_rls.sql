-- =====================================================
-- FIX VECTORS TABLE RLS POLICIES
-- =====================================================

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view own vectors" ON vectors;
DROP POLICY IF EXISTS "Users can insert own vectors" ON vectors;
DROP POLICY IF EXISTS "Users can update own vectors" ON vectors;
DROP POLICY IF EXISTS "Users can delete own vectors" ON vectors;

-- Create comprehensive RLS policies for vectors table
CREATE POLICY "Users can view own vectors" ON vectors 
  FOR SELECT TO authenticated 
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own vectors" ON vectors 
  FOR INSERT TO authenticated 
  WITH CHECK (
    user_id = auth.uid() AND 
    EXISTS (SELECT 1 FROM clips WHERE id = clip_id AND user_id = auth.uid())
  );

CREATE POLICY "Users can update own vectors" ON vectors 
  FOR UPDATE TO authenticated 
  USING (user_id = auth.uid()) 
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can delete own vectors" ON vectors 
  FOR DELETE TO authenticated 
  USING (user_id = auth.uid());

-- Verify the policies are in place
SELECT schemaname, tablename, policyname, cmd, permissive, roles, qual 
FROM pg_policies 
WHERE tablename = 'vectors' 
ORDER BY policyname;