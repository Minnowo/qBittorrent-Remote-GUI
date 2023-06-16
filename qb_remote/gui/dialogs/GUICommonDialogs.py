import qtpy

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG


def show_yes_cancel_dialog(message: str, parent=None):

    dialog = QW.QMessageBox()
    dialog.setWindowTitle('Confirmation')
    dialog.setText(message)
    dialog.setIcon(QW.QMessageBox.Question)
    dialog.setStandardButtons(QW.QMessageBox.Yes | QW.QMessageBox.Cancel)

    # Execute the dialog and get the user's response
    response = dialog.exec_()

    return response == QW.QMessageBox.Yes
 