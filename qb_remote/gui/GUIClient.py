import sys
import logging
import json
import concurrent.futures
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

from ..core import CoreController 
from ..core import CoreCaches as Cache
from ..core import CoreGlobals as CG
from ..core import CoreData as CD
from ..core import CoreConstants as CC

from . import GUICommon
from . import GUITreeWidget
from . import dialogs
from . import GUIThreading


class ClientWindow(QW.QMainWindow, CoreController.ClientControllerUser):
    def __init__(self):
        super().__init__()

        self.selected_torrent_hash: str = ""

        self.pause = False

        self.metadata_sync_timer = QC.QTimer(self)
        self.metadata_sync_timer.timeout.connect(self._update_metadata)
        self.metadata_sync_timer.start(CC.TORRENT_METADATA_SYNC_RATE_MS)

        self.setWindowTitle("qBittorrent Remote")

        self.panel = QW.QWidget()

        self.split_panel = QW.QSplitter(self.panel)
        self.split_panel.setOrientation(QC.Qt.Orientation.Vertical)

        input_box = QW.QLineEdit()
        input_box.setPlaceholderText("Regex for torrent name")
        input_box.returnPressed.connect(self._search_pressed)

        search_button = QW.QPushButton("Search")
        search_button.clicked.connect(self._search_pressed)

        update_torrent_list_button = QW.QPushButton("Update Torrents")
        update_torrent_list_button.clicked.connect(self.update_torrent_list)




        self.status_text_template = "Free Space: {}   DHT: {}   Download: {}   Upload: {}"
        self.status_label = QW.QLabel(self.status_text_template)
        self.status_label.setAlignment(QC.Qt.AlignRight)

        self.infite_progress_bar = GUICommon.InfiniteProgressBar(step_amount=-1)
        self.infite_progress_bar.setVisible(False)

        self.status_bar = QW.QStatusBar(self)
        self.status_bar.addWidget(self.status_label)
        self.status_bar.addWidget(self.infite_progress_bar)



        ### torrent list start
        self._torrent_list = GUITreeWidget.TorrentListTreeWidget()
        self._torrent_list.setContextMenuPolicy(QC.Qt.CustomContextMenu)
        self._torrent_list.setColumnCount(6)
        self._torrent_list.setSortingEnabled(True)
        self._torrent_list.header().setSectionResizeMode(QW.QHeaderView.ResizeToContents)
        self._torrent_list.header().setStretchLastSection(False)
        self._torrent_list.setHeaderLabels(
            ["Name", "Size", "Progress", "Status", "Ratio", "Availability", "Download", "Upload"]
        )

        
        self._torrent_list.itemSelectionChanged.connect(self._list_item_selection_changed)
        ### torrent list end


        self.file_tree = GUITreeWidget.ExtendedQTreeWidget()
        self.file_tree.setSortingEnabled(True)
        self.file_tree.header().setSectionResizeMode(QW.QHeaderView.ResizeToContents)
        self.file_tree.header().setStretchLastSection(False)
        self.file_tree.setSelectionMode(QW.QAbstractItemView.ExtendedSelection)
        self.file_tree.setColumnCount(6)
        self.file_tree.setHeaderLabels(
            ["Name", "Total Size", "Progress", "Download Priority", "Ramaining", "Availability"]
        )
        self.file_tree.itemChanged.connect(self._item_checkbox_changed)


        menu = QW.QMenu()

        toggle_action = QW.QAction("Toggle Checkbox", menu)
        toggle_action.triggered.connect(self._toggle_selected_files)
        menu.addAction(toggle_action)

        self.file_tree.set_menu(menu)





        self.file_menu = self.menuBar().addMenu("File")
        self.add_torrent_file_action = self.file_menu.addAction("Add Torrent(s)")
        self.add_torrent_file_action.triggered.connect(self._handle_magnet_dialog)

        self.login_menu = self.file_menu.addAction("Connect")
        self.login_menu.triggered.connect(self.CONTROLLER.init_qbittorrent_connection)
        self.logout_menu = self.file_menu.addAction("Disconnect")
        self.logout_menu.triggered.connect(self.CONTROLLER.shutdown_qbittorrent_connection)

        self.settings_action = self.menuBar().addAction("Settings")
        self.settings_action.triggered.connect(self._open_settings_dialog)

        # self.split_panel.addWidget(self.torrent_list)
        self.split_panel.addWidget(self._torrent_list)
        self.split_panel.addWidget(self.file_tree)

        layout = QW.QVBoxLayout()
        layout_2 = QW.QHBoxLayout()
        layout_2.addWidget(input_box)
        layout_2.addWidget(search_button)
        layout_2.addWidget(update_torrent_list_button)
        layout.addLayout(layout_2)
        layout.addWidget(self.split_panel)
        self.panel.setLayout(layout)

        self.setStatusBar(self.status_bar)
        self.setCentralWidget(self.panel)

        self.load_torrents_files_timer = QC.QTimer(self)
        self.load_torrents_files_timer.timeout.connect(self._load_torrents_files_timer_tick)
        self.LOAD_TORRENTS_FILES_TIMER_INTERVAL_MS = 200

        self._threads = []

        self.torrent_tree_list_cache = Cache.Expiring_Data_Cache(
            "tree list data cache", CC.TORRENT_CACHE_TIME_SECONDS
        )

        self._update_metadata()

    def _update_metadata(self):

        if self.pause or not self.CONTROLLER.is_qbittorrent_ok():
            return

        delta = self.CONTROLLER.get_metadata_delta()


        if not delta:
            return

        server_state = delta.get("server_state", None)

        if server_state:

            CACHE_KEY = "server_state"
            CACHE = self.CONTROLLER.qbittorrent_cache

            cached_state = CACHE.get_if_has_data(CACHE_KEY, True)

            if cached_state:

                CD.update_dictionary_no_key_remove(
                    cached_state, server_state
                )

                CACHE.add_data(CACHE_KEY, cached_state, True)

                server_state = cached_state

            else:
                CACHE.add_data(CACHE_KEY, server_state, True)


            self.status_label.setText(
                self.status_text_template.format(
                    CD.size_bytes_to_pretty_str(server_state.get("free_space_on_disk", -1)),
                    server_state.get("dht_nodes","-1"),
                    CD.size_bytes_to_pretty_str(server_state.get("dl_info_speed", -1)),
                    CD.size_bytes_to_pretty_str(server_state.get("up_info_speed", -1)),
                )
                + f"   RID: {delta.rid}"
            )

        torrents = delta.get("torrents", {})

        torrents_removed = delta.get("torrents_removed", {})

        if not torrents and not torrents_removed:
            return

        existing_hashes = set()
        items_to_remove = []

        for item in GUICommon.iter_qtreewidget_items(self._torrent_list):
            torrent_hash = item.data(0, QC.Qt.UserRole)

            if torrent_hash in torrents_removed:
                items_to_remove.append(item)

                continue

            if torrent_hash not in torrents:
                continue

            existing_hashes.add(torrent_hash)

            t: dict = torrents[torrent_hash]

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

        _ = self._torrent_list.invisibleRootItem()
        for item in items_to_remove:
            _.removeChild(item)

        if len(existing_hashes) != len(torrents):
            for hash in torrents.keys() - existing_hashes:

                metadata = torrents[hash]

                if not self.CONTROLLER.torrent_passes_filter(metadata):
                    continue

                item = self.get_torrent_tree_widget_item(metadata)
                item.setData(0, QC.Qt.UserRole, hash)
                self._torrent_list.insertTopLevelItem(0, item)

    def _handle_magnet_dialog(self):

        if not self.CONTROLLER.is_qbittorrent_ok():
            return

        magnets = dialogs.show_add_magnet_link_dialog(self.CONTROLLER, self)

        a = magnets.get('torrent_files', None)
        b = magnets.get('urls', None)

        if a or b:
            self.CONTROLLER.upload_torrents(magnets)


    def _open_settings_dialog(self):

        dialogs.SettingsDialog(self.CONTROLLER).exec_()

   
    def _toggle_selected_files(self):

        for item in self.file_tree.selectedItems():

            item.setCheckState(0, GUICommon.get_flipped_check_state(item.checkState(0)))


    def _item_checkbox_changed(self, item, column):
        if not item or self.pause or not self.CONTROLLER.is_qbittorrent_ok():
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
            priority = CC.TORRENT_FILE_PRIORITY_NORMAL

        else:
            priority = CC.TORRENT_FILE_PRIORITY_DO_NOT_DOWNLOAD

        self.CONTROLLER.update_torrents_file_priority_transactional(
            self.selected_torrent_hash, id, priority
        )

    def _torrent_right_click_menu(self, position): 

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

        menu.exec_(self._torrent_list.viewport().mapToGlobal(position))

    def _build_treewidget_recursive(
                self, nested_struct: CD.NestedTorrentFileDirectory, parent=None, style=None
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

                self._build_treewidget_recursive(child, item, style=style)

            return parent





    def _load_torrents_files_timer_tick(self):
        if self.pause or not self.CONTROLLER.is_qbittorrent_ok():
            self.load_torrents_files_timer.stop()
            return

        self.load_torrents_files_timer.stop()
        self.show_infinite_progress()

        def c(x): return self.CONTROLLER.get_torrents_files(x), x


        w = GUIThreading.WorkerThread(
            c,
            self.selected_torrent_hash
        )
        w.finished2.connect(self._on_torrent_files_loaded)
        w.start()
        
        self._threads.append(w)
        self._threads = list(filter(lambda x : not x.isFinished(), self._threads))



    @QC.Slot(object)
    def _on_torrent_files_loaded(self, *args):

        # holy this is stupid
        a = args[0]

        torrent_files, torrent_hash = a

        if torrent_hash != self.selected_torrent_hash:
            return

        self.set_tree_contents(torrent_files, torrent_hash)

        self.hide_infinite_progress()


    def _list_item_selection_changed(self):
        if self.pause or not self.CONTROLLER.is_qbittorrent_ok():
            return

        item = self._torrent_list.selectedItems()

        if not item:
            return 

        item = item[0]

        t_hash = item.data(0, QC.Qt.UserRole)
        
        self.selected_torrent_hash = t_hash

        self.load_selected_torrents_files()



    def _search_pressed(self):
        if self.pause:
            return

        search = self.input_box.text()

        use_ignorecase = not not re.search(r"[A-Z]", search)

        root_item = self._torrent_list.invisibleRootItem()

        for i in range(root_item.childCount()):
            item = root_item.child(i)

            if use_ignorecase:
                item.setHidden(not re.search(search, item.text(0)))
            else:
                item.setHidden(not re.search(search, item.text(0), re.IGNORECASE))


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
        if self.pause or not self.CONTROLLER.is_qbittorrent_ok():
            return
        self._torrent_list.clear()

        for torrent in self.CONTROLLER.get_torrents():
            if not self.CONTROLLER.torrent_passes_filter(torrent):
                continue
            item = self.get_torrent_tree_widget_item(torrent)
            item.setData(0, QC.Qt.UserRole, torrent.hash)
            self._torrent_list.insertTopLevelItem(0, item)




    def set_tree_contents(self, torrent_file_list: TorrentFilesList, cache_key: str = None):
        if self.pause:
            return

        self.show_infinite_progress()

        nested = None
        if cache_key:
            nested = self.torrent_tree_list_cache.get_if_has_non_expired_data(cache_key)

        if not nested:
            nested = CD.build_nested_torrent_structure(torrent_file_list)
            if cache_key:
                self.torrent_tree_list_cache.add_data(cache_key, nested, True)
        else:
            logging.debug("Cache hit on tree list")

        tree = self._build_treewidget_recursive(nested, style=self.style())

        self.file_tree.clear()

        if tree.childCount() > 0:
            self.file_tree.insertTopLevelItems(0, tree.takeChildren())

        else:
            self.file_tree.insertTopLevelItems(0, [tree])

        self.file_tree.resizeColumnToContents(0)
        self.file_tree.sortByColumn(0, QC.Qt.SortOrder.AscendingOrder)

        self.hide_infinite_progress()




    def load_selected_torrents_files(self):
        self.load_torrents_files_timer.stop()
        self.load_torrents_files_timer.start(self.LOAD_TORRENTS_FILES_TIMER_INTERVAL_MS)


    def show_infinite_progress(self):

        self.infite_progress_bar.progress_value = 10
        self.infite_progress_bar.setVisible(True)
        self.infite_progress_bar.start_progress()
        QW.QApplication.processEvents()

    def hide_infinite_progress(self):

        self.infite_progress_bar.setVisible(False)
        self.infite_progress_bar.stop_progress()
        self.infite_progress_bar.reset_progress()