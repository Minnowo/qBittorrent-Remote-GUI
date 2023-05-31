
import qtpy

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from .GUIMagnetDialog import MagnetLinkDialog


def show_add_torrent_file_dialog(parent=None):
        file_dialog = QW.QFileDialog(parent)
        file_dialog.setFileMode(QW.QFileDialog.ExistingFiles)

        if file_dialog.exec_() == QW.QFileDialog.Accepted:

            return file_dialog.selectedFiles()

        return []


def show_add_magnet_link_dialog(parent=None):

    dialog = MagnetLinkDialog(parent)

    if dialog.exec_() == QW.QDialog.Accepted:
         return dialog.get_magnet_links()
    
    return set()