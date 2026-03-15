"""
Shell/bash syntax highlighter for script viewer and run log viewer.
"""
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtCore import QRegularExpression


class ShellHighlighter(QSyntaxHighlighter):
    """Read-only syntax highlighter for .sh scripts and bash-style log output."""

    def __init__(self, parent, palette: dict):
        super().__init__(parent)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        self._build_rules(palette)

    def _fmt(self, color: str, bold: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        return fmt

    def _build_rules(self, palette: dict) -> None:
        self._rules = []

        # Shebang line (#!...)
        self._rules.append((
            QRegularExpression(r"^#!.*$"),
            self._fmt(palette["sh_shebang"], bold=True),
        ))
        # Comments (# not shebang)
        self._rules.append((
            QRegularExpression(r"(?<!#!)#[^\n]*"),
            self._fmt(palette["sh_comment"]),
        ))
        # Double-quoted strings
        self._rules.append((
            QRegularExpression(r'"[^"\\]*(?:\\.[^"\\]*)*"'),
            self._fmt(palette["sh_string"]),
        ))
        # Single-quoted strings
        self._rules.append((
            QRegularExpression(r"'[^']*'"),
            self._fmt(palette["sh_string"]),
        ))
        # Variables: $VAR, ${VAR}, $1 etc.
        self._rules.append((
            QRegularExpression(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|\$[0-9@#\*\?]"),
            self._fmt(palette["sh_variable"]),
        ))
        # Keywords
        keywords = (
            r"\b(if|then|else|elif|fi|for|while|do|done|case|esac|in|"
            r"function|return|exit|export|local|declare|readonly|shift|"
            r"source|echo|printf|cd|mkdir|rm|cp|mv|chmod|chown|grep|"
            r"sed|awk|cat|ls|pwd|set|unset|true|false|test|exec)\b"
        )
        self._rules.append((
            QRegularExpression(keywords),
            self._fmt(palette["sh_keyword"], bold=True),
        ))
        # Numbers
        self._rules.append((
            QRegularExpression(r"\b[0-9]+\b"),
            self._fmt(palette["sh_number"]),
        ))

    def update_palette(self, palette: dict) -> None:
        self._build_rules(palette)
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)
