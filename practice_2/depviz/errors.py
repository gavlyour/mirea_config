class ConfigError(Exception):
    """Base configuration error carrying a field name and a user-facing message."""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"[{field}] {message}")

class DataError(Exception):
    """Runtime data retrieval/parsing error (network, parsing, not found, etc.)."""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"[{field}] {message}")
