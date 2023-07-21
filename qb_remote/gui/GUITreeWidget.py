import logging
import json

import qtpy

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from qb_remote.core import CoreController

from ..core import CoreController
from ..core import CoreConstants

class ExtendedQTreeWidget(QW.QTreeWidget, CoreController.ClientControllerUser):

    def __init__(self, parent = None):
        super().__init__(parent)

        self._context_menu = None
        self._menu_ready = False

    def get_menu(self):
        return self._context_menu

    def set_menu(self, menu):
        self._context_menu = menu
        self._prepare_for_context_menu()
        
    def _show_menu(self, position):

        if not self._context_menu:
            return

        logging.debug("context menu exists")

        if not self.selectedItems():
            return

        logging.debug("selected items ")

        self.update_item_context_menu()

        self._context_menu.exec_(self.viewport().mapToGlobal(position))

    def _prepare_for_context_menu(self):

        if self._menu_ready:
            return

        self.setContextMenuPolicy(QC.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

        self._menu_ready = True

    def update_item_context_menu(self):

        count = len(self.selectedItems())

        logging.debug(self.selectedItems())

        if count == 0:
            return

        if count == 1:

            self.update_item_context_menu_single()

        else:

            self.update_item_context_menu_multi()



    def update_item_context_menu_single(self):
        """
        Called before showing the context menu if there is a single selected item
        """

    def update_item_context_menu_multi(self):
        """
        Called before showing the context menu if there is a 2 ore more selected items
        """


SHOULD_RESUME = 0
SHOULD_PAUSE = 1

class TorrentListTreeWidget(ExtendedQTreeWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        _item_context_menu = QW.QMenu()
        
        self.pause_resume_action = QW.QAction("Pause", _item_context_menu)
        self.pause_resume_action.triggered.connect(self._toggle_torrent_paused)

        _item_context_menu.addAction(self.pause_resume_action)

        self.set_menu(_item_context_menu)


    def update_item_context_menu_single(self):

        selected_item_row = self.selectedItems()[0]

        torrent_hash = selected_item_row.data(0, QC.Qt.UserRole)

        if not torrent_hash:
            logging.warn(f"Could not find torrent hash on row item {selected_item_row}")
            return

        torrent_info = self.CONTROLLER.get_torrents(skip_cache=True, torrent_hashes=[torrent_hash])


        if not torrent_info and len(torrent_info) > 0:
            return

        torrent_info = torrent_info[0]
        priority = torrent_info.get('priority', -1)


        if priority == CoreConstants.TORRENT_PAUSED_PRIORITY:
            self.pause_resume_action.setText("Resume")
            self.pause_resume_action.setData(SHOULD_RESUME)
        else:
            self.pause_resume_action.setText("Pause")
            self.pause_resume_action.setData(SHOULD_PAUSE)
        

    def update_item_context_menu_multi(self):
        """
        Called before showing the context menu if there is a 2 ore more selected items
        """


    def _toggle_torrent_paused(self):

        hash = []

        for selected_item_row in self.selectedItems():

            torrent_hash = selected_item_row.data(0, QC.Qt.UserRole)

            if not torrent_hash:
                logging.warn(f"Could not find torrent hash on row item {selected_item_row}")
                return

            hash .append(torrent_hash)

        print(hash)

        if not hash:
            return

        if self.pause_resume_action.data() == SHOULD_PAUSE:

            self.CONTROLLER.set_torrents_paused(hash)
        
        if self.pause_resume_action.data() == SHOULD_RESUME:

            self.CONTROLLER.set_torrents_resume(hash)

            



