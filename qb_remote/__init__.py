import os
import logging
import sys
import qbittorrentapi
import sys
from dotenv import load_dotenv

import qtpy

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from .gui import GUIClient
from .gui import GUICommon
from .core import CoreGlobals as CG
from .core import CoreData as CD
from .core import CoreController as Controller
from .core import CoreLogging 




def main():
    load_dotenv()
    CoreLogging.setup_logging()
    CoreLogging.add_unhandled_exception_hook()

    client_controller = Controller.ClientController()
    client_controller.boot_everything_base()

    try:
        GUICommon.enable_hi_dpi()
        
        app = QW.QApplication([])
        app.setPalette( GUICommon.get_darkModePalette(app))
        mainwindow = GUIClient.ClientWindow()

        mainwindow.show()

        mainwindow.update_torrent_list()

        app.exec()

    finally:
        client_controller.exit_everything_base()


if __name__ == "__main__":
    main()
