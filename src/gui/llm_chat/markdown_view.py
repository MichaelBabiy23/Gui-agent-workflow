"""Auto-growing markdown renderer used for chat bubbles and assistant text."""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextFrameFormat,
)
from PySide6.QtWidgets import QSizePolicy, QTextBrowser

from . import theme

_PROPORTIONAL = QTextBlockFormat.LineHeightTypes.ProportionalHeight.value


class MarkdownView(QTextBrowser):
    """Read-only, frameless markdown block that sizes itself to its text.

    Styling follows the Skylyx ``.code-markdown`` rules: 1.8 line height
    paragraphs with a 14 px bottom margin, headings at 1.5/1.25/1.1 em,
    fenced code inside a padded, bordered dark frame in the code font,
    inline code on a soft background, blockquotes in muted text, and
    accent-colored links.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._markdown = ""
        self._font_px = 14.0
        self._line_height = 180
        self._scale = 1.0
        self._last_width = -1
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)
        self.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.viewport().setAutoFillBackground(False)
        self.setStyleSheet(
            "QTextBrowser { background: transparent; border: none; padding: 0px; "
            f"color: {theme.TEXT}; selection-background-color: {theme.ACCENT}; "
            f"selection-color: {theme.SHADE}; }}"
        )
        self.document().setDocumentMargin(0)
        self.document().documentLayout().documentSizeChanged.connect(self._fit_height)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_markdown(self, text: str, font_px: float = 14.0, line_height: int = 180, scale: float = 1.0) -> None:
        self._markdown = text or ""
        self._font_px = font_px
        self._line_height = line_height
        self._scale = scale
        self._render()

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        document = self.document()
        old = document.textWidth()
        document.setTextWidth(max(1, width))
        height = int(document.size().height()) + 2
        document.setTextWidth(old)
        return height

    def sizeHint(self) -> QSize:  # noqa: N802
        width = self.viewport().width() if self.viewport().width() > 0 else 300
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(24, 0)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refit_to_viewport()

    def _refit_to_viewport(self) -> None:
        width = self.viewport().width()
        if width > 0 and width != self._last_width:
            self._last_width = width
            self.document().setTextWidth(max(1, width))
        self._fit_height()

    def _fit_height(self, *_args) -> None:
        height = int(self.document().size().height()) + 2
        if height != self.height():
            self.setFixedHeight(max(0, height))
            self.updateGeometry()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        document = self.document()
        document.setDefaultFont(theme.ui_font(self._font_px, scale=self._scale))
        document.setMarkdown(self._markdown, QTextDocument.MarkdownFeature.MarkdownDialectGitHub)
        self._wrap_code_blocks(document)
        self._style_document(document)
        self._last_width = -1
        self._refit_to_viewport()
        QTimer.singleShot(0, self._refit_to_viewport)

    def _code_ranges(self, document: QTextDocument) -> List[Tuple[int, int]]:
        """Return ``(start, end)`` character ranges of consecutive fenced-code blocks."""
        ranges: List[Tuple[int, int]] = []
        current: List[int] = []
        block = document.begin()
        while block.isValid():
            if block.blockFormat().nonBreakableLines():
                end = block.position() + block.length() - 1
                if current:
                    current[1] = end
                else:
                    current = [block.position(), end]
            elif current:
                ranges.append((current[0], current[1]))
                current = []
            block = block.next()
        if current:
            ranges.append((current[0], current[1]))
        return ranges

    def _wrap_code_blocks(self, document: QTextDocument) -> None:
        """Move each fenced code block into a padded, bordered ``QTextFrame``."""
        code_px = max(8, round(self._font_px * 0.85 * self._scale))
        char_format = QTextCharFormat()
        char_format.setFont(theme.code_font(code_px))
        char_format.setForeground(QColor(theme.TEXT))
        block_format = QTextBlockFormat()
        block_format.setLineHeight(160, _PROPORTIONAL)
        frame_format = QTextFrameFormat()
        frame_format.setPadding(12)
        frame_format.setBorder(1)
        frame_format.setBorderBrush(QColor(theme.LINE))
        frame_format.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
        frame_format.setBackground(QColor(theme.DARK))
        frame_format.setTopMargin(8)
        frame_format.setBottomMargin(8)

        for start, end in reversed(self._code_ranges(document)):
            cursor = QTextCursor(document)
            selection_start = start - 1 if start > 0 else 0
            cursor.setPosition(selection_start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            text = cursor.selectedText().replace(" ", "\n")
            if start > 0:
                text = text[1:]
            cursor.removeSelectedText()
            cursor.insertFrame(frame_format)
            cursor.setBlockFormat(block_format)
            cursor.insertText(text, char_format)

    @staticmethod
    def _collapse_empty_block(block) -> None:
        """Hide an empty separator block left next to a frame."""
        cursor = QTextCursor(block)
        block_format = QTextBlockFormat()
        block_format.setLineHeight(1, _PROPORTIONAL)
        block_format.setTopMargin(0)
        block_format.setBottomMargin(0)
        cursor.setBlockFormat(block_format)
        char_format = QTextCharFormat()
        char_format.setFontPointSize(1)
        cursor.setBlockCharFormat(char_format)

    def _style_document(self, document: QTextDocument) -> None:
        base_px = max(8, round(self._font_px * self._scale))
        code_px = max(8, round(self._font_px * 0.85 * self._scale))
        root = document.rootFrame()
        block = document.begin()
        last_block_number = document.lastBlock().blockNumber()
        while block.isValid():
            if document.frameAt(block.position()) is not root or block.blockFormat().nonBreakableLines():
                block = block.next()
                continue
            is_last = block.blockNumber() == last_block_number
            if not block.text() and (block.blockNumber() == 0 or is_last) and document.blockCount() > 1:
                self._collapse_empty_block(block)
                block = block.next()
                continue
            cursor = QTextCursor(block)
            block_format = QTextBlockFormat(block.blockFormat())
            heading = block_format.headingLevel()
            quote_level = block_format.intProperty(QTextFormat.Property.BlockQuoteLevel)
            if heading:
                size_factor = {1: 1.5, 2: 1.25, 3: 1.1}.get(heading, 1.0)
                block_format.setTopMargin(24)
                block_format.setBottomMargin(10)
                block_format.setLineHeight(140, _PROPORTIONAL)
                char_format = QTextCharFormat()
                char_format.setFont(theme.ui_font(base_px * size_factor, QFont.Weight.DemiBold))
                char_format.setForeground(QColor(theme.HEADING_TEXT))
                self._merge_block_chars(document, block, char_format)
            else:
                block_format.setLineHeight(self._line_height, _PROPORTIONAL)
                block_format.setBottomMargin(0 if is_last else 14)
                if quote_level:
                    block_format.setLeftMargin(18 * quote_level)
                    block_format.setBackground(QColor(theme.SOFT))
                    char_format = QTextCharFormat()
                    char_format.setForeground(QColor(theme.MUTED))
                    self._merge_block_chars(document, block, char_format)
            cursor.setBlockFormat(block_format)
            self._style_fragments(document, block, code_px)
            block = block.next()

    @staticmethod
    def _merge_block_chars(document: QTextDocument, block, char_format: QTextCharFormat) -> None:
        cursor = QTextCursor(document)
        cursor.setPosition(block.position())
        cursor.setPosition(block.position() + max(0, block.length() - 1), QTextCursor.MoveMode.KeepAnchor)
        cursor.mergeCharFormat(char_format)

    def _style_fragments(self, document: QTextDocument, block, code_px: int) -> None:
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            iterator += 1
            if not fragment.isValid():
                continue
            fmt = fragment.charFormat()
            cursor = QTextCursor(document)
            cursor.setPosition(fragment.position())
            cursor.setPosition(fragment.position() + fragment.length(), QTextCursor.MoveMode.KeepAnchor)
            if fmt.fontFixedPitch():
                code_format = QTextCharFormat()
                code_format.setFont(theme.code_font(code_px))
                code_format.setBackground(QColor(theme.SOFT))
                code_format.setForeground(QColor(theme.TEXT))
                cursor.mergeCharFormat(code_format)
            if fmt.isAnchor():
                link_format = QTextCharFormat()
                link_format.setForeground(QColor(theme.LINK))
                link_format.setFontUnderline(True)
                cursor.mergeCharFormat(link_format)
