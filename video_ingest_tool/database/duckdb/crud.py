import duckdb
from typing import Dict, List, Optional, Any
import logging

# Assuming get_db_connection will be imported from .connection
# from .connection import get_db_connection

logger = logging.getLogger(__name__)

def upsert_clip_data(
    clip_data: Dict[str, Any],
    conn: duckdb.DuckDBPyConnection
) -> Optional[str]:
    """
    Upserts (INSERTS or UPDATES) a clip record in the 'app_data.clips' table.
    Expects a dictionary where keys are column names and values are the corresponding data.

    Args:
        clip_data: A dictionary containing the pre-formatted data for the clip.
                   Must include 'file_checksum' and 'id' (can be new or existing).
        conn: Active DuckDB connection.

    Returns:
        The clip_id (UUID string) of the inserted or updated record, or None on failure.
    """
    checksum = clip_data.get("file_checksum")
    # The 'id' from clip_data is used for the INSERT part.
    # If a conflict occurs, the existing row's 'id' is preserved.
    provided_id = clip_data.get("id")

    if not checksum:
        logger.error("File checksum is missing in clip_data for upsert.")
        return None
    if not provided_id:
        logger.error("Clip ID is missing in clip_data for upsert.")
        return None
        
    logger.info(f"Attempting to upsert clip with checksum: {checksum}, provided ID for insert: {provided_id}")

    try:
        # Ensure 'updated_at' is set for every operation (insert or update)
        # 'created_at' should be in clip_data from the mapper for new inserts
        # and should NOT be updated if the record already exists.
        clip_data_final = clip_data.copy() # Avoid modifying the input dict
        
        # DuckDB's now() is suitable. Using conn.execute for consistency if transactions are used.
        current_timestamp_res = conn.execute("SELECT now()").fetchone()
        if not current_timestamp_res:
            logger.error("Failed to fetch current timestamp from DuckDB.")
            return None
        current_timestamp_for_updated_at = current_timestamp_res[0] # Use this only for updated_at
        clip_data_final['updated_at'] = current_timestamp_for_updated_at

        # If 'created_at' is not in clip_data or is None, set it using Python's UTC now.
        # The mapper should generally provide a UTC datetime for created_at.
        if 'created_at' not in clip_data_final or clip_data_final['created_at'] is None:
            # Import datetime and timezone if not already imported at the top of the file
            from datetime import datetime, timezone
            clip_data_final['created_at'] = datetime.now(timezone.utc)
            logger.info(f"Setting 'created_at' to Python's utcnow for checksum {checksum} as it was not provided or was None.")

        columns = []
        values = []
        # Ensure consistent order for columns and values
        # Sort keys to ensure consistent order for columns and values, important for prepared statements
        # However, for DuckDB's Python client, named parameters or direct dicts are often better.
        # Here, we construct based on dict keys, so order from clip_data_final.keys() is used.
        # It's generally safer if clip_data_final is an OrderedDict or keys are explicitly ordered.
        # For now, relying on Python 3.7+ dict insertion order preservation.
        
        # Explicitly define the order of columns to match the table schema for robustness
        # This list should match the one in mappers.py `clip_table_columns`
        # or be dynamically fetched, but for now, let's assume mapper provides all necessary valid keys.
        
        # Prepare columns and placeholders
        # Filter out keys that might not be columns or handle them appropriately
        # For now, assume clip_data_final contains only valid column keys
        column_names = list(clip_data_final.keys())
        columns_sql = ", ".join([f'"{k}"' for k in column_names])
        placeholders_sql = ", ".join(["?" for _ in column_names])
        
        # Prepare values in the same order as column_names
        param_values = [clip_data_final[k] for k in column_names]

        # Construct the SET clause for the UPDATE part
        # Exclude 'id', 'file_checksum', and 'created_at' from being updated
        update_set_clauses = []
        for key in column_names:
            if key not in ['id', 'file_checksum', 'created_at']:
                update_set_clauses.append(f'"{key}" = excluded."{key}"')
        update_clause_sql = ", ".join(update_set_clauses)

        if not update_clause_sql: # Should not happen if there are updatable fields
            logger.error(f"No fields available for update for checksum {checksum}. This is unexpected.")
            return None

        sql_upsert = f"""
        INSERT INTO app_data.clips ({columns_sql}) VALUES ({placeholders_sql})
        ON CONFLICT (file_checksum) DO UPDATE SET {update_clause_sql}
        RETURNING id
        """
        
        result = conn.execute(sql_upsert, param_values).fetchone()
        
        if result and result[0]:
            upserted_id = str(result[0])
            logger.info(f"Successfully upserted clip data. Resulting ID: {upserted_id} (checksum: {checksum})")
            return upserted_id
        else:
            logger.error(f"Upsert operation did not return an ID for checksum {checksum}.")
            return None
            
    except Exception as e:
        logger.error(f"Error during upsert_clip_data for checksum {checksum}, provided ID {provided_id}: {e}", exc_info=True)
        return None

def get_clip_details(clip_id: str, conn: duckdb.DuckDBPyConnection) -> Optional[Dict[str, Any]]:
    """
    Retrieves full details for a specific clip by its ID.

    Args:
        clip_id: The UUID string of the clip.
        conn: Active DuckDB connection.

    Returns:
        A dictionary representing the clip record, or None if not found.
    """
    logger.debug(f"Fetching clip details for ID: {clip_id}")
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM app_data.clips WHERE id = ?", [clip_id])
        row = cur.fetchone()
        if row:
            column_names = [desc[0] for desc in cur.description]
            return dict(zip(column_names, row))
        return None
    except Exception as e:
        logger.error(f"Error fetching clip details for ID {clip_id}: {e}", exc_info=True)
        return None

def find_clip_by_checksum(checksum: str, conn: duckdb.DuckDBPyConnection) -> Optional[Dict[str, Any]]:
    """
    Finds a clip by its file_checksum.

    Args:
        checksum: The file_checksum string.
        conn: Active DuckDB connection.

    Returns:
        A dictionary representing the clip record, or None if not found.
    """
    logger.debug(f"Finding clip by checksum: {checksum}")
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM app_data.clips WHERE file_checksum = ?", [checksum])
        row = cur.fetchone()
        if row:
            column_names = [desc[0] for desc in cur.description]
            return dict(zip(column_names, row))
        return None
    except Exception as e:
        logger.error(f"Error finding clip by checksum {checksum}: {e}", exc_info=True)
        return None

def delete_clip_by_id(clip_id: str, conn: duckdb.DuckDBPyConnection) -> bool:
    """Deletes a clip by its ID."""
    logger.info(f"Attempting to delete clip ID: {clip_id}")
    try:
        # Import uuid module if not already imported at the top
        import uuid
        try:
            uuid_obj = uuid.UUID(clip_id)
        except ValueError:
            logger.error(f"Invalid UUID string provided for deletion: {clip_id}")
            return False

        # Try passing clip_id as string, relying on DuckDB's coercion for UUID comparison.
        # Use RETURNING id to confirm if a row was actually deleted.
        result = conn.execute("DELETE FROM app_data.clips WHERE id = ? RETURNING id", [clip_id]).fetchone()
        
        if result and result[0]:
            logger.info(f"Successfully deleted clip ID: {clip_id}, returned ID: {result[0]}")
            return True # A row was deleted
        else:
            logger.warning(f"No row found to delete for clip ID: {clip_id} (or DELETE did not return ID).")
            # This will also catch cases where conn.rowcount might have been misleading.
            return False
    except Exception as e:
        logger.error(f"Error deleting clip ID {clip_id}: {e}", exc_info=True)
        return False

def get_all_clips(conn: duckdb.DuckDBPyConnection, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieves all clips with pagination."""
    logger.debug(f"Fetching all clips with limit={limit}, offset={offset}")
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM app_data.clips ORDER BY created_at DESC LIMIT ? OFFSET ?", [limit, offset])
        rows = cur.fetchall()
        if rows:
            column_names = [desc[0] for desc in cur.description]
            return [dict(zip(column_names, row)) for row in rows]
        return []
    except Exception as e:
        logger.error(f"Error fetching all clips: {e}", exc_info=True)
        return []