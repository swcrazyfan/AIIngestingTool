"""
This module previously handled Supabase-specific database storage logic.
Its functionalities have been migrated to:
- video_ingest_tool.database.duckdb.mappers
- video_ingest_tool.database.duckdb.crud
- Prefect tasks using the above modules (e.g., a future database_storage_step for DuckDB)

This file is largely a placeholder after the migration to DuckDB and
may be further refactored or removed if no longer needed for any
transitional or high-level orchestration logic.
"""

import structlog

logger = structlog.get_logger(__name__)

# All Supabase-specific functions (store_video_in_database, generate_searchable_content)
# have been removed as their logic is now handled by the DuckDB-specific
# modules (mappers.py, crud.py) and the data preparation/storage steps
# within the Prefect flows.

# For example, the equivalent of 'generate_searchable_content' is now
# '_generate_searchable_content' in 'video_ingest_tool/database/duckdb/mappers.py'.

# The equivalent of 'store_video_in_database' is achieved by:
# 1. Calling 'prepare_clip_data_for_db' from 'video_ingest_tool/database/duckdb/mappers.py'
#    to get the data dictionary.
# 2. Calling appropriate CRUD functions (e.g., 'upsert_clip') from
#    'video_ingest_tool/database/duckdb/crud.py' to interact with the DuckDB database.
# This sequence is typically orchestrated by a Prefect task.

logger.info("video_ingest_tool.database_storage: Supabase-specific logic has been removed. Using DuckDB implementation.")