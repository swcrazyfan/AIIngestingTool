-- =====================================================
-- SUPABASE USER PROFILE FIX - COPY AND PASTE THIS
-- =====================================================

-- Step 1: Fix the trigger function that's causing user creation to fail
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER 
LANGUAGE plpgsql 
SECURITY DEFINER
AS $$
BEGIN
  -- Insert user profile with bulletproof error handling
  INSERT INTO public.user_profiles (id, profile_type, display_name)
  VALUES (
    NEW.id,
    'user', -- Always default to 'user' to avoid any metadata issues
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
    -- If profile creation fails, log warning but DON'T block user creation
    RAISE WARNING 'Failed to create user profile for user %: %', NEW.id, SQLERRM;
    RETURN NEW;
END;
$$;

-- Step 2: Recreate the trigger to make sure it's active
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- Step 3: Create profiles for any existing users who don't have them
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

-- Step 4: Check results
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
    RAISE NOTICE '✅ SUCCESS: All users have profiles!';
  ELSE
    RAISE NOTICE '⚠️  WARNING: % users missing profiles', (user_count - profile_count);
  END IF;
END;
$$;
