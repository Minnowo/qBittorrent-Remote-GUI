import os
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
from .core import CoreLogging as logging




def main():
    load_dotenv()
    logging.setup_logger()

    client_controller = Controller.ClientController()
    client_controller.boot_everything_base()

    try:
        GUICommon.enable_hi_dpi()
        
        app = QW.QApplication([])
        app.setPalette( GUICommon.get_darkModePalette(app))
        mainwindow = GUIClient.ClientWindow(client_controller)

        mainwindow.show()

        mainwindow.update_torrent_list()

        app.exec()

    finally:
        client_controller.exit_everything_base()


if __name__ == "__main__":
    main()
