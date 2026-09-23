from pathlib import Path

# Заготовка для валидации документов, загружаемых в приложение
class DocumentValidationError(ValueError):
    """The submitted file cannot be used in an application."""


def validate_application_document(path: Path) -> tuple[str, str]:
    """File checks are disabled; every upload is accepted for manual review."""
    return "review_required", "Файл принят. Содержательная проверка выполняется специалистом ТАТЭК."
