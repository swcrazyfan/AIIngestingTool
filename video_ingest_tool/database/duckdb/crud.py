import duckdb
from typing import Dict, List, Optional, Any
import logging
import uuid # Add uuid import

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
            clip_dict = dict(zip(column_names, row))
            if 'id' in clip_dict and isinstance(clip_dict['id'], uuid.UUID): # Ensure uuid is imported if not already
                clip_dict['id'] = str(clip_dict['id'])
            return clip_dict
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
            clip_dict = dict(zip(column_names, row))
            if 'id' in clip_dict and isinstance(clip_dict['id'], uuid.UUID): # Ensure uuid is imported
                clip_dict['id'] = str(clip_dict['id'])
            return clip_dict
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
            results = []
            for row in rows:
                clip_dict = dict(zip(column_names, row))
                if 'id' in clip_dict and isinstance(clip_dict['id'], uuid.UUID): # Ensure uuid is imported
                    clip_dict['id'] = str(clip_dict['id'])
                # Convert other potential UUIDs if they exist in the selection
                results.append(clip_dict)
            return results
        return []
    except Exception as e:
        logger.error(f"Error fetching all clips: {e}", exc_info=True)
        return []
def list_clips_advanced_duckdb(
    conn: duckdb.DuckDBPyConnection,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Lists clips from the 'app_data.clips' table with advanced sorting and filtering.

    Args:
        conn: Active DuckDB connection.
        sort_by: Column name to sort by.
        sort_order: 'asc' or 'desc'.
        limit: Maximum number of records to return.
        offset: Number of records to skip (for pagination).
        filters: A dictionary of filters to apply. 
                 Example: {"column_name": "value", "other_column >=": 10}
                 For more complex filters like date ranges, the calling function
                 should construct the appropriate SQL filter strings.

    Returns:
        A list of dictionaries, where each dictionary represents a clip record.
    """
    logger.debug(
        f"Listing clips with sort_by={sort_by}, sort_order={sort_order}, "
        f"limit={limit}, offset={offset}, filters={filters}"
    )
    
    # Basic validation for sort_by to prevent SQL injection if it's directly used.
    # A more robust approach would be to map allowed sort_by values to actual column names.
    allowed_sort_columns = [
        "id", "local_path", "file_name", "file_checksum", "file_size_bytes",
        "duration_seconds", "created_at", "processed_at", "updated_at", "width", "height",
        "frame_rate", "codec", "container", "camera_make", "camera_model",
        "content_category", "content_summary" 
        # Add other sortable columns as needed from your schema
    ]
    if sort_by not in allowed_sort_columns:
        logger.warning(f"Invalid sort_by column: {sort_by}. Defaulting to 'created_at'.")
        sort_by = "created_at"

    sort_order_sql = "DESC" if sort_order.lower() == "desc" else "ASC"
    
    base_query = "SELECT * FROM app_data.clips"
    filter_clauses = []
    filter_params = []

    if filters:
        for key, value in filters.items():
            # This is a simple equality filter. More complex filters (>, <, LIKE, date ranges)
            # would require more sophisticated parsing of the key or specific filter structures.
            # For example, if key is "processed_at >=", then use "processed_at >= ?"
            # For now, assuming simple equality or that the key contains the operator.
            
            parts = key.strip().split(" ", 1)
            column_name = parts[0]
            operator = "=" # Default operator
            if len(parts) > 1:
                operator = parts[1]

            # Validate column_name against allowed columns to prevent injection
            if column_name not in allowed_sort_columns: # Re-using allowed_sort_columns for filterable columns
                logger.warning(f"Invalid filter column: {column_name}. Skipping this filter.")
                continue
            
            # Basic operator whitelist
            allowed_operators = ["=", "!=", ">", "<", ">=", "<=", "LIKE", "ILIKE"]
            if operator.upper() not in allowed_operators:
                logger.warning(f"Invalid filter operator: {operator} for column {column_name}. Using '='.")
                operator = "="
            
            filter_clauses.append(f'"{column_name}" {operator.upper()} ?')
            filter_params.append(value)

    if filter_clauses:
        base_query += " WHERE " + " AND ".join(filter_clauses)
    
    query_sql = f"{base_query} ORDER BY \"{sort_by}\" {sort_order_sql} LIMIT ? OFFSET ?"
    query_params = filter_params + [limit, offset]
    
    logger.debug(f"Executing SQL for list_clips_advanced: {query_sql} with params: {query_params}")

    try:
        cur = conn.cursor()
        cur.execute(query_sql, query_params)
        rows = cur.fetchall()
        if rows:
            column_names_desc = [desc[0] for desc in cur.description]
            return [dict(zip(column_names_desc, row)) for row in rows]
        return []
    except Exception as e:
        logger.error(f"Error listing clips: {e}", exc_info=True)
        return []