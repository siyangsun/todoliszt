import os
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QLineEdit, QPushButton, QStatusBar, QScrollArea, QLabel
)
from data.store import Store
from app.themes import apply_theme
from core.scanner import scan
from app.project_list import ProjectListView
from app.project_detail import ProjectDetail
from app.settings_dialog import SettingsDialog

APP_NAME = "ToDoLiszt"
_GEOMETRY_KEY = "geometry"
_SPLITTER_KEY = "splitter_v2"  # v2: default rebalanced toward the list panel


class ScanThread(QThread):
    done = pyqtSignal(list)

    def __init__(self, store: Store):
        super().__init__()
        self._store = store

    def run(self):
        projects = scan(self._store)
        self.done.emit(projects)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._store = Store()
        self._projects = []
        self._scan_thread: ScanThread | None = None
        self._qsettings = QSettings(APP_NAME, APP_NAME)

        apply_theme(QApplication.instance(), self._store.theme)
        self.setWindowTitle(APP_NAME)
        self.resize(1050, 680)
        self._build_ui()
        self._restore_geometry()
        self._setup_shortcuts()
        self._trigger_scan()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 0)
        root.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setClearButtonEnabled(True)
        self._search.setPlaceholderText("Filter by name, tag, or plugin…  (Ctrl+F)")
        self._search.textChanged.connect(self._on_filter)
        toolbar.addWidget(self._search)
        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._open_settings)
        rescan_btn = QPushButton("Rescan")
        rescan_btn.clicked.connect(self._trigger_scan)
        toolbar.addWidget(settings_btn)
        toolbar.addWidget(rescan_btn)
        root.addLayout(toolbar)

        # Splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._list_view = ProjectListView()
        self._list_view.selectionModel().selectionChanged.connect(self._on_selection)
        self._splitter.addWidget(self._list_view)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        self._detail = ProjectDetail(self._store)
        self._detail.notes_changed.connect(self._on_notes_saved)
        self._detail.tags_changed.connect(self._on_tags_changed)
        self._detail.custom_title_changed.connect(self._on_custom_title_changed)
        scroll.setWidget(self._detail)
        self._splitter.addWidget(scroll)

        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)
        self._splitter.setSizes([620, 410])
        root.addWidget(self._splitter)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._root_lbl = QLabel()
        self._root_lbl.setStyleSheet("color: palette(dark); margin-right: 4px;")
        self._status.addPermanentWidget(self._root_lbl)
        self._status.showMessage("Ready")

    def _setup_shortcuts(self):
        # Ctrl+F → focus search bar
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(
            lambda: (self._search.setFocus(), self._search.selectAll())
        )
        # Escape → clear search (when search has focus) or deselect
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_escape)
        # Ctrl+R → rescan
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._trigger_scan)

    def _on_escape(self):
        if self._search.hasFocus() and self._search.text():
            self._search.clear()
        else:
            self._list_view.clearSelection()

    def _restore_geometry(self):
        geom = self._qsettings.value(_GEOMETRY_KEY)
        if geom:
            self.restoreGeometry(geom)
        splitter_state = self._qsettings.value(_SPLITTER_KEY)
        if splitter_state:
            self._splitter.restoreState(splitter_state)

    def closeEvent(self, event):
        self._qsettings.setValue(_GEOMETRY_KEY, self.saveGeometry())
        self._qsettings.setValue(_SPLITTER_KEY, self._splitter.saveState())
        if self._scan_thread and self._scan_thread.isRunning():
            self._scan_thread.wait(2000)
        super().closeEvent(event)

    def _trigger_scan(self):
        roots = self._store.root_folders
        if len(roots) == 1:
            self._root_lbl.setText(roots[0])
        elif roots:
            self._root_lbl.setText(f"{len(roots)} project folders")
        else:
            self._root_lbl.setText("")
        if not roots:
            self._open_settings()
            return
        missing = [r for r in roots if not os.path.isdir(r)]
        if missing:
            self._status.showMessage(f"Folder not found: {missing[0]}")
            return
        if self._scan_thread and self._scan_thread.isRunning():
            return
        self._status.showMessage("Scanning…")
        self._scan_thread = ScanThread(self._store)
        self._scan_thread.done.connect(self._on_scan_done)
        self._scan_thread.start()

    def _on_scan_done(self, projects):
        self._projects = projects
        self._list_view.set_projects(projects)
        bounce_count = sum(1 for p in projects if p.bounce_files)
        msg = f"{len(projects)} projects"
        if bounce_count:
            msg += f"  ·  {bounce_count} with bounces"
        self._status.showMessage(msg)

    def _on_filter(self, text: str):
        self._list_view.set_filter(text)

    def _on_selection(self):
        project = self._list_view.selected_project()
        self._detail.load_project(project)

    def _on_notes_saved(self, name: str, notes: str):
        self._status.showMessage(f'Saved notes for "{name}"', 2000)

    def _on_tags_changed(self, name: str, tags: list):
        self._status.showMessage(f'Tags updated for "{name}"', 2000)

    def _on_custom_title_changed(self, name: str, title: str):
        model = self._list_view.source_model
        for row, p in enumerate(model._projects):
            if p.name == name:
                idx = model.index(row, 0)
                model.dataChanged.emit(idx, idx, [])
                break
        self._status.showMessage(f'Title saved for "{name}"', 2000)

    def _open_settings(self):
        dlg = SettingsDialog(self._store, self)
        dlg.applied.connect(self._trigger_scan)
        if dlg.exec():
            self._trigger_scan()
