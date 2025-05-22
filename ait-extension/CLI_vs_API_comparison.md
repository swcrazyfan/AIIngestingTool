# CLI vs API Feature Comparison

## CLI Commands Available:

### 1. Main Commands
- `ingest` - Process videos with many options
- `list_steps` - List available pipeline steps

### 2. Search Commands (`search` subcommand)
- `query` - Search with various types (semantic, fulltext, hybrid, transcripts)
- `similar` - Find similar videos to a clip
- `show` - Show detailed info about a clip
- `stats` - Show catalog statistics

### 3. Auth Commands (`auth` subcommand)
- `login` - Login to Supabase
- `signup` - Create new account
- `logout` - Logout from session
- `status` - Show auth status

## API Endpoints Available:

### 1. Health & Status
- GET `/api/health` ✅

### 2. Authentication
- GET `/api/auth/status` ✅
- POST `/api/auth/login` ✅
- POST `/api/auth/logout` ✅

### 3. Ingest
- POST `/api/ingest` ✅ (basic)
- GET `/api/ingest/progress` ✅
- GET `/api/ingest/results` ✅

### 4. Search
- POST `/api/search` ✅
- POST `/api/search/similar` ✅

### 5. Database
- GET `/api/database/status` ✅

## Missing from API:

### 1. Authentication
- ❌ Signup endpoint (`/api/auth/signup`)

### 2. Search Features
- ❌ Show clip details endpoint (`/api/clips/{id}`)
- ❌ Catalog statistics endpoint (`/api/stats`)
- ❌ Search weights configuration (summary_weight, keyword_weight, fulltext_weight)

### 3. Ingest Features
- ❌ List available pipeline steps (`/api/pipeline/steps`)
- ❌ Configuration options:
  - Custom output directory
  - Pipeline step enable/disable via config
  - Compression settings (fps, bitrate) configuration
  - Config file support

### 4. Advanced Features
- ❌ Export formats (JSON output)
- ❌ Batch operations
- ❌ Progress for individual files during ingest

## API Has But CLI Doesn't:
- ✅ Real-time progress monitoring via polling
- ✅ CORS support for browser access
- ✅ Session-based authentication persistence
