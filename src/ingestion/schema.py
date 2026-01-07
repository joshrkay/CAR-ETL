"""Schema registry and validation for ingestion events."""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import avro.schema
    AVRO_AVAILABLE = True
except ImportError:
    AVRO_AVAILABLE = False
    avro = None  # type: ignore

logger = logging.getLogger(__name__)

# Schema file path
SCHEMA_FILE = Path(__file__).parent.parent.parent / "schemas" / "ingestion_event.avsc"


class SchemaRegistryError(Exception):
    """Raised when schema registry operation fails."""
    pass


class IngestionEventSchema:
    """Manages Avro schema for IngestionEvent."""
    
    def __init__(self, schema_file: Optional[Path] = None):
        """Initialize schema manager.
        
        Args:
            schema_file: Path to Avro schema file. Defaults to schemas/ingestion_event.avsc.
        
        Raises:
            SchemaRegistryError: If schema file cannot be loaded.
        """
        self.schema_file = schema_file or SCHEMA_FILE
        self._schema: Optional[avro.schema.Schema] = None
        self._load_schema()
    
    def _load_schema(self) -> None:
        """Load Avro schema from file.
        
        Raises:
            SchemaRegistryError: If schema cannot be loaded or parsed.
        """
        try:
            if not self.schema_file.exists():
                raise SchemaRegistryError(f"Schema file not found: {self.schema_file}")
            
            with open(self.schema_file, "r", encoding="utf-8") as f:
                schema_json = json.load(f)
            
            if AVRO_AVAILABLE and avro is not None:
                self._schema = avro.schema.parse(json.dumps(schema_json))
                logger.info(f"Loaded Avro schema from {self.schema_file}")
            else:
                # Store as JSON dict if Avro not available
                self._schema = schema_json  # type: ignore
                logger.warning(
                    "avro-python3 not installed. Using JSON schema validation only. "
                    "Install with: pip install avro-python3"
                )
            
        except json.JSONDecodeError as e:
            raise SchemaRegistryError(f"Invalid JSON in schema file: {e}") from e
        except Exception as e:
            if AVRO_AVAILABLE and avro is not None:
                if isinstance(e, avro.schema.SchemaParseException):
                    raise SchemaRegistryError(f"Invalid Avro schema: {e}") from e
            raise SchemaRegistryError(f"Failed to load schema: {e}") from e
    
    @property
    def schema(self):
        """Get the Avro schema.
        
        Returns:
            Avro schema object (or JSON dict if Avro not available).
        
        Raises:
            SchemaRegistryError: If schema is not loaded.
        """
        if self._schema is None:
            raise SchemaRegistryError("Schema not loaded")
        return self._schema
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate data against Avro schema.
        
        Args:
            data: Dictionary to validate.
        
        Returns:
            True if valid, False otherwise.
        """
        try:
            # Use Avro's schema validation
            # Note: Full validation requires Avro's DatumReader
            # For now, we do basic type checking
            
            # Check required fields
            required_fields = [
                "tenant_id", "source_type", "file_hash", "s3_uri",
                "original_filename", "mime_type", "timestamp"
            ]
            
            for field in required_fields:
                if field not in data:
                    logger.warning(f"Missing required field: {field}")
                    return False
            
            # Validate source_type enum
            if data.get("source_type") not in ["UPLOAD", "EMAIL", "CLOUD_SYNC"]:
                logger.warning(f"Invalid source_type: {data.get('source_type')}")
                return False
            
            # Validate file_hash format (SHA-256: 64 hex chars)
            file_hash = data.get("file_hash", "")
            if len(file_hash) != 64:
                logger.warning(f"Invalid file_hash length: {len(file_hash)}, expected 64")
                return False
            
            try:
                int(file_hash, 16)  # Check if hexadecimal
            except ValueError:
                logger.warning(f"Invalid file_hash format: not hexadecimal")
                return False
            
            # Validate timestamp is numeric (milliseconds)
            timestamp = data.get("timestamp")
            if not isinstance(timestamp, (int, float)):
                logger.warning(f"Invalid timestamp type: {type(timestamp)}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Schema validation error: {e}")
            return False
    
    def get_schema_json(self) -> Dict[str, Any]:
        """Get schema as JSON dictionary.
        
        Returns:
            Schema as JSON dictionary.
        """
        with open(self.schema_file, "r", encoding="utf-8") as f:
            return json.load(f)


class SchemaRegistryClient:
    """Client for schema registry operations.
    
    This class handles registration and validation of schemas with a schema registry.
    For now, it validates locally. Full schema registry integration can be added later.
    """
    
    def __init__(self, registry_url: Optional[str] = None):
        """Initialize schema registry client.
        
        Args:
            registry_url: Schema registry URL (e.g., http://localhost:8081).
                         If not provided, uses local validation only.
        """
        self.registry_url = registry_url
        self.schema_manager = IngestionEventSchema()
    
    def register_schema(self, subject: str, schema) -> int:
        """Register schema with schema registry.
        
        Args:
            subject: Schema subject name (e.g., "ingestion-events-value").
            schema: Avro schema object.
        
        Returns:
            Schema ID from registry.
        
        Raises:
            SchemaRegistryError: If registration fails.
        """
        if not self.registry_url:
            logger.warning("Schema registry URL not configured, skipping registration")
            return -1
        
        # TODO: Implement actual schema registry API call
        # For now, return -1 to indicate local-only mode
        logger.info(f"Schema registry not configured, using local validation only")
        return -1
    
    def validate_message(self, message: Dict[str, Any]) -> bool:
        """Validate message against registered schema.
        
        Args:
            message: Message dictionary to validate.
        
        Returns:
            True if message is valid, False otherwise.
        """
        return self.schema_manager.validate(message)
    
    def reject_non_compliant(self, message: Dict[str, Any]) -> None:
        """Reject non-compliant messages by raising exception.
        
        Args:
            message: Message dictionary to validate.
        
        Raises:
            SchemaRegistryError: If message is not compliant with schema.
        """
        if not self.validate_message(message):
            raise SchemaRegistryError(
                "Message does not comply with IngestionEvent schema. "
                "All required fields must be present and valid."
            )


def get_schema_registry_client(registry_url: Optional[str] = None) -> SchemaRegistryClient:
    """Get or create schema registry client instance.
    
    Args:
        registry_url: Schema registry URL. If not provided, uses local validation.
    
    Returns:
        SchemaRegistryClient instance.
    """
    return SchemaRegistryClient(registry_url)
