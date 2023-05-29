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
from .core import CoreGlobals as CG
from .core import CoreData as CD
from .core import CoreController as Controller
from .core import CoreLogging as logging


def check_qbit_auth():
    try:
        CG.client_instance.auth_log_in()
        return True
    except qbittorrentapi.LoginFailed as e:
        logging.error(e)
        sys.exit(1)

    return False


def main():
    load_dotenv()
    logging.setup_logger()

    CG.client_connection_settings = dict(
        host=os.getenv("qbit_host"),
        port=os.getenv("qbit_port"),
        username=os.getenv("qbit_username"),
        password=os.getenv("qbit_password"),
    )

    CG.client_instance = qbittorrentapi.Client(**CG.client_connection_settings)

    CG.client_initialized = check_qbit_auth()

    logging.info(CD.get_client_build_information())

    client_controller = Controller.ClientController()
    client_controller.boot_everything_base()

    try:
        app = QW.QApplication([])
        mainwindow = GUIClient.ClientWidnow(client_controller)

        mainwindow.update_torrent_list()

        mainwindow.show()

        app.exec()

    finally:
        client_controller.exit_everything_base()
        CG.client_instance.auth_log_out()


if __name__ == "__main__":
    main()
