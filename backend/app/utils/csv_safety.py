from __future__ import annotations

from typing import Any

# Leading characters that spreadsheet applications treat as a formula.
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r", "\n", "\u0000", "\ufeff")


def sanitize_csv_cell(value: Any) -> Any:
    """Neutralize spreadsheet formula injection in an exported CSV cell.

    Evidence content is attacker-controllable: a chat message, username or
    command line beginning with ``=`` would be evaluated as a formula when an
    investigator opens the export in Excel or LibreOffice. Such cells are
    prefixed with a single quote so the application treats them as text.

    Numbers, booleans and None are returned unchanged so numeric columns stay
    numeric.
    """

    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    if not text:
        return text
    if text.startswith(_FORMULA_TRIGGERS):
        return f"'{text}"
    return text


def sanitize_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: sanitize_csv_cell(value) for key, value in row.items()}
