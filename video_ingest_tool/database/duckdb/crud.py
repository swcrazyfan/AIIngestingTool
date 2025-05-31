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
    clip_id = clip_data.get("id")

    if not checksum:
        logger.error("File checksum is missing in clip_data.")
        return None
    if not clip_id: # ID must be provided, either new or existing for upsert logic
        logger.error("Clip ID is missing in clip_data.")
        return None
        
    logger.info(f"Attempting to upsert clip with checksum: {checksum}, ID: {clip_id}")

    # Filter out any keys not part of the actual table schema if necessary,
    # or assume clip_data is perfectly formed. For now, assume it's well-formed.

    existing_clip_id = None
    try:
        # Check if clip exists by checksum to decide on ID for update
        # This logic might be simplified if the caller guarantees the ID is correct for existing records.
        # For a true upsert based on checksum, we might fetch existing ID first.
        res = conn.execute("SELECT id FROM app_data.clips WHERE file_checksum = ?", [checksum]).fetchone()
        if res:
            existing_clip_id = str(res[0])
            logger.info(f"Found existing clip ID {existing_clip_id} for checksum {checksum}.")
            # If an existing clip is found by checksum, its ID should be used for the update.
            # The caller should ideally handle this by providing the correct ID in clip_data.
            # If clip_data['id'] is different, it implies an issue or a specific update strategy.
            if str(clip_id) != existing_clip_id:
                logger.warning(f"Provided clip_id {clip_id} differs from existing_clip_id {existing_clip_id} for checksum {checksum}. Using provided ID for upsert.")
                # This could be an update of a record that previously had a different ID but same checksum (data integrity issue)
                # Or it's an attempt to change the ID, which is usually not done for PKs.
                # For simplicity, we'll proceed with the ID given in clip_data for the operation.
                # A stricter approach might raise an error or force usage of existing_clip_id.
    except Exception as e:
        logger.error(f"Error checking for existing clip by checksum {checksum}: {e}", exc_info=True)
        return None


    try:
        with conn.cursor() as cur:
            # If existing_clip_id was found and matches clip_data['id'], it's an update.
            # If no existing_clip_id, or if IDs don't match but we proceed with clip_data['id'],
            # it could be an insert or an update on a specific ID.
            # A common upsert pattern is INSERT ... ON CONFLICT (column) DO UPDATE SET ...
            # DuckDB supports this: INSERT INTO tbl VALUES (1, 'foo') ON CONFLICT (col1) DO UPDATE SET col2 = excluded.col2;
            # We'll use file_checksum as the conflict target.
            
            # Ensure 'updated_at' is set
            clip_data_final = clip_data.copy() # Avoid modifying the input dict
            clip_data_final['updated_at'] = duckdb.query("SELECT now()").fetchone()[0]
            
            # Remove 'id' from update set if it's the conflict target or PK
            # For ON CONFLICT (file_checksum), 'id' can be in the insert part.
            
            columns = ", ".join([f'"{k}"' for k in clip_data_final.keys()]) # Quote column names
            placeholders = ", ".join(["?" for _ in clip_data_final])
            
            update_set_clauses = []
            for key in clip_data_final.keys():
                if key not in ['id', 'file_checksum']: # Don't update PK or conflict key itself
                    update_set_clauses.append(f'"{key}" = excluded."{key}"')
            update_clause_str = ", ".join(update_set_clauses)

            # Using file_checksum for conflict resolution
            sql_upsert = f"""
            INSERT INTO app_data.clips ({columns}) VALUES ({placeholders})
            ON CONFLICT (file_checksum) DO UPDATE SET {update_clause_str}
            """
            
            # The values must be in the same order as `columns`
            values = [clip_data_final[k] for k in clip_data_final.keys()]
            
            cur.execute(sql_upsert, values)
            
            # To get the ID of the upserted row, especially if it was an insert where ID was generated
            # or if we want to confirm the ID. If ID is always provided, this is simpler.
            # If ID is part of clip_data_final and is the PK, it's the ID.
            upserted_id = str(clip_data_final['id']) 
            
            logger.info(f"Successfully upserted clip data for ID: {upserted_id} (checksum: {checksum})")
            return upserted_id
            
    except Exception as e:
        logger.error(f"Error during upsert_clip_data for checksum {checksum}, ID {clip_id}: {e}", exc_info=True)
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
        with conn.cursor() as cur:
            cur.execute("DELETE FROM app_data.clips WHERE id = ?", [clip_id])
            return cur.rowcount > 0 # Returns True if a row was deleted
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