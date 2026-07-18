import os
from PyQt6.QtCore import (
    QAbstractTableModel, QModelIndex, Qt, QSortFilterProxyModel, pyqtSignal
)
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QTableView, QHeaderView, QMenu, QApplication
)
from data.store import Project, fmt_date

COLUMNS = ["Name", "BPM", "Length", "Created", "Modified", "Bounces"]
COL_NAME, COL_BPM, COL_LEN, COL_CREATED, COL_MOD, COL_BOUNCE = range(6)


class ProjectModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._projects: list[Project] = []

    def set_projects(self, projects: list[Project]):
        self.beginResetModel()
        self._projects = projects
        self.endResetModel()

    def project_at(self, row: int) -> Project:
        return self._projects[row]

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._projects)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        p = self._projects[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_NAME:
                return p.title
            if col == COL_BPM:
                return p.bpm_str
            if col == COL_LEN:
                return p.length_str
            if col == COL_CREATED:
                return fmt_date(p.created)
            if col == COL_MOD:
                return fmt_date(p.modified)
            if col == COL_BOUNCE:
                n = len(p.bounce_files)
                return str(n) if n else ""

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (COL_BPM, COL_LEN, COL_BOUNCE):
                return Qt.AlignmentFlag.AlignCenter

        if role == Qt.ItemDataRole.ToolTipRole and col == COL_NAME:
            tip = p.folder_path
            if p.title != p.name:
                tip = f"Folder: {p.name}\n{tip}"
            return tip

        # Sort role: header clicks sort via the proxy, which would otherwise
        # compare display strings ("99" > "120"). Give it real keys instead.
        if role == Qt.ItemDataRole.UserRole:
            if col == COL_NAME:
                return p.title.lower()
            if col == COL_BPM:
                return p.bpm or 0.0
            if col == COL_LEN:
                return p.length_seconds or 0.0
            if col == COL_CREATED:
                return p.created or 0.0
            if col == COL_MOD:
                return p.modified or 0.0
            if col == COL_BOUNCE:
                return len(p.bounce_files)

        return None


class FilterProxyModel(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self._filter = ""

    def set_filter(self, text: str):
        self._filter = text.lower().strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._filter:
            return True
        model: ProjectModel = self.sourceModel()
        p = model.project_at(source_row)
        if self._filter in p.title.lower():
            return True
        if self._filter in p.name.lower():
            return True
        if any(self._filter in t.lower() for t in p.tags):
            return True
        return any(self._filter in pl.lower() for pl in p.plugins)

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        model: ProjectModel = self.sourceModel()
        lp = model.project_at(left.row())
        rp = model.project_at(right.row())
        col = left.column()
        if col == COL_NAME:    return lp.title.lower() < rp.title.lower()
        if col == COL_BPM:     return (lp.bpm or 0.0) < (rp.bpm or 0.0)
        if col == COL_LEN:     return (lp.length_seconds or 0.0) < (rp.length_seconds or 0.0)
        if col == COL_CREATED: return (lp.created or 0.0) < (rp.created or 0.0)
        if col == COL_MOD:     return (lp.modified or 0.0) < (rp.modified or 0.0)
        if col == COL_BOUNCE:  return len(lp.bounce_files) < len(rp.bounce_files)
        return False


class ProjectListView(QTableView):
    bounce_play_requested = pyqtSignal(str)  # path of bounce to play

    def __init__(self):
        super().__init__()
        self.source_model = ProjectModel()
        self.proxy = FilterProxyModel()
        self.proxy.setSourceModel(self.source_model)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.setModel(self.proxy)

        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.setSortingEnabled(True)
        self.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(24)
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for col in (COL_BPM, COL_LEN, COL_CREATED, COL_MOD, COL_BOUNCE):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        hh.setResizeContentsPrecision(0)  # only sample visible rows, not all rows
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Double-click opens the project folder
        self.doubleClicked.connect(self._on_double_click)

        # Most recently modified first by default
        self.sortByColumn(COL_MOD, Qt.SortOrder.DescendingOrder)

    def set_projects(self, projects):
        self.source_model.set_projects(projects)

    def set_filter(self, text: str):
        self.proxy.set_filter(text)

    def selected_project(self):
        indexes = self.selectedIndexes()
        if not indexes:
            return None
        source_idx = self.proxy.mapToSource(indexes[0])
        return self.source_model.project_at(source_idx.row())

    def _project_at_pos(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return None
        source_idx = self.proxy.mapToSource(index)
        return self.source_model.project_at(source_idx.row())

    def _show_context_menu(self, pos):
        project = self._project_at_pos(pos)
        if project is None:
            return

        menu = QMenu(self)

        open_action = QAction("Open folder", self)
        open_action.triggered.connect(lambda: os.startfile(project.folder_path))
        menu.addAction(open_action)

        copy_name = QAction("Copy name", self)
        copy_name.triggered.connect(lambda: QApplication.clipboard().setText(project.name))
        menu.addAction(copy_name)

        copy_path = QAction("Copy path", self)
        copy_path.triggered.connect(lambda: QApplication.clipboard().setText(project.folder_path))
        menu.addAction(copy_path)

        if project.bounce_files:
            menu.addSeparator()
            bounces_menu = menu.addMenu(f"Bounces ({len(project.bounce_files)})")
            for path in project.bounce_files:
                action = QAction(os.path.basename(path), self)
                action.triggered.connect(lambda checked, p=path: os.startfile(p))
                bounces_menu.addAction(action)

        menu.exec(self.viewport().mapToGlobal(pos))

    def _on_double_click(self, index: QModelIndex):
        source_idx = self.proxy.mapToSource(index)
        project = self.source_model.project_at(source_idx.row())
        if project and project.bounce_files:
            self.bounce_play_requested.emit(project.bounce_files[0])
        elif project:
            os.startfile(project.folder_path)
