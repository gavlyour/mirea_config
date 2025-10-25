class ConfigError(Exception):
    """Базовая ошибка конфигурации с указанием поля и сообщения."""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"[{field}] {message}")
