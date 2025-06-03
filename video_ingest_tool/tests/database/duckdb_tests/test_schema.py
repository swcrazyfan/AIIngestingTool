import pytest
import duckdb
from video_ingest_tool.database.duckdb.connection import get_db_connection
from video_ingest_tool.database.duckdb.schema import initialize_schema, APP_DATA_SCHEMA, PREFECT_SCHEMA

@pytest.fixture(scope="function")
def db_connection():
    """Fixture to provide an initialized in-memory DuckDB connection for schema tests."""
    con = get_db_connection(db_path=":memory:")
    # For schema tests, we want to ensure FTS index creation is also tested as part of initialize_schema's default behavior.
    initialize_schema(con, create_fts=True)
    yield con
    con.close()

def test_schemas_created(db_connection):
    """Test if the app_data and prefect_orchestration schemas are created."""
    schemas = db_connection.execute("SELECT schema_name FROM information_schema.schemata;").fetchall()
    schema_names = [s[0] for s in schemas]
    assert APP_DATA_SCHEMA in schema_names, f"Schema '{APP_DATA_SCHEMA}' should be created."
    assert PREFECT_SCHEMA in schema_names, f"Schema '{PREFECT_SCHEMA}' should be created."

def test_tables_created(db_connection):
    """Test if the 'clips' table is created in the app_data schema."""
    tables_query = f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{APP_DATA_SCHEMA}';"
    tables = db_connection.execute(tables_query).fetchall()
    table_names = [t[0] for t in tables]
    
    expected_tables = ["clips"]
    for table in expected_tables:
        assert table in table_names, f"Table '{table}' should be created in schema '{APP_DATA_SCHEMA}'."
    
    assert len(table_names) == len(expected_tables), "Only the 'clips' table should exist in the app_data schema."

def get_table_columns_info(con, table_name, schema_name=APP_DATA_SCHEMA):
    """Helper to get column names and types for a table."""
    query = f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = '{schema_name}' AND table_name = '{table_name}'
        ORDER BY ordinal_position;
    """
    return {row[0]: row[1] for row in con.execute(query).fetchall()}

def test_clips_table_columns_and_types(db_connection):
    """Test all columns and their types in the 'clips' table."""
    columns_info = get_table_columns_info(db_connection, "clips")
    
    # Based on the final schema in duckdb_schema_crud_design_plan.md
    expected_columns = {
        "id": "UUID",
        # "file_path": "VARCHAR", # Removed, replaced by local_path
        "local_path": "VARCHAR",
        "file_name": "VARCHAR",
        "file_checksum": "VARCHAR",
        "file_size_bytes": "BIGINT",
        "duration_seconds": "DOUBLE",
        "created_at": "TIMESTAMP",
        "processed_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
        "width": "INTEGER",
        "height": "INTEGER",
        "frame_rate": "DOUBLE",
        "codec": "VARCHAR",
        "container": "VARCHAR",
        "camera_make": "VARCHAR",
        "camera_model": "VARCHAR",
        "camera_details": "JSON",
        "content_category": "VARCHAR",
        "content_summary": "VARCHAR", # TEXT is an alias for VARCHAR in DuckDB
        "content_tags": "VARCHAR[]",
        "searchable_content": "VARCHAR", # TEXT is an alias for VARCHAR
        "full_transcript": "VARCHAR",    # TEXT is an alias for VARCHAR
        "transcript_preview": "VARCHAR",
        "transcript_segments_json": "JSON",
        "thumbnails": "VARCHAR[]",
        "primary_thumbnail_path": "VARCHAR",
        "ai_selected_thumbnails_json": "JSON",
        "technical_metadata": "JSON",
        "audio_tracks": "JSON",
        "subtitle_tracks": "JSON",
        "full_ai_analysis_json": "JSON",
        "summary_embedding": "FLOAT[1024]",
        "keyword_embedding": "FLOAT[1024]",
        "thumbnail_1_embedding": "FLOAT[1152]",
        "thumbnail_2_embedding": "FLOAT[1152]",
        "thumbnail_3_embedding": "FLOAT[1152]",
    }
    
    assert len(columns_info) == len(expected_columns), \
        f"Number of columns in 'clips' table mismatch. Expected {len(expected_columns)}, got {len(columns_info)}. Missing: {set(expected_columns.keys()) - set(columns_info.keys())}, Extra: {set(columns_info.keys()) - set(expected_columns.keys())}"

    for col, expected_type in expected_columns.items():
        assert col in columns_info, f"Column '{col}' should exist in 'clips' table."
        # DuckDB's information_schema.columns.data_type returns types like 'FLOAT[1024]' directly.
        # For TEXT, it returns VARCHAR.
        actual_type = columns_info[col].upper()
        assert actual_type == expected_type.upper(), \
            f"Column '{col}' in 'clips' should have type '{expected_type}', found '{actual_type}'."

def test_indexes_created_for_clips_table(db_connection):
    """Test if FTS, HNSW, and B-Tree indexes are created for the clips table."""
    indexes_result = db_connection.execute(f"SELECT index_name, table_name, sql FROM duckdb_indexes() WHERE schema_name = '{APP_DATA_SCHEMA}' AND table_name = 'clips';").fetchall()
    index_map = {(row[1], row[0]): {"sql": row[2]} for row in indexes_result}

    # HNSW Indexes
    expected_hnsw_indexes_clips = [
        "idx_clips_summary_vec", "idx_clips_keyword_vec",
        "idx_clips_thumbnail_1_vec", "idx_clips_thumbnail_2_vec", "idx_clips_thumbnail_3_vec"
    ]
    for idx_name in expected_hnsw_indexes_clips:
        assert ("clips", idx_name) in index_map, f"HNSW Index '{idx_name}' on table 'clips' should exist."
        index_sql = index_map[("clips", idx_name)]["sql"]
        assert "USING HNSW" in index_sql.upper(), f"Index '{idx_name}' on table 'clips' should be HNSW. SQL: {index_sql}"

    # B-Tree Indexes (DuckDB uses ART for these)
    expected_btree_indexes_clips = [
        "idx_clips_file_checksum", "idx_clips_created_at"
    ]
    for idx_name in expected_btree_indexes_clips:
        assert ("clips", idx_name) in index_map, f"B-Tree Index '{idx_name}' on table 'clips' should exist."
        index_sql = index_map[("clips", idx_name)]["sql"]
        assert "USING HNSW" not in index_sql.upper(), f"Index '{idx_name}' on table 'clips' should be B-Tree/ART. SQL: {index_sql}"

    # Verify FTS index creation for app_data.clips by attempting a simple FTS query.
    try:
        db_connection.execute(f"""
            SELECT id FROM {APP_DATA_SCHEMA}.clips
            WHERE fts_app_data_clips.match_bm25(id, 'test_query_value') LIMIT 1;
        """).fetchall()
    except (duckdb.BinderException, duckdb.InvalidInputException, duckdb.CatalogException) as e:
        pytest.fail(
            f"FTS index for '{APP_DATA_SCHEMA}.clips' does not seem to be working. FTS query failed: {e}"
        )
    except Exception as e:
         pytest.fail(
            f"An unexpected error occurred during FTS functionality test for '{APP_DATA_SCHEMA}.clips': {e}"
        )

# Removed test_foreign_keys_created as there is only one table now.