import os
import qtpy

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from ...core import CoreConstants as CC
from ...core import CoreGlobals as CG
from ...core import CoreLogging as logging

from . import GUICommonDialogs


class SettingsDialog(QW.QDialog):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)

        self._controller = controller or CG.controller

        layout = QW.QVBoxLayout()
        self.setLayout(layout)

        tab_widget = QW.QTabWidget()
        layout.addWidget(tab_widget)

        client_settings_tab = QW.QWidget()
        settings_layout =QW. QVBoxLayout()
        client_settings_tab.setLayout(settings_layout)

        label = QW.QLabel('Client ID:')
        self.line_edit__client_id = QW.QLineEdit()
        self.line_edit__client_id.setText(self._controller.get_client_id(False))
        self.line_edit__client_id.setMaxLength(64)
        self.line_edit__client_id.setEnabled(not CC.USE_HARDWARE_ID)

        settings_layout.addWidget(label)
        settings_layout.addWidget(self.line_edit__client_id)
        
        tab_widget.addTab(client_settings_tab, "Settings")


        self.button_box = QW.QDialogButtonBox(
            QW.QDialogButtonBox.Ok | QW.QDialogButtonBox.Cancel, self
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout.addWidget(self.button_box)

    def save(self):

        new_client_id = self.line_edit__client_id.text()
        if new_client_id != self._controller.get_client_id(False):

            if GUICommonDialogs.show_yes_cancel_dialog("Are you sure you want to update your client ID? You will lose the ability to see your torrents because the client does not support renaming yet."):
                self._controller.change_client_id(new_client_id)
            else:
                return False

        return True 

    def accept(self) -> None:

        if not self.save():
            return

        return super().accept()
