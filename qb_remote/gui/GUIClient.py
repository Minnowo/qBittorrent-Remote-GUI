import sys
import os 
import random
import numpy as np
import re

from qbittorrentapi import TorrentFilesList
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


class ClientWidnow(QW.QMainWindow):
    def __init__(self, controller: Controller.ClientController):
        super().__init__()

        self.contrller = controller

        self.setWindowTitle("qBittorrent File Viewer")

        self.panel = QW.QWidget()
        
        self.split_panel = QW.QSplitter(self.panel)
        self.split_panel.setOrientation(QC.Qt.Orientation.Vertical)

        self.input_box = QW.QLineEdit()
        self.input_box.setPlaceholderText("Regex for torrent name")
        self.input_box.returnPressed.connect(self._search_pressed)

        self.search_button = QW.QPushButton("Search")
        self.search_button.clicked.connect(self._search_pressed)

        self.torrent_list = QW.QListWidget()
        self.torrent_list.itemClicked.connect(self._list_item_click)

        self.file_tree = QW.QTreeWidget()
        self.file_tree.setColumnCount(6)
        self.file_tree.setHeaderLabels(
            ["Name", "Total Size", "Progress", "Download Priority", "Ramaining", "Availability"]
        )

        self.display_label = QW.QLabel("")

        self.split_panel.addWidget(self.torrent_list)
        self.split_panel.addWidget(self.file_tree)

        layout = QW.QVBoxLayout()
        layout.addWidget(self.input_box)
        layout.addWidget(self.search_button)
        layout.addWidget(self.display_label)
        layout.addWidget(self.split_panel)
        self.panel.setLayout(layout)

        self.setCentralWidget(self.panel)

        self.torrent_tree_list_cache = Cache.Expiring_Data_Cache("tree list data cache", CC.TORRENT_CACHE_TIME_SECONDS)


    def _list_item_click(self, list_item: QW.QListWidgetItem):
        t_hash = list_item.data(QC.Qt.UserRole)

        self.load_file_for_torrent(t_hash)


    def _search_pressed(self, *args):

        search = self.input_box.text()
        
        for i in range(self.torrent_list.count()):
            item = self.torrent_list.item(i)
            item.setHidden(not re.search(search, item.text()))




    def update_torrent_list(self):

        self.torrent_list.clear()
        for torrent in CG.client_instance.torrents_info():
            item = QW.QListWidgetItem(torrent.name, self.torrent_list)
            item.setData(QC.Qt.UserRole, torrent.hash)
            self.torrent_list.addItem(item)


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
            logging.warnning(f"Could not find torrent with hash: {torrent_hash}") 



    def _recursive_add(self, nested_struct: CD.NestedTorrentFileDirectory, parent=None):

        if parent is None:
            parent = QW.QTreeWidgetItem(["/"])

        for name, child in nested_struct.children.items():


            if child.torrent:

                item = QW.QTreeWidgetItem(
                    [
                        name,
                        CD.size_bytes_to_pretty_str(child.size),
                        f"{child.torrent['progress'] * 100:.2f}%",
                        CD.get_pretty_download_priority(child.torrent["priority"]),
                        "",
                        f"{child.torrent['availability']}",
                    ]
                )
                item.setFlags(item.flags() | QC.Qt.ItemFlag.ItemIsUserCheckable)

                if child.torrent["priority"] == 0:
                    item.setCheckState(0, QC.Qt.CheckState.Unchecked)
                else:
                    item.setCheckState(0, QC.Qt.CheckState.Checked)
            else:
                item = QW.QTreeWidgetItem(
                    [
                        name,
                        CD.size_bytes_to_pretty_str(child.size),
                    ]
                )

            parent.addChild(item)

            self._recursive_add(child, item)

        return parent

    def set_tree_contents(self, torrent_file_list:  TorrentFilesList, cache_key:str=None):
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
        
        tree = self._recursive_add(nested)

        if tree.childCount() > 0:
            self.file_tree.insertTopLevelItems(0, tree.takeChildren())
            
        else:
            self.file_tree.insertTopLevelItems(0, [tree])

        self.file_tree.resizeColumnToContents(0)