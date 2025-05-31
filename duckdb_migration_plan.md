# DuckDB Migration Plan for AI Ingesting Tool

> **Status Legend**:
> ⬜ = Not Started
> 🔄 = In Progress
> ✅ = Completed

## 1. Introduction ⬜

This document outlines the plan to migrate the AI Ingesting Tool from its current Supabase (PostgreSQL) backend to a local DuckDB database. The goal is to create a fully local setup, removing cloud dependencies and authentication, while retaining core functionalities like video metadata storage, full-text search, and semantic/vector search.

**Important Environment Note:** All terminal commands related to this project (e.g., running tests, installing dependencies) must be executed within the `video-ingest` Conda environment. Commands should be prefixed with `conda activate video-ingest && `.

This plan references:
-   The previously generated `supabase_schema_and_functions.md` for the existing PostgreSQL schema and SQL functions.
-   The user-provided "Complete DuckDB Setup Guide" for general DuckDB implementation ideas.
-   Analysis of `video_ingest_tool/database_storage.py` and `video_ingest_tool/api/server.py`.
-   The `duckdb_schema_crud_design_plan.md` for the final schema and detailed CRUD implementation plan.

**Key Objectives:**
-   Transition to a local DuckDB file-based database.
-   Remove all user authentication and `user_id` dependencies.
-   Implement a new, simplified database schema and adapt search functions to DuckDB.
-   Maintain full-text and semantic/vector search capabilities.
-   Organize DuckDB-specific code into a dedicated directory.
-   Prepare for Prefect by using distinct schemas for application data and orchestration.

## 2. Proposed Project Structure for Database Code ⬜

To separate database concerns and facilitate the new DuckDB implementation, a new directory structure is proposed within `video_ingest_tool/`:

```
video_ingest_tool/
├── database/
│   ├── duckdb/
│   │   ├── __init__.py
│   │   ├── connection.py       # Manages DuckDB connection, extensions
│   │   ├── schema.py           # Defines table creation, index creation
│   │   ├── crud.py             # CRUD operations (insert, update, delete, fetch by ID)
│   │   └── search_logic.py     # Implements search functions (FTS, semantic, hybrid)
│   └── base_db.py            # (Optional) Abstract base class for DB interactions
├── ... (other existing directories like api, cli_commands, tasks)
├── database_storage.py       # Current Supabase logic - will be refactored/replaced
├── auth.py                   # To be removed or heavily refactored if any local config remains
└── models.py                 # Pydantic models - may need user_id removal
```

The existing `video_ingest_tool/database_storage.py` will be refactored. Its responsibilities will be distributed among the new files in `video_ingest_tool/database/duckdb/`.

## 3. DuckDB Database Setup ⬜

### 3.1. Database File and Schemas ⬜
-   A single DuckDB database file will be used, e.g., `ai_ingest_local.duckdb`, stored at the project root or a configurable `data/` directory.
-   Two main schemas will be created within this file:
    -   `app_data`: For the application's `clips` table. *Note: The `vectors`, `segments`, `analysis`, and `transcripts` tables from the original Supabase design will not be created; their essential data is consolidated into the `clips` table.*
    -   `prefect_orchestration`: Reserved for Prefect's internal tables. Prefect will be configured to use this schema. (Actual Prefect setup is deferred).

### 3.2. Extensions ⬜
The following DuckDB extensions will be required and loaded at connection time (in `connection.py`):
-   `fts`: For Full-Text Search capabilities.
-   `vss`: For Vector Similarity Search. DuckDB documentation indicates `vss` for HNSW indexing on `FLOAT[]` types. We will use `FLOAT[N]` for embeddings.

### 3.3. Connection Management (`connection.py`) ⬜
-   This file will provide a function to get a DuckDB connection.
-   It will handle loading necessary extensions (`INSTALL ...; LOAD ...;`).
-   It will set the default search path to `app_data`.

## 4. Schema Migration (from Supabase to DuckDB) ⬜

This section details the adaptation of tables defined in `supabase_schema_and_functions.md` to DuckDB. All `user_id` columns and related foreign keys/logic will be removed.

### 4.1. Data Type Mapping
| Supabase (PostgreSQL) Type | DuckDB Type             | Notes                                                                 |
|----------------------------|-------------------------|-----------------------------------------------------------------------|
| `uuid`                     | `UUID`                  | DuckDB has a native UUID type.                                        |
| `text`                     | `VARCHAR`               | Standard string type in DuckDB.                                       |
| `jsonb`                    | `JSON`                  | DuckDB's JSON type.                                                   |
| `timestamptz`              | `TIMESTAMP`             | DuckDB's TIMESTAMP type.                                              |
| `numeric`                  | `DOUBLE` or `DECIMAL`   | `DOUBLE` is generally fine for durations, frame rates.                |
| `integer`, `bigint`        | `INTEGER`, `BIGINT`     | Direct mapping.                                                       |
| `boolean`                  | `BOOLEAN`               | Direct mapping.                                                       |
| `_text` (array of text)    | `VARCHAR[]`             | DuckDB list of VARCHAR.                                               |
| `tsvector`                 | N/A (handled by FTS)  | DuckDB FTS uses `PRAGMA create_fts_index` on `VARCHAR` columns.       |
| `vector(N)` (pgvector)     | `FLOAT[N]`              | DuckDB array of FLOAT. (e.g., `FLOAT[1024]`, `FLOAT[768]`).          |

### 4.2. Table Definitions (`schema.py`)
The final schema consists of a single `clips` table. See `duckdb_schema_crud_design_plan.md` for the detailed DDL. `schema.py` will contain functions to create this table and necessary indexes within the `app_data` schema.

**General Changes:**
-   Remove all `user_id` columns.
-   Remove foreign keys related to `user_id` or `auth.users`.
-   Change `public.` schema references to `app_data.`.
-   Adapt default value syntax if needed (e.g., `gen_random_uuid()` to `uuid()`).
-   `GENERATED ALWAYS AS` for `fts` columns in PostgreSQL will be replaced by DuckDB's FTS mechanism (indexing existing text columns).

**Specific Table Notes:**

*   **`user_profiles` Table:** This table will be **removed** entirely as authentication is being removed.

*   **`clips` Table:** (This will be the sole table in the `app_data` schema. See `duckdb_schema_crud_design_plan.md` for full details.)
    *   `user_id` column is removed.
    *   The FTS `tsvector` column is removed; FTS will be applied directly to relevant text columns.
    *   Embedding vectors and all other necessary data (including full AI analysis JSON, transcript segments JSON, and detailed thumbnail metadata) are stored directly in this table.

*   **`segments` Table:** This table will **not be created**.

*   **`analysis` Table:** This table will **not be created**. The full AI analysis JSON will be stored directly in the `clips` table.

*   **`vectors` Table:** This table will **not be created**. Embedding vectors will be stored directly in the `clips` table.

*   **`transcripts` Table:** This table will **not be created**. Transcript data (full text, preview, segments JSON) will be stored directly in the `clips` table.

### 4.3. Index Creation (`schema.py`)
-   **FTS Indexes:**
    *   `PRAGMA create_fts_index('app_data.clips', 'id', 'file_name', 'content_summary', 'transcript_preview', 'searchable_content', 'content_tags');`
-   **Vector Indexes (HNSW):**
    *   On `app_data.clips`:
        *   `CREATE INDEX idx_clips_summary_vec ON app_data.clips USING HNSW (summary_embedding);`
        *   `CREATE INDEX idx_clips_keyword_vec ON app_data.clips USING HNSW (keyword_embedding);`
        *   `CREATE INDEX idx_clips_thumb1_vec ON app_data.clips USING HNSW (thumbnail_1_embedding);` (and for thumb2, thumb3).
-   **Standard B-Tree Indexes:** Create on frequently queried/sorted columns (e.g., `clips.created_at`, `clips.file_checksum`).

## 5. Search Functionality Migration (`search_logic.py`) ⬜

The SQL functions from `supabase_schema_and_functions.md` need to be adapted to DuckDB's SQL dialect and FTS/VSS mechanisms. These will be implemented as Python functions in `search_logic.py` that construct and execute the appropriate DuckDB SQL.

*   **`fulltext_search_clips`:**
    *   Input: `query_text`, `match_count`.
    *   Logic: Use `fts_main_app_data_clips.match_bm25(id, query_text)` on the FTS index of the `clips` table.
    *   Order by rank, limit by `match_count`.

*   **`semantic_search_clips`:**
    *   Input: `query_summary_embedding (FLOAT[1024])`, `query_keyword_embedding (FLOAT[1024])`, `match_count`, weights, threshold.
    *   Logic:
        *   Calculate similarity using `1 - array_distance(summary_embedding, query_summary_embedding)` and for keywords. (Note: `array_distance` in DuckDB is L2, ensure this is the desired metric or find/implement cosine distance if needed, e.g. `1 - (col <=> query_vec)` if VSS extension provides cosine directly or use formula). For now, assume `array_distance` is acceptable or a UDF for cosine similarity will be created if necessary.
        *   Filter by `similarity_threshold`.
        *   Combine scores using weights.
        *   Order by combined similarity, limit by `match_count`.

*   **`hybrid_search_clips`:**
    *   Input: `query_text`, `query_summary_embedding`, `query_keyword_embedding`, weights, thresholds, `rrf_k`, `match_count`.
    *   Logic:
        1.  Perform FTS to get ranked results (CTE_fts).
        2.  Perform semantic search for summary embeddings (CTE_summary_semantic).
        3.  Perform semantic search for keyword embeddings (CTE_keyword_semantic).
        4.  Combine results using Reciprocal Rank Fusion (RRF): `score = (weight_fts / (rrf_k + rank_fts)) + (weight_summary / (rrf_k + rank_summary)) + ...`
        5.  Order by RRF score, limit by `match_count`.

*   **`search_transcripts`:**
    *   Input: `query_text`, `match_count`.
    *   Logic: Use `fts_app_data_clips.match_bm25(id, query_text, ...)` on the FTS index of the `clips` table (searching relevant text fields including transcript data stored in `clips`).

## 6. Application Code Refactoring ⬜

### 6.1. Database Interaction Layer (`video_ingest_tool/database/duckdb/crud.py`, `search_logic.py`) ⬜
-   Replace all Supabase client calls (e.g., `client.table(...).select(...)`, `client.rpc(...)`) with DuckDB Python API calls using the connection from `connection.py`.
-   The `generate_searchable_content` logic from `video_ingest_tool/database_storage.py` will be reused when preparing data for insertion into DuckDB `clips` table. This function is vital for populating the `searchable_content` column.
-   CRUD operations (Create, Read, Update, Delete) for the `clips` table will be implemented in `crud.py`. This includes adapting the data preparation logic seen in `store_video_in_database` from `database_storage.py`.
-   Search operations will call functions in `search_logic.py`.

### 6.2. Data Models (`video_ingest_tool/models.py`) ⬜
-   Review Pydantic models (e.g., `VideoIngestOutput` and its sub-models). Remove `user_id` fields where they appear.
-   Ensure data types in models align with DuckDB schema (e.g., `list[float]` for embeddings, standard Python types for `JSON` fields).

### 6.3. Command Classes (`video_ingest_tool/cli_commands/`) ⬜
-   `AuthCommand`: To be largely removed. Any local configuration aspects (if any) will be handled differently.
-   `SearchCommand`, `ClipsCommand`: These currently orchestrate calls to Supabase. They will be refactored to:
    *   Use the new DuckDB interaction layer (`video_ingest_tool/database/duckdb/crud.py`, `video_ingest_tool/database/duckdb/search_logic.py`).
    *   Remove any `user_id` filtering internally.
    *   Adapt parameters and expected return types if necessary.
-   `IngestCommand`: Will use the new DuckDB `crud.py` for storing data. The core logic of preparing `clip_data` and `analysis_data` from `VideoIngestOutput` (as seen in the current `store_video_in_database` function in `database_storage.py`) will be moved into a method within the new DuckDB CRUD layer or a helper function called by `IngestCommand`.

### 6.4. API Server (`video_ingest_tool/api/server.py`) ⬜
-   Remove `@require_auth` decorators and any auth-specific logic (e.g., fetching user from request context).
-   API endpoints will continue to call the command classes. Since the command classes will be updated to use DuckDB, the API layer changes should be minimal beyond auth removal.
-   The `/api/thumbnail/<clip_id>` proxy:
    *   If thumbnails are stored as local file paths (recommended for simplicity with DuckDB), this endpoint will read the file from the local path stored in the `clips` table and serve it using Flask's `send_file`.
    *   The logic for fetching `thumbnail_url` from the `clips` table will be adapted to get a local file path.

### 6.5. Storage Logic (Refactoring `video_ingest_tool/database_storage.py`) ⬜
-   The `store_video_in_database` function from `video_ingest_tool/database_storage.py` will be the primary reference for creating the new data insertion logic in `video_ingest_tool/database/duckdb/crud.py`.
    *   Remove Supabase client and `user_id` logic.
    *   Use DuckDB connection from `video_ingest_tool/database/duckdb/connection.py`.
    *   The detailed mapping of `VideoIngestOutput` fields to `clip_data` (and `analysis_data`) will be preserved and adapted for DuckDB `INSERT` or `UPDATE` statements. This includes handling of nested JSON data (e.g., `technical_metadata`, `camera_details`, `ai_analysis`).
    *   The `file_checksum` check for existing records will be implemented using a DuckDB `SELECT` then `UPDATE` or `INSERT`.

## 7. Auth Removal - Specifics ⬜
-   **Tables:**
    *   `user_profiles`: Delete.
    *   `clips`, `segments`, `analysis`, `transcripts`: Remove `user_id` column.
-   **Functions (SQL adapted to DuckDB):**
    *   All search functions (`fulltext_search_clips`, `hybrid_search_clips`, `semantic_search_clips`, `search_transcripts`): Remove `p_user_id_filter` parameter and corresponding `WHERE` clause conditions related to user filtering.
-   **Python Code:**
    *   `AuthManager` and its usage: Remove from `video_ingest_tool/database_storage.py`, `video_ingest_tool/api/server.py`, and any command classes.
    *   `video_ingest_tool/auth.py`: Remove.
    *   Remove `user_id` from data passed to database functions and from Pydantic models in `video_ingest_tool/models.py`.
    *   API endpoints in `video_ingest_tool/api/server.py`: Remove auth decorators and user context handling.

## 8. Prefect Considerations (High-Level) ⬜
-   The DuckDB database file will contain two schemas: `app_data` and `prefect_orchestration`.
-   The application code (tasks, flows) will interact with tables in the `app_data` schema.
-   Prefect server/agent, when configured, will use the `prefect_orchestration` schema for its own metadata. This keeps application data separate from Prefect's operational data within the same DuckDB file.
-   The actual configuration of `PREFECT_API_DATABASE_CONNECTION_URL="duckdb:///path/to/ai_ingest_local.duckdb?schema=prefect_orchestration"` is deferred but planned for.

## 9. Implementation Phases & Testing Strategy

This section breaks down the migration into phases with explicit testing steps.

### Phase 1: Core DuckDB Setup & Schema Definition ✅
-   ✅ **Task 1.1:** Create `video_ingest_tool/database/duckdb/` directory structure.
-   ✅ **Task 1.2:** Implement `video_ingest_tool/database/duckdb/connection.py` (connect, load extensions, set schema).
-   ✅ **Task 1.3:** Implement `video_ingest_tool/database/duckdb/schema.py` with functions to:
    -   ✅ Create `app_data` and `prefect_orchestration` schemas.
    -   ✅ Create the `clips` table in `app_data` schema with DuckDB types and no auth.
    -   ✅ Create FTS, HNSW (vector), and B-Tree indexes for the `clips` table.
-   🧪 **Testing 1.4:**
    -   ✅ Write unit tests for `connection.py` (verify connection, extension loading).
    -   ✅ Write tests for `schema.py` to ensure the `clips` table and its indexes are created correctly.
-   **Note:** The final schema design, consisting of a single `clips` table, is detailed in `duckdb_schema_crud_design_plan.md`.

#### Key Findings from FTS Implementation and Testing:

During the implementation and testing of FTS indexes in Phase 1, several important details about using DuckDB's `match_bm25` function were discovered:

1.  **Function Naming:** While initial attempts and some documentation searches might suggest `fts_match_bm25` as the function name, diagnostic queries against `duckdb_functions()` revealed the base function name registered by the FTS extension is `match_bm25`.
2.  **Qualified Invocation for Schema-Specific Tables:** The crucial insight came from DuckDB's error messages. When an FTS index is created on a schema-qualified table (e.g., `PRAGMA create_fts_index('app_data.clips', ...)`), the `match_bm25` function must be invoked by qualifying it with the FTS virtual table name.
3.  **Virtual Table Naming Convention:** DuckDB's error message (`Did you mean "fts_app_data_clips.match_bm25, ..."?`) indicated that for a table like `app_data.clips`, the corresponding FTS virtual table is named `fts_app_data_clips`.
4.  **Correct Invocation:** Therefore, the correct way to query the FTS index on `app_data.clips` is by using `fts_app_data_clips.match_bm25(id_column, query_string, ...)`.
5.  **Contrast with `fts_main_<table>`:** This naming convention (`fts_<schema>_<table>`) differs from some documentation examples that show `fts_main_<table>.match_bm25(...)`. The `fts_main_<table>` convention likely applies when the table name provided in the `PRAGMA create_fts_index` command is *not* schema-qualified (e.g., `PRAGMA create_fts_index('corpus', ...)`), defaulting to the `main` schema.

These findings were critical for getting the FTS index tests in `test_schema.py` to pass and are important for the subsequent implementation of search logic in `search_logic.py`.

### Phase 2: CRUD Operations Implementation 🔄
-   🔄 **Task 2.1:** Implement CRUD functions in `video_ingest_tool/database/duckdb/crud.py` for the `clips` table:
    -   `insert_clip`, `get_clip_by_id`, `update_clip_by_id`, `delete_clip_by_id`, `get_clip_by_checksum`.
    -   (Adapt logic from `video_ingest_tool/database_storage.py store_video_in_database` for data mapping and `generate_searchable_content`).
    -   **Note:** The detailed design for CRUD operations and necessary modifications to Prefect tasks are specified in `duckdb_schema_crud_design_plan.md`. This document should be followed for implementation.
-   🧪 **Testing 2.2:**
    -   ⬜ Write unit tests for each CRUD function in `crud.py`.

### Phase 3: Search Functionality Implementation ⬜
-   ⬜ **Task 3.1:** Implement search functions in `video_ingest_tool/database/duckdb/search_logic.py`:
    -   ⬜ `fulltext_search_clips_duckdb`
    -   ⬜ `semantic_search_clips_duckdb`
    -   ⬜ `hybrid_search_clips_duckdb`
    -   ⬜ `search_transcripts_duckdb`
    -   (Adapt SQL logic from `supabase_schema_and_functions.md` and DuckDB FTS/VSS documentation).
-   🧪 **Testing 3.2:**
    -   ⬜ Write unit tests for each search function. This will require setting up test data with embeddings and FTS content. Verify ranking, filtering, and limit clauses.

### Phase 4: Refactor Core Application Logic ⬜
-   ⬜ **Task 4.1:** Refactor `video_ingest_tool/database_storage.py`:
    -   ⬜ Remove Supabase-specific code.
    -   ⬜ Update `store_video_in_database` (or its replacement) to use the new DuckDB CRUD operations from `video_ingest_tool/database/duckdb/crud.py`.
-   ⬜ **Task 4.2:** Refactor `video_ingest_tool/cli_commands/` (`SearchCommand`, `ClipsCommand`, `IngestCommand`):
    -   ⬜ Replace Supabase client/RPC calls with calls to the new DuckDB layer (`crud.py`, `search_logic.py`).
    -   ⬜ Remove `AuthCommand` and its usage.
-   ⬜ **Task 4.3:** Update `video_ingest_tool/models.py`:
    -   ⬜ Remove `user_id` and other auth-related fields from Pydantic models.
    -   ⬜ Adjust types if necessary to align with DuckDB (e.g., `list[float]` for embeddings).
-   🧪 **Testing 4.4:**
    -   ⬜ Write integration tests for the refactored command classes to ensure they interact correctly with the DuckDB layer.
    -   ⬜ Test data ingestion and retrieval through the command classes.

### Phase 5: API Server Refactoring ⬜
-   ⬜ **Task 5.1:** Update `video_ingest_tool/api/server.py`:
    -   ⬜ Remove all authentication decorators (`@require_auth`) and logic.
    -   ⬜ Ensure API endpoints correctly call the refactored command classes.
    -   ⬜ Adapt the `/api/thumbnail/<clip_id>` endpoint for local file serving.
-   🧪 **Testing 5.2:**
    -   ⬜ Perform end-to-end testing of API endpoints (ingestion, search, clip retrieval) using tools like `curl` or Postman, or by running the frontend extension if possible.

### Phase 6: Final Integration, Documentation & Validation ⬜
-   ⬜ **Task 6.1:** Perform full system integration testing.
-   ⬜ **Task 6.2:** Update all relevant project documentation (READMEs, usage guides) to reflect the new DuckDB backend and local-only operation.
-   ⬜ **Task 6.3:** Review and validate the removal of all Supabase dependencies and auth logic.
-   ⬜ **Task 6.4:** Performance testing (optional but recommended for search functions).

This plan provides a structured approach to migrating the application to DuckDB. Each step builds upon the previous, ensuring a methodical transition.