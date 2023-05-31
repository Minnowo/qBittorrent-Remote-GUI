
import qtpy

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from ...core import CoreConstants as CC
from ...core import CoreLogging as logging 

class MagnetLinkDialog(QW.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.magnets = set()
        
        self.setWindowTitle("Input Dialog")
        self.text_edit = QW.QTextEdit(self)

        self.label_management_mode = QW.QLabel("Torrent Management Mode: ", self)
        self.dropdown_management_mode = QW.QComboBox(self)
        self.dropdown_management_mode.addItems(["Automatic", "Manual"])
        
        self.label_save_location = QW.QLabel("Save files to location: ", self)
        self.textbox_save_location = QW.QLineEdit(self)
        
        self.label_rename_torrent = QW.QLabel("Rename Torrent: ", self)
        self.textbox_rename_torrent = QW.QLineEdit(self)
        
        self.checkbox_start_torrent = QW.QCheckBox("Start Torrent", self)
        self.checkbox_start_torrent.setChecked(true)
        self.checkbox_skip_hash_check = QW.QCheckBox("Skip Hash Check", self)
        self.checkbox_sequential_download = QW.QCheckBox("Download In Sequential Order", self)
        self.checkbox_first_and_last_piece = QW.QCheckBox("Download First And Last Pieces First", self)

        self.button_box = QW.QDialogButtonBox(QW.QDialogButtonBox.Ok | QW.QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QW.QVBoxLayout(self)
        layout.addWidget(self.text_edit)
        layout_2 = QW.QHBoxLayout()
        layout_2.addWidget(self.label_management_mode)
        layout_2.addWidget(self.dropdown_management_mode)
        layout.addLayout(layout_2)
        layout.addWidget(self.label_save_location)
        layout.addWidget(self.textbox_save_location)
        layout.addWidget(self.label_rename_torrent)
        layout.addWidget(self.textbox_rename_torrent)
        layout.addWidget(self.checkbox_start_torrent)
        layout.addWidget(self.checkbox_skip_hash_check)
        layout.addWidget(self.checkbox_sequential_download)
        layout.addWidget(self.checkbox_first_and_last_piece)
        layout.addWidget(self.button_box)

        self.installEventFilter(self)
        
    def eventFilter(self, obj, event):
        if obj == self and event.type() == QC.QEvent.WindowActivate:
            self.check_pull_clipboard()
        
        return super().eventFilter(obj, event)
        
    def check_pull_clipboard(self):

        clipboard = QW.QApplication.clipboard()

        try:
            text = clipboard.text()
            
            m = set(CC.MAGNET_LINK_REGEX.findall(text))

            links = "\n".join(m - self.magnets)

            self.magnets.update(m)

            links = links.strip()

            if links:
                self.text_edit.append(links)

        except Exception as e:
            logging.error(e)
            pass


    def get_magnet_links(self):
        text = self.text_edit.toPlainText()
        
        m = set(CC.MAGNET_LINK_REGEX.findall(text))

        save_path = self.textbox_save_location.text().strip()

        if not save_path:
            save_path = None

        rename_to = self.textbox_rename_torrent.text().strip()

        if not rename_to:
            rename_to = None

        return {
        "urls": m ,
        "save_path":save_path,
        # "category":None,
        "is_skip_checking":self.checkbox_skip_hash_check.isChecked(),
        "is_paused":not self.checkbox_start_torrent.isChecked(),
        # "is_root_folder":None,
        "rename":rename_to,
        # "upload_limit":None,
        # "download_limit":None,
        "use_auto_torrent_management":self.dropdown_management_mode.currentText() == "Automatic",
        "is_sequential_download":self.checkbox_sequential_download.isChecked(),
        "is_first_last_piece_priority":self.checkbox_first_and_last_piece.isChecked(),
        # "tags":None,
        # "content_layout":None,
        # "ratio_limit":None,
        # "seeding_time_limit":None,
        # "download_path":None,
        # "use_download_path":None,
        # "stop_condition":None,
        }
