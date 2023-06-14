import sys
import json
import os
import random
import numpy as np
import re

from qbittorrentapi import TorrentFilesList, SyncMainDataDictionary
from qbittorrentapi.exceptions import NotFound404Error

import qtpy

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from ..core import CoreController as Controller
from ..core import CoreCaches as Cache
from ..core import CoreGlobals as CG
from ..core import CoreData as CD
from ..core import CoreConstants as CC
from ..core import CoreLogging as logging

from . import GUICommon
from . import dialogs


class ClientWidnow(QW.QMainWindow):
    def __init__(self, controller: Controller.ClientController):
        super().__init__()

        self.contrller = controller

        self.selected_torrent_hash: str = None

        self.metadata_sync_timer = QC.QTimer(self)
        self.metadata_sync_timer.timeout.connect(self._update_metadata)
        self.metadata_sync_timer.start(CC.TORRENT_METADATA_SYNC_RATE_MS)

        self.setWindowTitle("qBittorrent Remote")

        self.panel = QW.QWidget()

        self.split_panel = QW.QSplitter(self.panel)
        self.split_panel.setOrientation(QC.Qt.Orientation.Vertical)

        self.input_box = QW.QLineEdit()
        self.input_box.setPlaceholderText("Regex for torrent name")
        self.input_box.returnPressed.connect(self._search_pressed)

        self.search_button = QW.QPushButton("Search")
        self.search_button.clicked.connect(self._search_pressed)

        def debug():
            # controller.sync_metadata()
            pass

        self.debug_button = QW.QPushButton("Debug")
        self.debug_button.clicked.connect(debug)

        self.status_text_template = "Free Space: {}   DHT: {}   Download: {}   Upload: {}"
        self.status_label = QW.QLabel(self.status_text_template)
        self.status_label.setAlignment(QC.Qt.AlignRight)

        self.status_bar = QW.QStatusBar(self)
        self.status_bar.addWidget(self.status_label)

        self.update_torrent_list_button = QW.QPushButton("Update Torrents")
        self.update_torrent_list_button.clicked.connect(self.update_torrent_list)

        self._torrent_list_new = QW.QTreeWidget()
        self._torrent_list_new.setColumnCount(6)
        self._torrent_list_new.setSortingEnabled(True)
        self._torrent_list_new.header().setSectionResizeMode(QW.QHeaderView.ResizeToContents)
        self._torrent_list_new.header().setStretchLastSection(False)
        self._torrent_list_new.setHeaderLabels(
            ["Name", "Size", "Progress", "Status", "Ratio", "Availability", "Download", "Upload"]
        )
        self._torrent_list_new.itemClicked.connect(self._list_item_click)

        self.file_tree = QW.QTreeWidget()
        self.file_tree.setContextMenuPolicy(QC.Qt.CustomContextMenu)
        self.file_tree.setSortingEnabled(True)
        self.file_tree.header().setSectionResizeMode(QW.QHeaderView.ResizeToContents)
        self.file_tree.header().setStretchLastSection(False)
        self.file_tree.setSelectionMode(QW.QAbstractItemView.ExtendedSelection)
        self.file_tree.setColumnCount(6)
        self.file_tree.setHeaderLabels(
            ["Name", "Total Size", "Progress", "Download Priority", "Ramaining", "Availability"]
        )
        self.file_tree.customContextMenuRequested.connect(self._right_click_menu)
        self.file_tree.itemChanged.connect(self._item_checkbox_changed)

        self.file_menu = self.menuBar().addMenu("File")
        self.add_torrent_file_action = self.file_menu.addAction("Add Torrent(s)")
        self.add_torrent_file_action.triggered.connect(self._handle_magnet_dialog)

        self.logout_menu = self.file_menu.addMenu("Logout")

        # self.split_panel.addWidget(self.torrent_list)
        self.split_panel.addWidget(self._torrent_list_new)
        self.split_panel.addWidget(self.file_tree)

        layout = QW.QVBoxLayout()
        layout_2 = QW.QHBoxLayout()
        layout_2.addWidget(self.input_box)
        layout_2.addWidget(self.search_button)
        layout_2.addWidget(self.update_torrent_list_button)
        layout_2.addWidget(self.debug_button)
        layout.addLayout(layout_2)
        layout.addWidget(self.split_panel)
        self.panel.setLayout(layout)

        self.setStatusBar(self.status_bar)
        self.setCentralWidget(self.panel)

        self.torrent_tree_list_cache = Cache.Expiring_Data_Cache(
            "tree list data cache", CC.TORRENT_CACHE_TIME_SECONDS
        )

        self.global_state_cache = Cache.Data_Cache("globalstate")
        self.global_state_cache.add_data("server_state", {})

        self._update_metadata()

    def _update_metadata(self):
        logging.debug("timer tick")

        delta = self.contrller.get_metadata_delta()

        server_state = delta.get("server_state", None)

        if server_state:
            CD.update_dictionary_no_key_remove(
                self.global_state_cache.get_data("server_state"), server_state
            )

            server_state = self.global_state_cache.get_data("server_state")

            self.status_label.setText(
                self.status_text_template.format(
                    CD.size_bytes_to_pretty_str(server_state["free_space_on_disk"]),
                    server_state["dht_nodes"],
                    CD.size_bytes_to_pretty_str(server_state["dl_info_speed"]),
                    CD.size_bytes_to_pretty_str(server_state["up_info_speed"]),
                )
                + f"   RID: {delta.rid}"
            )

        torrents = delta.get("torrents", {})

        torrents_removed = delta.get("torrents_removed", {})

        if torrents or torrents_removed:
            existing_hashes = set()
            items_to_remove = []

            for item in GUICommon.iter_qtreewidget_items(self._torrent_list_new):
                torrent_hash = item.data(0, QC.Qt.UserRole)

                if torrent_hash in torrents_removed:
                    items_to_remove.append(item)

                    continue

                if torrent_hash not in torrents:
                    continue

                existing_hashes.add(torrent_hash)

                t = torrents[torrent_hash]

                if "name" in t:
                    item.setText(0, t.name)
                if "size" in t:
                    item.setText(1, CD.size_bytes_to_pretty_str(t.size))
                if "progress" in t:
                    item.setText(2, f"{t.progress * 100:.2f}%")
                if "state" in t:
                    item.setText(3, CD.torrent_state_to_pretty(t.state))
                if "ratio" in t:
                    item.setText(4, f"{t.ratio:.3f}")
                if "availability" in t:
                    item.setText(5, f"{t.availability:.3f}")
                if "dlspeed" in t:
                    item.setText(6, CD.size_bytes_to_pretty_str(t.dlspeed))
                if "upspeed" in t:
                    item.setText(7, CD.size_bytes_to_pretty_str(t.upspeed))

            _ = self._torrent_list_new.invisibleRootItem()
            for item in items_to_remove:
                _.removeChild(item)

            if len(existing_hashes) != len(torrents):
                for hash in torrents.keys() - existing_hashes:
                    item = self.get_torrent_tree_widget_item(torrents[hash])
                    item.setData(0, QC.Qt.UserRole, hash)
                    self._torrent_list_new.insertTopLevelItem(0, item)

    def _handle_magnet_dialog(self):
        magnets = dialogs.show_add_magnet_link_dialog(self)

        if magnets:
            self.contrller.add_magnet_links(magnets)

    def _item_checkbox_changed(self, item, column):
        if not item:
            return

        info = item.data(0, QC.Qt.UserRole)

        if not info:
            GUICommon.set_check_item_all_sub_items(item, item.checkState(column))

            return

        if "id" not in info:
            logging.warning(f"Could not find id in torrent files info, {info}")
            return

        id = info["id"]

        if item.checkState(column) == QC.Qt.Checked:
            priority = CC.TORRENT_PRIORITY_NORMAL

        else:
            priority = CC.TORRENT_PRIORITY_DO_NOT_DOWNLOAD

        self.contrller.update_torrents_file_priority_transactional(
            self.selected_torrent_hash, id, priority
        )

    def _right_click_menu(self, position):
        indexes = self.file_tree.selectedIndexes()

        def toggle_action_callback():
            # selectedIndexes returns the item 1 time per column, we only want it once
            for i in filter(lambda i: i.column() == 0, indexes):
                item = self.file_tree.itemFromIndex(i)

                item.setCheckState(0, GUICommon.get_flipped_check_state(item.checkState(0)))

                print(item.data(0, QC.Qt.UserRole))

        menu = QW.QMenu()

        toggle_action = QW.QAction("Toggle Checkbox", menu)
        toggle_action.triggered.connect(toggle_action_callback)
        menu.addAction(toggle_action)

        menu.exec_(self.file_tree.viewport().mapToGlobal(position))

    def _list_item_click(self, list_item: QW.QListWidgetItem):
        t_hash = list_item.data(0, QC.Qt.UserRole)

        self.selected_torrent_hash = t_hash

        self.load_file_for_torrent(t_hash)

    def _search_pressed(self):
        search = self.input_box.text()

        root_item = self._torrent_list_new.invisibleRootItem()

        for i in range(root_item.childCount()):
            item = root_item.child(i)
            item.setHidden(not re.search(search, item.text(0)))

    def _build_treewidget_recursive(
        self, nested_struct: CD.NestedTorrentFileDirectory, parent=None
    ):
        if parent is None:
            parent = QW.QTreeWidgetItem(["/"])

        for name, child in nested_struct.children.items():
            if child.torrents_file:
                item = QW.QTreeWidgetItem(
                    [
                        name,
                        CD.size_bytes_to_pretty_str(child.size),
                        f"{child.torrents_file.progress * 100:.2f}%",
                        CD.get_pretty_download_priority(child.torrents_file.priority),
                        "",
                        f"{child.torrents_file.availability}",
                    ]
                )
                item.setData(0, QC.Qt.UserRole, child.torrents_file)

                item.setFlags(item.flags() | QC.Qt.ItemFlag.ItemIsUserCheckable)

                if child.torrents_file.priority == 0:
                    item.setCheckState(0, QC.Qt.CheckState.Unchecked)
                else:
                    p = parent
                    while p.parent():
                        p.setCheckState(0, QC.Qt.CheckState.Checked)
                        p = p.parent()
                        p.setCheckState(0, QC.Qt.CheckState.Checked)

                    item.setCheckState(0, QC.Qt.CheckState.Checked)
            else:
                item = QW.QTreeWidgetItem(
                    [
                        name,
                        CD.size_bytes_to_pretty_str(child.size),
                        f"{child.get_progress() * 100:.3f}%",
                    ]
                )
                item.setFlags(item.flags() | QC.Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, QC.Qt.CheckState.Unchecked)
                item.setIcon(0, self.style().standardIcon(QW.QStyle.SP_DirOpenIcon))

            parent.addChild(item)

            self._build_treewidget_recursive(child, item)

        return parent

    def get_torrent_tree_widget_item(self, values: dict):
        item = QW.QTreeWidgetItem(
            [
                values.get("name", "N/A"),
                CD.size_bytes_to_pretty_str(values.get("size", 0)),
                f"{values.get('progress', 0) * 100:.2f}%",
                CD.torrent_state_to_pretty(values.get("state", "N/A")),
                f"{values.get('ratio', 0):.3f}",
                f"{values.get('availability', 0):.3f}",
                CD.size_bytes_to_pretty_str(values.get("dlspeed", 0)),
                CD.size_bytes_to_pretty_str(values.get("upspeed", 0)),
            ]
        )

        return item

    def update_torrent_list(self):
        self._torrent_list_new.clear()

        for torrent in self.contrller.get_torrents():
            item = self.get_torrent_tree_widget_item(torrent)
            item.setData(0, QC.Qt.UserRole, torrent.hash)
            self._torrent_list_new.insertTopLevelItem(0, item)

    def load_file_for_torrent(self, torrent_hash: str):
        data = self.contrller.torrent_metadata_cache.get_if_has_data(torrent_hash)

        if data:
            logging.debug(f"Cache hit for torrent hash: {torrent_hash}")
            self.set_tree_contents(data, torrent_hash)
            return

        try:
            data = CG.client_instance.torrents_files(torrent_hash)

            self.contrller.torrent_metadata_cache.add_data(torrent_hash, data)

            self.set_tree_contents(data, torrent_hash)

        except NotFound404Error:
            logging.warning(f"Could not find torrent with hash: {torrent_hash}")

    def set_tree_contents(self, torrent_file_list: TorrentFilesList, cache_key: str = None):
        self.file_tree.clear()

        nested = None
        if cache_key:
            nested = self.torrent_tree_list_cache.get_if_has_non_expired_data(cache_key)

        if not nested:
            nested = CD.build_nested_torrent_structure(torrent_file_list)
            if cache_key:
                self.torrent_tree_list_cache.add_data(cache_key, nested, True)
        else:
            logging.debug("Cache hit on tree list")

        tree = self._build_treewidget_recursive(nested)

        if tree.childCount() > 0:
            self.file_tree.insertTopLevelItems(0, tree.takeChildren())

        else:
            self.file_tree.insertTopLevelItems(0, [tree])

        self.file_tree.resizeColumnToContents(0)
        self.file_tree.sortByColumn(0, QC.Qt.SortOrder.AscendingOrder)
