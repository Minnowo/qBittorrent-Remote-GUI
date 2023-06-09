import qtpy

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from .GUITorrentDialog import TorrentDialog
from .GUISettingsDialog import SettingsDialog
from .GUICommonDialogs import *

def show_add_torrent_file_dialog(parent=None):
    file_dialog = QW.QFileDialog(parent)
    file_dialog.setFileMode(QW.QFileDialog.ExistingFiles)

    if file_dialog.exec_() == QW.QFileDialog.Accepted:
        return file_dialog.selectedFiles()

    return []


def show_add_magnet_link_dialog(controller=None,parent=None):
    dialog = TorrentDialog(controller=controller,parent=parent)

    if dialog.exec_() == QW.QDialog.Accepted:
        return dialog.get_magnet_links()

    return {}
