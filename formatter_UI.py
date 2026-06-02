"""
formatter_UI.py — display formatting classes for the console interface.

All classes implement __str__ for rendering.
Output is produced only via print() calls in menu.py.
"""

try:
    from colorama import Fore, Style, init as _colorama_init
    _colorama_init(autoreset=True)
    _COLORS_OK = True
except ImportError:
    _COLORS_OK = False


# ── Colour palette ────────────────────────────────────────────────────────────

class Colors:
    """Colorama colour codes, or empty strings when colorama is unavailable."""

    if _COLORS_OK:
        HEADER  = Fore.CYAN  + Style.BRIGHT
        SUCCESS = Fore.GREEN + Style.BRIGHT
        WARNING = Fore.YELLOW
        ERROR   = Fore.RED   + Style.BRIGHT
        DIM     = Style.DIM
        BOLD    = Style.BRIGHT
        RESET   = Style.RESET_ALL
    else:
        HEADER = SUCCESS = WARNING = ERROR = DIM = BOLD = RESET = ""


# ── Main menu ─────────────────────────────────────────────────────────────────

class MenuFormatter:
    """
    Formats the application main menu.

    Menu items are injected from outside — the class has no knowledge
    of specific actions. Adding a new item requires only one line in
    build_menu_actions(); this class is never modified (OCP).

    Args:
        menu_actions: Dict of {"key": ("Label", callable)}.
    """

    _TITLE: str = "🎬  ПОИСК ФИЛЬМОВ (Sakila)  🎬"
    _WIDTH: int = 54

    def __init__(self, menu_actions: dict) -> None:
        self._items: tuple = tuple(
            (key, label)
            for key, (label, _) in menu_actions.items()
        )

    def __str__(self) -> str:
        border = Colors.HEADER + "═" * self._WIDTH + Colors.RESET
        title  = f"{self._TITLE:^{self._WIDTH}}"
        rows   = "\n".join(
            f"  {Colors.SUCCESS}[{key}]{Colors.RESET}  {label}"
            for key, label in self._items
        )
        return f"\n{border}\n{Colors.BOLD}{title}{Colors.RESET}\n{border}\n{rows}\n{border}"


# ── Film table ────────────────────────────────────────────────────────────────

class MovieTableFormatter:
    """
    Formats a list of films as a pseudo-graphic table.

    Private attributes (accessible via properties):
        _rows  — list of film row dictionaries.
        _start — sequence number of the first film (for continuous numbering).
    """

    _COLUMNS: tuple[str, ...] = ("№", "Название", "Жанр", "Год", "Рейтинг")
    _WIDTHS:  tuple[int, ...] = (4,   32,          16,     6,     8)
    _DESC_WIDTH: int = 42

    def __init__(self, rows: list[dict], start_idx: int = 1) -> None:
        self._rows:  list[dict] = rows
        self._start: int        = start_idx

    @property
    def rows(self) -> list[dict]:
        """Film row list."""
        return self._rows

    @rows.setter
    def rows(self, value: list[dict]) -> None:
        if not isinstance(value, list):
            raise TypeError("rows must be a list of dicts")
        self._rows = value

    @property
    def start_idx(self) -> int:
        """Sequence number of the first row."""
        return self._start

    @start_idx.setter
    def start_idx(self, value: int) -> None:
        if not isinstance(value, int) or value < 1:
            raise ValueError("start_idx must be a positive integer")
        self._start = value

    @staticmethod
    def _clip(text: str, width: int) -> str:
        """Truncates text to width characters, appending '…' if clipped."""
        text = text or ""
        return text if len(text) <= width else text[: width - 1] + "…"

    def _header(self) -> str:
        cells = (c.ljust(w) for c, w in zip(self._COLUMNS, self._WIDTHS))
        desc  = "Описание".ljust(self._DESC_WIDTH)
        return Colors.HEADER + " │ ".join([*cells, desc]) + Colors.RESET

    def _separator(self) -> str:
        parts = ("─" * w for w in (*self._WIDTHS, self._DESC_WIDTH))
        return "─┼─".join(parts)

    def _format_row(self, idx: int, row: dict) -> str:
        cells = [
            str(idx).ljust(self._WIDTHS[0]),
            self._clip(row.get("title",    ""), self._WIDTHS[1]).ljust(self._WIDTHS[1]),
            self._clip(row.get("category", "N/A"), self._WIDTHS[2]).ljust(self._WIDTHS[2]),
            str(row.get("release_year", "N/A")).ljust(self._WIDTHS[3]),
            (row.get("rating") or "N/A").ljust(self._WIDTHS[4]),
            self._clip(row.get("description", ""), self._DESC_WIDTH).ljust(self._DESC_WIDTH),
        ]
        return " │ ".join(cells)

    def __str__(self) -> str:
        if not self._rows:
            return f"{Colors.WARNING}Результаты не найдены.{Colors.RESET}"
        lines = [self._header(), self._separator()]
        lines += [
            self._format_row(self._start + i, row)
            for i, row in enumerate(self._rows)
        ]
        return "\n".join(lines)


# ── Genre list ────────────────────────────────────────────────────────────────

class GenreListFormatter:
    """Formats a genre list to display before user input."""

    def __init__(self, genres: list[str]) -> None:
        self._genres: list[str] = genres

    def __str__(self) -> str:
        if not self._genres:
            return f"{Colors.WARNING}Жанры не найдены.{Colors.RESET}"
        header = f"\n{Colors.HEADER}Доступные жанры:{Colors.RESET}"
        items  = [
            f"  {Colors.SUCCESS}{g}{Colors.RESET}"
            for g in self._genres
        ]
        return header + "\n" + "  ".join(items)


# ── Search history / statistics ───────────────────────────────────────────────

class SearchHistoryFormatter:
    """
    Formats a list of search history records.

    Supports both popular queries (with 'frequency' field)
    and recent unique queries.

    Args:
        records: List of MongoDB document dictionaries.
        title:   Section heading displayed above the list.
    """

    def __init__(self, records: list[dict], title: str) -> None:
        self._records: list[dict] = records
        self._title:   str        = title

    @staticmethod
    def _fmt_params(params: dict) -> str:
        """Formats a parameter dictionary into a readable string."""
        return ", ".join(f"{k}: {v}" for k, v in params.items())

    def __str__(self) -> str:
        if not self._records:
            return f"{Colors.WARNING}История запросов пуста.{Colors.RESET}"

        border = Colors.HEADER + "─" * 60 + Colors.RESET
        lines  = [f"\n{Colors.BOLD}{self._title}{Colors.RESET}", border]

        for idx, rec in enumerate(self._records, start=1):
            ts      = rec.get("timestamp", "N/A")
            s_type  = rec.get("search_type", "N/A")
            params  = self._fmt_params(rec.get("params", {}))
            count   = rec.get("results_count", 0)
            freq    = rec.get("frequency")
            freq_str = (
                f"  {Colors.DIM}(повторов: {freq}){Colors.RESET}"
                if freq else ""
            )
            lines.append(
                f"  {idx}. {Colors.SUCCESS}[{s_type}]{Colors.RESET} "
                f"{params}{freq_str}\n"
                f"     результатов: {count}  │  {Colors.DIM}{ts}{Colors.RESET}"
            )

        lines.append(border)
        return "\n".join(lines)


# ── Info messages ─────────────────────────────────────────────────────────────

class InfoMessage:
    """
    Formats an informational, warning, or error message.

    Args:
        text:  Message text.
        level: Severity level — 'info', 'warning', or 'error'.
    """

    _LEVEL_COLOR: dict[str, str] = {
        "info":    Colors.SUCCESS,
        "warning": Colors.WARNING,
        "error":   Colors.ERROR,
    }

    def __init__(self, text: str, level: str = "info") -> None:
        self._text:  str = text
        self._color: str = self._LEVEL_COLOR.get(level, Colors.RESET)

    def __str__(self) -> str:
        return f"{self._color}{self._text}{Colors.RESET}"
