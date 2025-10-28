#!/usr/bin/env python3
"""
Senzing Entity Resolution Client

Wrapper for Senzing G2 SDK to perform entity resolution on Neo4j graph entities.
This client handles the initialization, record management, and entity resolution
operations using the Senzing engine.

Note: This implementation requires Senzing to be installed and licensed.
If Senzing is not available, the system will fall back to text-based entity matching.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import Senzing modules - will fail if not installed
SENZING_AVAILABLE = False
try:
    from senzing import G2Engine, G2Config, G2ConfigMgr, G2Diagnostic, G2Exception
    SENZING_AVAILABLE = True
    logger.info("Senzing SDK modules imported successfully")
except ImportError:
    logger.warning("Senzing SDK not available - will use text-based entity matching")
    # Define mock classes for type hints
    class G2Engine:
        pass
    class G2Config:
        pass
    class G2ConfigMgr:
        pass
    class G2Diagnostic:
        pass
    class G2Exception(Exception):
        pass


class SenzingClient:
    """
    Client wrapper for Senzing G2 entity resolution engine.

    This client provides methods to:
    - Initialize the Senzing engine
    - Add records for entity resolution
    - Retrieve resolved entities
    - Search for similar entities
    - Clean up resources

    Example:
        ```python
        client = SenzingClient()
        if client.is_available():
            client.initialize()
            client.add_record("NIEM_GRAPH", "entity_123", json_data)
            result = client.get_entity_by_record_id("NIEM_GRAPH", "entity_123")
            client.close()
        ```
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Senzing client.

        Args:
            config_path: Path to g2.ini configuration file.
                        If None, uses environment variable or default.
        """
        self.config_path = config_path or os.getenv(
            "SENZING_CONFIG_PATH",
            "/app/config/g2.ini"
        )
        self.engine: Optional[G2Engine] = None
        self.config: Optional[G2Config] = None
        self.config_mgr: Optional[G2ConfigMgr] = None
        self.diagnostic: Optional[G2Diagnostic] = None
        self.initialized = False

        # Module name for Senzing initialization
        self.module_name = "NIEM_ENTITY_RESOLUTION"

    def is_available(self) -> bool:
        """
        Check if Senzing SDK is available and licensed.

        Returns:
            True if Senzing can be used, False otherwise
        """
        if not SENZING_AVAILABLE:
            return False

        # Check for license file
        from ..core.config import senzing_config
        return senzing_config.is_available()

    def initialize(self, verbose_logging: bool = False) -> bool:
        """
        Initialize the Senzing engine with configuration.

        Args:
            verbose_logging: Enable verbose Senzing logging

        Returns:
            True if initialization successful, False otherwise
        """
        if not self.is_available():
            logger.error("Cannot initialize Senzing - SDK not available or not licensed")
            return False

        try:
            # Load INI parameters
            ini_params = self._load_ini_params()

            # Initialize G2Engine
            self.engine = G2Engine()
            self.engine.init(self.module_name, ini_params, verbose_logging)

            # Initialize G2Config for configuration management
            self.config = G2Config()
            self.config.init(self.module_name, ini_params, verbose_logging)

            # Initialize G2ConfigMgr for configuration updates
            self.config_mgr = G2ConfigMgr()
            self.config_mgr.init(self.module_name, ini_params, verbose_logging)

            # Initialize G2Diagnostic for monitoring
            self.diagnostic = G2Diagnostic()
            self.diagnostic.init(self.module_name, ini_params, verbose_logging)

            self.initialized = True
            logger.info("Senzing engine initialized successfully")
            return True

        except G2Exception as e:
            logger.error(f"Failed to initialize Senzing engine: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error initializing Senzing: {e}")
            return False

    def _load_ini_params(self) -> str:
        """
        Load and format INI parameters for Senzing initialization.

        Returns:
            JSON string of initialization parameters
        """
        try:
            # Use simplified configuration
            import sys
            from pathlib import Path

            # Add config directory to path
            config_dir = Path(__file__).parent.parent.parent / "config"
            if str(config_dir) not in sys.path:
                sys.path.insert(0, str(config_dir))

            from senzing_simple_config import get_ini_json_params
            ini_params = get_ini_json_params()

            logger.info(f"Loaded Senzing configuration with SQLite at {ini_params['SQL']['CONNECTION']}")
            return json.dumps(ini_params)

        except ImportError as e:
            logger.warning(f"Could not import simple config: {e}")

            # Fallback to minimal in-memory configuration
            logger.info("Using fallback minimal configuration")
            return json.dumps({
                "PIPELINE": {
                    "CONFIGPATH": "/tmp/senzing/config/",  # nosec B108 - Senzing SDK standard config path
                    "RESOURCEPATH": "/opt/senzing/g2/resources/",
                    "SUPPORTPATH": "/tmp/senzing/"  # nosec B108 - Senzing SDK standard support path
                },
                "SQL": {
                    "CONNECTION": "sqlite3://na:na@/tmp/senzing/g2.db"  # nosec B108 - Senzing SDK standard DB path
                }
            })

    def add_record(self, data_source: str, record_id: str, record_json: str,
                   load_id: Optional[str] = None) -> bool:
        """
        Add a record to Senzing for entity resolution.

        Args:
            data_source: Data source code (e.g., "NIEM_GRAPH")
            record_id: Unique record identifier
            record_json: JSON string of record data
            load_id: Optional load batch identifier

        Returns:
            True if record added successfully, False otherwise
        """
        if not self.initialized:
            logger.error("Senzing engine not initialized")
            return False

        try:
            if load_id:
                self.engine.addRecordWithInfo(data_source, record_id, record_json, load_id)
            else:
                self.engine.addRecord(data_source, record_id, record_json)
            logger.debug(f"Added record {record_id} from {data_source}")
            return True

        except G2Exception as e:
            logger.error(f"Failed to add record {record_id}: {e}")
            return False

    def get_entity_by_record_id(self, data_source: str, record_id: str,
                                flags: Optional[int] = None) -> Optional[Dict]:
        """
        Get resolved entity information for a specific record.

        Args:
            data_source: Data source code
            record_id: Record identifier
            flags: Optional flags for response detail level

        Returns:
            Dictionary with resolved entity information, or None if error
        """
        if not self.initialized:
            logger.error("Senzing engine not initialized")
            return None

        try:
            response = bytearray()
            if flags is not None:
                self.engine.getEntityByRecordID(data_source, record_id, response, flags)
            else:
                self.engine.getEntityByRecordID(data_source, record_id, response)

            return json.loads(response.decode())

        except G2Exception as e:
            logger.error(f"Failed to get entity for record {record_id}: {e}")
            return None

    def search_by_attributes(self, attributes_json: str, flags: Optional[int] = None) -> Optional[Dict]:
        """
        Search for entities matching specified attributes.

        Args:
            attributes_json: JSON string of search attributes
            flags: Optional flags for response detail level

        Returns:
            Dictionary with search results, or None if error
        """
        if not self.initialized:
            logger.error("Senzing engine not initialized")
            return None

        try:
            response = bytearray()
            if flags is not None:
                self.engine.searchByAttributes(attributes_json, response, flags)
            else:
                self.engine.searchByAttributes(attributes_json, response)

            return json.loads(response.decode())

        except G2Exception as e:
            logger.error(f"Failed to search by attributes: {e}")
            return None

    def get_entity_by_entity_id(self, entity_id: int, flags: Optional[int] = None) -> Optional[Dict]:
        """
        Get entity information by Senzing entity ID.

        Args:
            entity_id: Senzing internal entity ID
            flags: Optional flags for response detail level

        Returns:
            Dictionary with entity information, or None if error
        """
        if not self.initialized:
            logger.error("Senzing engine not initialized")
            return None

        try:
            response = bytearray()
            if flags is not None:
                self.engine.getEntityByEntityID(entity_id, response, flags)
            else:
                self.engine.getEntityByEntityID(entity_id, response)

            return json.loads(response.decode())

        except G2Exception as e:
            logger.error(f"Failed to get entity {entity_id}: {e}")
            return None

    def find_path_by_entity_id(self, start_entity_id: int, end_entity_id: int,
                               max_degrees: int = 3) -> Optional[Dict]:
        """
        Find relationship path between two entities.

        Args:
            start_entity_id: Starting entity ID
            end_entity_id: Ending entity ID
            max_degrees: Maximum degrees of separation

        Returns:
            Dictionary with path information, or None if error
        """
        if not self.initialized:
            logger.error("Senzing engine not initialized")
            return None

        try:
            response = bytearray()
            self.engine.findPathByEntityID(
                start_entity_id, end_entity_id, max_degrees, response
            )
            return json.loads(response.decode())

        except G2Exception as e:
            logger.error(f"Failed to find path between {start_entity_id} and {end_entity_id}: {e}")
            return None

    def process_batch(self, records: List[Tuple[str, str, str]]) -> Dict[str, Any]:
        """
        Process a batch of records for entity resolution.

        Args:
            records: List of tuples (data_source, record_id, record_json)

        Returns:
            Dictionary with batch processing results
        """
        results = {
            "processed": 0,
            "failed": 0,
            "errors": []
        }

        for data_source, record_id, record_json in records:
            if self.add_record(data_source, record_id, record_json):
                results["processed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"Failed to add record {record_id}")

        return results

    def delete_record(self, data_source: str, record_id: str, load_id: Optional[str] = None) -> bool:
        """
        Delete a record from Senzing.

        Args:
            data_source: Data source code (e.g., "NIEM_GRAPH")
            record_id: Unique record identifier
            load_id: Optional load batch identifier

        Returns:
            True if record deleted successfully, False otherwise
        """
        if not self.initialized:
            logger.error("Senzing engine not initialized")
            return False

        try:
            if load_id:
                self.engine.deleteRecordWithInfo(data_source, record_id, load_id)
            else:
                self.engine.deleteRecord(data_source, record_id)
            logger.debug(f"Deleted record {record_id} from {data_source}")
            return True

        except G2Exception as e:
            logger.error(f"Failed to delete record {record_id}: {e}")
            return False

    def purge_repository(self) -> bool:
        """
        Purge all data from the Senzing repository.
        WARNING: This deletes ALL data from the Senzing database.

        Returns:
            True if purge successful, False otherwise
        """
        if not self.initialized:
            logger.error("Senzing engine not initialized")
            return False

        try:
            self.engine.purgeRepository()
            logger.info("Purged all data from Senzing repository")
            return True

        except G2Exception as e:
            logger.error(f"Failed to purge repository: {e}")
            return False

    def get_stats(self) -> Optional[Dict]:
        """
        Get Senzing engine statistics.

        Returns:
            Dictionary with engine statistics, or None if error
        """
        if not self.initialized or not self.diagnostic:
            logger.error("Senzing diagnostic not initialized")
            return None

        try:
            response = bytearray()
            self.diagnostic.getDBInfo(response)
            return json.loads(response.decode())

        except G2Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return None

    def close(self):
        """
        Clean up and destroy Senzing engine resources.
        """
        if self.engine:
            try:
                self.engine.destroy()
                logger.info("Senzing engine destroyed")
            except Exception as e:
                logger.error(f"Error destroying engine: {e}")

        if self.config:
            try:
                self.config.destroy()
            except Exception as e:
                logger.error(f"Error destroying config: {e}")

        if self.config_mgr:
            try:
                self.config_mgr.destroy()
            except Exception as e:
                logger.error(f"Error destroying config manager: {e}")

        if self.diagnostic:
            try:
                self.diagnostic.destroy()
            except Exception as e:
                logger.error(f"Error destroying diagnostic: {e}")

        self.initialized = False


# Singleton instance for application-wide use
_senzing_client: Optional[SenzingClient] = None


def get_senzing_client() -> SenzingClient:
    """
    Get or create the singleton Senzing client instance.

    Returns:
        SenzingClient instance
    """
    global _senzing_client
    if _senzing_client is None:
        _senzing_client = SenzingClient()
        if _senzing_client.is_available():
            _senzing_client.initialize()
    return _senzing_client