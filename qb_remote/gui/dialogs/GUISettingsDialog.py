import os
import qtpy


from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from ...core import CoreConstants as CC
from ...core import CoreGlobals as CG
from ...core import CoreController
from ...core import CoreLogging as logging

from . import GUICommonDialogs


class SettingsDialog(QW.QDialog):
    def __init__(self, controller:CoreController.ClientController=None, parent=None):
        super().__init__(parent)

        self._controller:CoreController.ClientController = controller or CG.controller

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



        qbittorrent_tab = QW.QWidget()
        settings_layout =QW. QVBoxLayout()
        qbittorrent_tab.setLayout(settings_layout)

        self.line_edit__qbittorrent_ip = QW.QLineEdit()
        self.line_edit__qbittorrent_ip.setPlaceholderText("127.0.0.1")
        self.line_edit__qbittorrent_ip.setText(self._controller.get_qbittorrent_setting("host"))
        self.spinbox__qbittorrent_port= QW.QSpinBox()
        self.spinbox__qbittorrent_port.setMinimum(0)
        self.spinbox__qbittorrent_port.setMaximum(9999999)
        self.spinbox__qbittorrent_port.setValue(self._controller.get_qbittorrent_setting("port"))
        self.line_edit__qbittorrent_username = QW.QLineEdit()
        self.line_edit__qbittorrent_username.setPlaceholderText("username")
        self.line_edit__qbittorrent_username.setText(self._controller.get_qbittorrent_setting("username"))
        self.line_edit__qbittorrent_password= QW.QLineEdit()
        self.line_edit__qbittorrent_password.setPlaceholderText("password")
        self.checkbox__autoconnect_at_startup = QW.QCheckBox("Connect at startup")
        self.checkbox__autoconnect_at_startup.setChecked(self._controller.get_qbittorrent_setting("autoconnect"))
        self.checkbox__reconnect_when_updated = QW.QCheckBox("Reconnect after settings update")
        self.checkbox__reconnect_when_updated.setChecked(self._controller.get_qbittorrent_setting("reconnect_on_update"))

        _layouthz1 = QW.QHBoxLayout()
        _layouthz1.addWidget(self.line_edit__qbittorrent_ip)
        _layouthz1.addWidget(self.spinbox__qbittorrent_port)
        settings_layout.addLayout(_layouthz1)
        settings_layout.addWidget(self.line_edit__qbittorrent_username)
        settings_layout.addWidget(self.line_edit__qbittorrent_password)
        _layouthz1 = QW.QHBoxLayout()
        _layouthz1.addWidget(self.checkbox__autoconnect_at_startup)
        _layouthz1.addWidget(self.checkbox__reconnect_when_updated)
        settings_layout.addLayout(_layouthz1)

        
        tab_widget.addTab(client_settings_tab, "Client Settings")
        tab_widget.addTab(qbittorrent_tab, "qBittorrent Settings")


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

        refresh_qbit_connection = False

        ip = self.line_edit__qbittorrent_ip.text().strip()
        if ip and ip != self._controller.get_qbittorrent_setting("host"): 
            self._controller.set_qbittorrent_setting("host", ip)
            refresh_qbit_connection = True

        port = self.spinbox__qbittorrent_port.value()
        if port and port != self._controller.get_qbittorrent_setting("port"):
            self._controller.set_qbittorrent_setting("port", port)
            refresh_qbit_connection = True

        username = self.line_edit__qbittorrent_username.text().strip()
        if username and username != self._controller.get_qbittorrent_setting("username"):
            self._controller.set_qbittorrent_setting("username", username)
            refresh_qbit_connection = True

        password = self.line_edit__qbittorrent_password.text().strip()
        if password and password != self._controller.get_qbittorrent_setting("password"):
            self._controller.set_qbittorrent_setting("password", password)
            refresh_qbit_connection = True

        self._controller.set_qbittorrent_setting("autoconnect", self.checkbox__autoconnect_at_startup.isChecked())
        self._controller.set_qbittorrent_setting("reconnect_on_update", self.checkbox__reconnect_when_updated.isChecked())

        if refresh_qbit_connection and self.checkbox__reconnect_when_updated.isChecked():
            self._controller.init_qbittorrent_connection()

        return True 

    def accept(self) -> None:

        if not self.save():
            return

        return super().accept()
