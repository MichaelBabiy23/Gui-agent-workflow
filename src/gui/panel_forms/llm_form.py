"""The LLM-call form widget used inside PropertiesPanel.

The form is split into two full-height pages behind one header:

- ``Settings``: name, model/effort, profile, session controls, prompt
  templates, prompt editor, and prompt preview (scrollable).
- ``Output``: the chat transcript of everything the workflow sent to the
  model and everything the model did and answered (``ChatView``).

The header (session crumb, node title, live pill, Settings/Output toggle)
stays visible on both pages.
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..checked_dropdown import CheckedDropdown
from ..llm_chat import VIEW_OUTPUT, VIEW_SETTINGS, ChatHeader, ChatTranscript, ChatView
from ..llm_widget import (
    ModelSelector,
    default_variant_for,
    missing_cli_message,
    populate_model_selector,
    variant_options_for,
)
from src.llm.base_provider import compose_model_variant, normalize_model_id, split_model_variant


class _LLMForm(QWidget):
    """Form widget for editing an LLMNode's properties."""

    model_selection_changed = Signal(str)
    view_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_full_model_id = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = ChatHeader()
        self.header.view_changed.connect(self._on_view_toggled)
        outer.addWidget(self.header)

        self._pages = QStackedWidget()
        outer.addWidget(self._pages, stretch=1)

        settings = QWidget()
        settings.setObjectName("llm_settings_page")
        self._build_settings(settings)
        self._settings_scroll = QScrollArea()
        self._settings_scroll.setWidgetResizable(True)
        self._settings_scroll.setWidget(settings)
        self._settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._pages.addWidget(self._settings_scroll)

        self.chat_view = ChatView()
        self.chat_view.turn_started.connect(self._on_turn_started)
        self.chat_view.busy_changed.connect(self.header.set_busy)
        self._pages.addWidget(self.chat_view)

        self.set_view(VIEW_SETTINGS)
        self.model_selector.model_changed.connect(self._on_base_model_changed)
        self.effort_combo.activated.connect(self._on_effort_activated)

    # ------------------------------------------------------------------
    # Settings page
    # ------------------------------------------------------------------

    def _build_settings(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(6)

        type_label = QLabel("LLM CALL")
        type_label.setObjectName("section_label")
        layout.addWidget(type_label)

        layout.addSpacing(4)

        layout.addWidget(QLabel("Name"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Node name...")
        layout.addWidget(self.title_edit)

        layout.addSpacing(4)

        layout.addWidget(QLabel("Model"))
        self.model_selector = ModelSelector(popup_parent=self)
        populate_model_selector(self.model_selector)
        layout.addWidget(self.model_selector)

        self._cli_status_widget = QWidget()
        cli_layout = QHBoxLayout(self._cli_status_widget)
        cli_layout.setContentsMargins(0, 0, 0, 0)
        cli_layout.setSpacing(6)
        self.cli_status_label = QLabel("")
        self.cli_status_label.setObjectName("warning_label")
        self.cli_status_label.setWordWrap(True)
        cli_layout.addWidget(self.cli_status_label, stretch=1)
        self.rescan_cli_button = QPushButton("Rescan")
        self.rescan_cli_button.setToolTip(
            "Look again for installed provider CLIs (claude, codex, grok, opencode)."
        )
        self.rescan_cli_button.clicked.connect(self.rescan_installed_clis)
        cli_layout.addWidget(self.rescan_cli_button, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._cli_status_widget)
        self._refresh_cli_status()

        self._effort_widget = QWidget()
        effort_layout = QVBoxLayout(self._effort_widget)
        effort_layout.setContentsMargins(0, 0, 0, 0)
        effort_layout.setSpacing(4)
        self.effort_label = QLabel("Effort")
        effort_layout.addWidget(self.effort_label)
        self.effort_combo = QComboBox()
        self.effort_combo.setToolTip(
            "Reasoning effort used for this call. Options depend on the selected model."
        )
        effort_layout.addWidget(self.effort_combo)
        self._effort_widget.setVisible(False)
        layout.addWidget(self._effort_widget)

        layout.addSpacing(4)

        self._profile_widget = QWidget()
        profile_layout = QVBoxLayout(self._profile_widget)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(4)
        self.profile_label = QLabel("Profile")
        profile_layout.addWidget(self.profile_label)
        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip(
            "Account profile (config directory) used for this Claude/Codex call."
        )
        profile_layout.addWidget(self.profile_combo)
        self._profile_widget.setVisible(False)
        layout.addWidget(self._profile_widget)

        layout.addSpacing(4)

        self._resume_session_widget = QWidget()
        resume_session_layout = QVBoxLayout(self._resume_session_widget)
        resume_session_layout.setContentsMargins(0, 0, 0, 0)
        resume_session_layout.setSpacing(4)

        self.resume_session_checkbox = QCheckBox("Resume previous session")
        self.resume_session_checkbox.setToolTip(
            "Resume this node's previous Claude/Codex session on the next call."
        )
        resume_session_layout.addWidget(self.resume_session_checkbox)

        self.resume_session_note = QLabel("")
        self.resume_session_note.setWordWrap(True)
        self.resume_session_note.setVisible(False)
        resume_session_layout.addWidget(self.resume_session_note)

        layout.addWidget(self._resume_session_widget)
        layout.addSpacing(4)

        self.named_session_controls = QWidget()
        named_layout = QVBoxLayout(self.named_session_controls)
        named_layout.setContentsMargins(0, 0, 0, 0)
        named_layout.setSpacing(6)

        self.save_session_checkbox = QCheckBox("Save session ID")
        self.save_session_checkbox.setToolTip(
            "Store this node's captured Claude/Codex session under a workflow-level name."
        )
        named_layout.addWidget(self.save_session_checkbox)

        self.save_session_name_edit = QLineEdit()
        self.save_session_name_edit.setPlaceholderText("Saved session name...")
        named_layout.addWidget(self.save_session_name_edit)

        self.restart_session_checkbox = QCheckBox("Restart session ID at this node")
        self.restart_session_checkbox.setToolTip(
            "Start fresh at this node, then overwrite the saved session ID with the new one."
        )
        named_layout.addWidget(self.restart_session_checkbox)

        named_layout.addWidget(QLabel("Resume session ID"))

        self.resume_named_session_combo = QComboBox()
        self.resume_named_session_combo.setPlaceholderText("")
        named_layout.addWidget(self.resume_named_session_combo)

        self.named_session_note = QLabel("")
        self.named_session_note.setWordWrap(True)
        self.named_session_note.setVisible(False)
        named_layout.addWidget(self.named_session_note)

        layout.addWidget(self.named_session_controls)

        layout.addSpacing(4)

        layout.addWidget(QLabel("Prepend"))
        self.prepend_template_dropdown = CheckedDropdown(popup_parent=self)
        self.prepend_template_dropdown.set_placeholder_text("")
        layout.addWidget(self.prepend_template_dropdown)

        layout.addWidget(QLabel("Append"))
        self.append_template_dropdown = CheckedDropdown(popup_parent=self)
        self.append_template_dropdown.set_placeholder_text("")
        layout.addWidget(self.append_template_dropdown)

        layout.addSpacing(4)

        self.prompt_warning_label = QLabel("")
        self.prompt_warning_label.setObjectName("warning_label")
        self.prompt_warning_label.setWordWrap(True)
        self.prompt_warning_label.setVisible(False)
        layout.addWidget(self.prompt_warning_label)

        layout.addSpacing(2)

        self._prompt_splitter = QSplitter(Qt.Orientation.Vertical)
        self._prompt_splitter.setChildrenCollapsible(False)

        prompt_editor_frame = QFrame()
        prompt_layout = QVBoxLayout(prompt_editor_frame)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_layout.setSpacing(4)
        prompt_layout.addWidget(QLabel("Prompt"))
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText("Enter your prompt here...")
        self.prompt_edit.setMinimumHeight(100)
        self.prompt_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        prompt_layout.addWidget(self.prompt_edit)
        self._prompt_splitter.addWidget(prompt_editor_frame)

        preview_frame = QFrame()
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(4)
        preview_layout.addWidget(QLabel("Prompt Preview"))
        self.prompt_preview_edit = QPlainTextEdit()
        self.prompt_preview_edit.setReadOnly(True)
        self.prompt_preview_edit.setPlaceholderText(
            "Composed prompt preview will appear here."
        )
        self.prompt_preview_edit.setMinimumHeight(100)
        preview_layout.addWidget(self.prompt_preview_edit)
        self._prompt_splitter.addWidget(preview_frame)
        self._prompt_splitter.setSizes([4, 1])

        layout.addWidget(self._prompt_splitter, stretch=1)

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    def view(self) -> str:
        return self.header.view()

    def set_view(self, view: str) -> None:
        self.header.set_view(view)
        self._pages.setCurrentIndex(1 if view == VIEW_OUTPUT else 0)

    def _on_view_toggled(self, view: str) -> None:
        self._pages.setCurrentIndex(1 if view == VIEW_OUTPUT else 0)
        self.view_changed.emit(view)

    def _on_turn_started(self) -> None:
        if self.view() != VIEW_OUTPUT:
            self.set_view(VIEW_OUTPUT)

    def bind_transcript(self, transcript: Optional[ChatTranscript], *, title: str, session_label: str, shared: bool) -> None:
        self.header.set_title(title)
        self.header.set_crumb(session_label)
        self.chat_view.set_transcript(transcript, show_sender=shared)

    def set_header_title(self, title: str) -> None:
        self.header.set_title(title)

    def set_text_scale(self, scale: float) -> None:
        self.header.set_text_scale(scale)
        self.chat_view.set_text_scale(scale)

    def chat_widgets(self) -> tuple[QWidget, QWidget]:
        """Widgets whose fonts the panel zoom must leave to ``set_text_scale``."""
        return self.header, self.chat_view

    # ------------------------------------------------------------------
    # Model / effort
    # ------------------------------------------------------------------

    def rescan_installed_clis(self) -> None:
        """Re-detect provider CLIs and rebuild the Model dropdown."""
        current = self._last_full_model_id
        populate_model_selector(self.model_selector, rescan=True)
        self.set_model_state(current)
        self._refresh_cli_status()

    def _refresh_cli_status(self) -> None:
        message = missing_cli_message()
        self.cli_status_label.setText(message)
        self._cli_status_widget.setVisible(bool(message))

    def set_model_state(self, full_model_id: Optional[str]) -> None:
        """Load a stored ``<model>[:<variant>]`` id into both selectors."""
        self._last_full_model_id = full_model_id or ""
        normalized = normalize_model_id(full_model_id) or ""
        base, variant = split_model_variant(normalized)
        self.model_selector.blockSignals(True)
        self.model_selector.set_model_id(base or None)
        self.model_selector.blockSignals(False)
        self._reload_effort_options(variant if base else "")

    def current_full_model_id(self) -> str:
        """Return the composed ``<model>[:<variant>]`` id currently selected."""
        base = self.model_selector.current_model_id() or ""
        if not base:
            return ""
        if not variant_options_for(base):
            return base
        data = self.effort_combo.currentData()
        variant = data if isinstance(data, str) and data else default_variant_for(base)
        return compose_model_variant(base, variant)

    def _on_base_model_changed(self, _old_id: str, _new_id: str) -> None:
        self._reload_effort_options("")
        self.model_selection_changed.emit(self.current_full_model_id())

    def _on_effort_activated(self, _index: int) -> None:
        self.model_selection_changed.emit(self.current_full_model_id())

    def _reload_effort_options(self, selected_variant: str) -> None:
        base_id = self.model_selector.current_model_id() or ""
        options = variant_options_for(base_id)
        self._effort_widget.setVisible(bool(options))
        self.effort_combo.blockSignals(True)
        self.effort_combo.clear()
        for value, label in options:
            self.effort_combo.addItem(label, userData=value)
        known = {value for value, _ in options}
        target = selected_variant if selected_variant in known else default_variant_for(base_id)
        target_index = 0
        for index in range(self.effort_combo.count()):
            if self.effort_combo.itemData(index) == target:
                target_index = index
                break
        if self.effort_combo.count():
            self.effort_combo.setCurrentIndex(target_index)
        self.effort_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Profile / sessions / templates
    # ------------------------------------------------------------------

    def set_profile_state(
        self,
        *,
        visible: bool,
        options: list[tuple[str, str]],
        selected_name: str,
    ) -> None:
        """Populate the profile dropdown.

        ``options`` are ``(profile_name, label)`` pairs; the empty-string value
        is the "Default account" entry. Hidden for providers without profiles.
        """
        self._profile_widget.setVisible(bool(visible))
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for value, label in options:
            self.profile_combo.addItem(label, userData=value)
        target_index = 0
        for index in range(self.profile_combo.count()):
            if self.profile_combo.itemData(index) == selected_name:
                target_index = index
                break
        self.profile_combo.setCurrentIndex(target_index)
        self.profile_combo.blockSignals(False)

    def current_profile_name(self) -> str:
        data = self.profile_combo.currentData()
        return data if isinstance(data, str) else ""

    def set_resume_session_state(self, checked: bool, enabled: bool, note: str = "") -> None:
        self._resume_session_widget.setVisible(bool(enabled))
        self.resume_session_checkbox.blockSignals(True)
        self.resume_session_checkbox.setChecked(bool(checked))
        self.resume_session_checkbox.blockSignals(False)
        normalized_note = note.strip()
        self.resume_session_note.setText(normalized_note)
        self.resume_session_note.setVisible(bool(normalized_note))

    def set_named_session_controls_visible(self, visible: bool) -> None:
        self.named_session_controls.setVisible(bool(visible))

    def set_named_session_state(
        self,
        *,
        save_enabled: bool,
        save_name: str,
        restart_enabled: bool,
        resume_name: str,
        options: list[tuple[str, str]],
        note: str = "",
    ) -> None:
        self.save_session_checkbox.blockSignals(True)
        self.save_session_name_edit.blockSignals(True)
        self.restart_session_checkbox.blockSignals(True)
        self.resume_named_session_combo.blockSignals(True)

        self.save_session_checkbox.setChecked(bool(save_enabled))
        self.save_session_name_edit.setText(save_name)
        self.restart_session_checkbox.setChecked(bool(restart_enabled))

        self.resume_named_session_combo.clear()
        for value, label in options:
            self.resume_named_session_combo.addItem(label, userData=value)

        target_index = -1
        for index in range(self.resume_named_session_combo.count()):
            if self.resume_named_session_combo.itemData(index) == resume_name:
                target_index = index
                break
        self.resume_named_session_combo.setCurrentIndex(target_index)

        self.save_session_checkbox.blockSignals(False)
        self.save_session_name_edit.blockSignals(False)
        self.restart_session_checkbox.blockSignals(False)
        self.resume_named_session_combo.blockSignals(False)

        save_blocked = bool(resume_name)
        self.save_session_checkbox.setEnabled(not save_blocked)
        self.save_session_name_edit.setEnabled(bool(save_enabled) and not save_blocked)
        self.restart_session_checkbox.setVisible(bool(save_enabled) and not save_blocked)
        self.restart_session_checkbox.setEnabled(bool(save_enabled) and not save_blocked)

        normalized_note = note.strip()
        self.named_session_note.setText(normalized_note)
        self.named_session_note.setVisible(bool(normalized_note))

    def set_prompt_template_options(
        self,
        options: list[tuple[str, str]],
        *,
        checked_prepend_ids: list[str],
        checked_append_ids: list[str],
    ) -> None:
        self.prepend_template_dropdown.set_items(options)
        self.append_template_dropdown.set_items(options)
        self.prepend_template_dropdown.set_checked_ids(checked_prepend_ids)
        self.append_template_dropdown.set_checked_ids(checked_append_ids)
