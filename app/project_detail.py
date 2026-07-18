import os
import subprocess
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint, QRect, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QLineEdit,
    QPushButton, QFrame, QSizePolicy, QInputDialog, QStackedWidget, QLayout
)
from data.store import Project, Store, fmt_date


def _reveal_in_explorer(path: str):
    subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])


class FlowLayout(QLayout):
    """Left-to-right layout that wraps items onto new rows (Qt has no built-in)."""

    def __init__(self, parent=None, spacing=4):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self._spacing = spacing
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _do_layout(self, rect, test_only):
        x, y = rect.x(), rect.y()
        row_height = 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() and row_height > 0:
                x = rect.x()
                y += row_height + self._spacing
                row_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y()


class SectionBox(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 4, 6, 6)
        outer.setSpacing(4)
        lbl = QLabel(title)
        font = lbl.font()
        font.setBold(True)
        lbl.setFont(font)
        outer.addWidget(lbl)
        self.inner = QVBoxLayout()
        self.inner.setSpacing(3)
        outer.addLayout(self.inner)

    def add_widget(self, w: QWidget):
        self.inner.addWidget(w)

    def add_layout(self, layout):
        self.inner.addLayout(layout)


class TagChip(QPushButton):
    removed = pyqtSignal(str)

    def __init__(self, tag: str, parent=None):
        super().__init__(f"× {tag}", parent)
        self.tag = tag
        self.setFlat(True)
        self.setStyleSheet(
            "QPushButton { border: 1px solid palette(mid); padding: 1px 5px;"
            " background: palette(button); }"
            "QPushButton:hover { background: palette(midlight); }"
        )
        self.clicked.connect(lambda: self.removed.emit(self.tag))


class ProjectDetail(QWidget):
    tags_changed = pyqtSignal(str, list)
    notes_changed = pyqtSignal(str, str)
    custom_title_changed = pyqtSignal(str, str)  # (project_name, new_title)

    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self._store = store
        self._project: Project | None = None
        self._notes_timer = QTimer()
        self._notes_timer.setSingleShot(True)
        self._notes_timer.setInterval(1000)
        self._notes_timer.timeout.connect(self._save_notes)
        self._title_timer = QTimer()
        self._title_timer.setSingleShot(True)
        self._title_timer.setInterval(600)
        self._title_timer.timeout.connect(self._save_custom_title)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        # Page 0: empty state
        empty = QWidget()
        el = QVBoxLayout(empty)
        el.addStretch()
        hint = QLabel("Select a project to view details")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: palette(dark);")
        el.addWidget(hint)
        el.addStretch()
        self._stack.addWidget(empty)

        # Page 1: project detail
        detail = QWidget()
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(8, 8, 8, 8)
        dl.setSpacing(8)

        # Title row
        title_row = QHBoxLayout()
        self._title = QLabel("")
        f = self._title.font()
        f.setPointSize(f.pointSize() + 3)
        f.setBold(True)
        self._title.setFont(f)
        self._title.setWordWrap(True)
        title_row.addWidget(self._title, 1)
        self._open_bitwig_btn = QPushButton("Open in Bitwig")
        self._open_bitwig_btn.clicked.connect(self._open_in_bitwig)
        title_row.addWidget(self._open_bitwig_btn)
        open_folder_btn = QPushButton("Open folder")
        open_folder_btn.clicked.connect(self._open_folder)
        title_row.addWidget(open_folder_btn)
        dl.addLayout(title_row)

        self._path_lbl = QLabel("")
        self._path_lbl.setStyleSheet("color: palette(dark);")
        self._path_lbl.setWordWrap(True)
        dl.addWidget(self._path_lbl)

        # Song title (custom)
        song_title_row = QHBoxLayout()
        song_title_lbl = QLabel("Song title:")
        song_title_lbl.setFixedWidth(70)
        self._song_title_edit = QLineEdit()
        self._song_title_edit.setPlaceholderText("Custom title…")
        self._song_title_edit.textEdited.connect(self._on_song_title_edited)
        song_title_row.addWidget(song_title_lbl)
        song_title_row.addWidget(self._song_title_edit, 1)
        dl.addLayout(song_title_row)

        # Parsed metadata
        parsed_box = SectionBox("Project info")
        info_row = QHBoxLayout()
        self._bpm_lbl = QLabel()
        self._len_lbl = QLabel()
        for lbl in (self._bpm_lbl, self._len_lbl):
            info_row.addWidget(lbl)
        info_row.addStretch()
        parsed_box.add_layout(info_row)

        dates_row = QHBoxLayout()
        self._created_lbl = QLabel()
        self._modified_lbl = QLabel()
        dates_row.addWidget(self._created_lbl)
        dates_row.addWidget(self._modified_lbl)
        dates_row.addStretch()
        parsed_box.add_layout(dates_row)
        dl.addWidget(parsed_box)

        # Tags
        tags_box = SectionBox("Tags")
        self._tags_layout = FlowLayout(spacing=4)
        self._add_tag_btn = QPushButton("+ add")
        self._add_tag_btn.setFlat(True)
        self._add_tag_btn.setStyleSheet(
            "QPushButton { border: 1px dashed palette(mid); padding: 1px 5px;"
            " color: palette(dark); }"
        )
        self._add_tag_btn.clicked.connect(self._on_add_tag)
        self._tags_layout.addWidget(self._add_tag_btn)
        tags_box.add_layout(self._tags_layout)
        dl.addWidget(tags_box)

        # Notes
        notes_box = SectionBox("Notes")
        self._notes_edit = QPlainTextEdit()
        self._notes_edit.setPlaceholderText("Add notes here…")
        self._notes_edit.setFixedHeight(110)
        self._notes_edit.textChanged.connect(self._on_notes_changed)
        notes_box.add_widget(self._notes_edit)
        dl.addWidget(notes_box)

        # Plugins
        self._plugins_box = SectionBox("3rd Party Plugins")
        self._plugins_lbl = QLabel()
        self._plugins_lbl.setWordWrap(True)
        self._plugins_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._plugins_box.add_widget(self._plugins_lbl)
        dl.addWidget(self._plugins_box)

        # Bounces
        self._bounces_box = SectionBox("Bounces")
        self._bounces_inner = QVBoxLayout()
        self._bounces_inner.setSpacing(2)
        self._bounces_box.inner.addLayout(self._bounces_inner)
        dl.addWidget(self._bounces_box)

        dl.addStretch()
        self._stack.addWidget(detail)

    def load_project(self, project: Project | None):
        # Flush any pending saves for the previous project before switching
        if self._notes_timer.isActive():
            self._notes_timer.stop()
            self._save_notes()
        if self._title_timer.isActive():
            self._title_timer.stop()
            self._save_custom_title()

        self._project = project

        if project is None:
            self._stack.setCurrentIndex(0)
            return

        self._stack.setCurrentIndex(1)
        self._title.setText(project.title)
        path_text = project.folder_path
        if project.title != project.name:
            path_text = f"Folder: {project.name}  ·  {project.folder_path}"
        self._path_lbl.setText(path_text)
        self._song_title_edit.blockSignals(True)
        self._song_title_edit.setText(project.custom_title)
        self._song_title_edit.blockSignals(False)

        self._bpm_lbl.setText(f"BPM: {project.bpm_str}")
        self._len_lbl.setText(f"  ·  {project.length_str}" if project.length_seconds else "")
        self._created_lbl.setText(f"Created: {fmt_date(project.created)}")
        self._modified_lbl.setText(f"  ·  Modified: {fmt_date(project.modified)}")

        self._refresh_tags(project.tags)

        self._notes_edit.blockSignals(True)
        self._notes_edit.setPlainText(project.notes)
        self._notes_edit.blockSignals(False)

        self._plugins_lbl.setText(",  ".join(project.plugins))
        self._plugins_box.setVisible(bool(project.plugins))

        self._open_bitwig_btn.setVisible(
            bool(project.bwproject_path) and os.path.isfile(project.bwproject_path)
        )

        self._refresh_bounces(project.bounce_files)

    def _open_in_bitwig(self):
        if self._project and self._project.bwproject_path:
            os.startfile(self._project.bwproject_path)

    def _open_folder(self):
        if self._project:
            os.startfile(self._project.folder_path)

    def _refresh_tags(self, tags: list[str]):
        # Rebuild: chips first, then the persistent "+ add" button
        while self._tags_layout.count():
            item = self._tags_layout.takeAt(0)
            w = item.widget()
            if w is not None and w is not self._add_tag_btn:
                w.deleteLater()
        for tag in tags:
            chip = TagChip(tag)
            chip.removed.connect(self._on_remove_tag)
            self._tags_layout.addWidget(chip)
        self._tags_layout.addWidget(self._add_tag_btn)

    def _on_add_tag(self):
        if self._project is None:
            return
        tag, ok = QInputDialog.getText(self, "Add tag", "Tag:")
        tag = tag.strip().lower()
        if ok and tag and tag not in self._project.tags:
            self._project.tags.append(tag)
            self._store.set_tags(self._project.name, self._project.tags)
            self._refresh_tags(self._project.tags)
            self.tags_changed.emit(self._project.name, self._project.tags)

    def _on_remove_tag(self, tag: str):
        if self._project is None:
            return
        if tag in self._project.tags:
            self._project.tags.remove(tag)
            self._store.set_tags(self._project.name, self._project.tags)
            self._refresh_tags(self._project.tags)
            self.tags_changed.emit(self._project.name, self._project.tags)

    def _on_song_title_edited(self):
        self._title_timer.start()

    def _save_custom_title(self):
        if self._project is None:
            return
        text = self._song_title_edit.text().strip()
        self._project.custom_title = text
        self._store.set_custom_title(self._project.name, text)
        self.custom_title_changed.emit(self._project.name, text)

    def _on_notes_changed(self):
        self._notes_timer.start()

    def _save_notes(self):
        if self._project is None:
            return
        text = self._notes_edit.toPlainText()
        self._project.notes = text
        self._store.set_notes(self._project.name, text)
        self.notes_changed.emit(self._project.name, text)

    def _refresh_bounces(self, bounce_files: list[str]):
        self._clear_bounces()
        for path in bounce_files:
            row = QHBoxLayout()
            name_lbl = QLabel(os.path.basename(path))
            name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            open_btn = QPushButton("Open")
            open_btn.setFixedWidth(50)
            open_btn.clicked.connect(lambda checked, p=path: os.startfile(p))
            reveal_btn = QPushButton("Reveal")
            reveal_btn.setFixedWidth(55)
            reveal_btn.setToolTip("Show in Explorer")
            reveal_btn.clicked.connect(lambda checked, p=path: _reveal_in_explorer(p))
            row.addWidget(name_lbl)
            row.addWidget(open_btn)
            row.addWidget(reveal_btn)
            self._bounces_inner.addLayout(row)
        self._bounces_box.setVisible(bool(bounce_files))

    def _clear_bounces(self):
        while self._bounces_inner.count():
            item = self._bounces_inner.takeAt(0)
            if item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()


