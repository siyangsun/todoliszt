import os
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QDialogButtonBox, QFileDialog, QComboBox
)
from data.store import Store
from app.themes import apply_theme, theme_names


class SettingsDialog(QDialog):
    applied = pyqtSignal()

    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self._store = store
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Project folders
        layout.addWidget(QLabel("Project folders:"))
        self._root_list = QListWidget()
        for f in self._store.root_folders:
            self._root_list.addItem(f)
        self._root_list.setFixedHeight(100)
        layout.addWidget(self._root_list)

        root_btn_row = QHBoxLayout()
        add_root_btn = QPushButton("Add folder…")
        add_root_btn.clicked.connect(self._add_root_folder)
        remove_root_btn = QPushButton("Remove")
        remove_root_btn.clicked.connect(self._remove_root_folder)
        root_btn_row.addWidget(add_root_btn)
        root_btn_row.addWidget(remove_root_btn)
        root_btn_row.addStretch()
        layout.addLayout(root_btn_row)

        # Bounce folders
        layout.addWidget(QLabel("Bounce folders:"))
        self._bounce_list = QListWidget()
        for f in self._store.bounce_folders:
            self._bounce_list.addItem(f)
        self._bounce_list.setFixedHeight(100)
        layout.addWidget(self._bounce_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add folder…")
        add_btn.clicked.connect(self._add_bounce_folder)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_bounce_folder)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Theme
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme:"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(theme_names())
        self._theme_combo.setCurrentText(self._store.theme)
        theme_row.addWidget(self._theme_combo)
        theme_row.addStretch()
        layout.addLayout(theme_row)

        # OK / Cancel / Apply
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._on_apply
        )
        layout.addWidget(buttons)

    def _add_root_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select project folder")
        if folder:
            self._root_list.addItem(folder)

    def _remove_root_folder(self):
        row = self._root_list.currentRow()
        if row >= 0:
            self._root_list.takeItem(row)

    def _add_bounce_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select bounce folder")
        if folder:
            self._bounce_list.addItem(folder)

    def _remove_bounce_folder(self):
        row = self._bounce_list.currentRow()
        if row >= 0:
            self._bounce_list.takeItem(row)

    def _apply(self):
        self._store.root_folders = [
            os.path.normpath(self._root_list.item(i).text())
            for i in range(self._root_list.count())
        ]
        self._store.bounce_folders = [
            os.path.normpath(self._bounce_list.item(i).text())
            for i in range(self._bounce_list.count())
        ]
        theme = self._theme_combo.currentText()
        if theme != self._store.theme:
            self._store.theme = theme
            apply_theme(QApplication.instance(), theme)
        self._store.save_settings()

    def _on_apply(self):
        self._apply()
        self.applied.emit()

    def _save(self):
        self._apply()
        self.accept()
