-- =====================================================
-- MANUAL USER PROFILE FIX
-- Run this after the main database_setup.sql
-- =====================================================

-- First, let's make sure the trigger function is bulletproof
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER 
LANGUAGE plpgsql 
SECURITY DEFINER
AS $$
BEGIN
  -- Insert user profile with maximum error handling
  INSERT INTO public.user_profiles (id, profile_type, display_name)
  VALUES (
    NEW.id,
    'user', -- Always default to 'user' 
    COALESCE(
      NEW.raw_user_meta_data->>'display_name',
      NEW.raw_user_meta_data->>'full_name', 
      NEW.raw_user_meta_data->>'name',
      split_part(NEW.email, '@', 1),
      'User'
    )
  );
  
  RETURN NEW;
EXCEPTION
  WHEN OTHERS THEN
    -- Log the error but don't block user creation
    RAISE WARNING 'Failed to create user profile for user %: %', NEW.id, SQLERRM;
    RETURN NEW;
END;
$$;

-- Recreate the trigger to make sure it's active
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- Create profiles for any existing users who don't have them
INSERT INTO public.user_profiles (id, profile_type, display_name, created_at)
SELECT 
  au.id,
  'user' as profile_type,
  COALESCE(
    au.raw_user_meta_data->>'display_name',
    au.raw_user_meta_data->>'full_name', 
    au.raw_user_meta_data->>'name',
    split_part(au.email, '@', 1),
    'User'
  ) as display_name,
  au.created_at
FROM auth.users au
WHERE NOT EXISTS (
  SELECT 1 FROM public.user_profiles up 
  WHERE up.id = au.id
)
ON CONFLICT (id) DO NOTHING;

-- Check how many users we have vs profiles
DO $$
DECLARE
  user_count INTEGER;
  profile_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO user_count FROM auth.users;
  SELECT COUNT(*) INTO profile_count FROM public.user_profiles;
  
  RAISE NOTICE 'Users in auth.users: %', user_count;
  RAISE NOTICE 'Profiles in user_profiles: %', profile_count;
  
  IF user_count = profile_count THEN
    RAISE NOTICE 'SUCCESS: All users have profiles!';
  ELSE
    RAISE NOTICE 'WARNING: % users missing profiles', (user_count - profile_count);
  END IF;
END;
$$;
