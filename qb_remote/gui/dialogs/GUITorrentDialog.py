import os
import qtpy

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from ...core import CoreConstants as CC
from ...core import CoreGlobals as CG
from ...core import CoreData as CD
from ...core import CoreLogging as logging


class TorrentDialog(QW.QDialog):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)

        self._controller = controller or CG.controller

        if self._controller:
            self.preferences = self._controller.get_client_preferences()
            self.categories = self._controller.get_client_categories()

            for cat in self._controller.settings['categories_to_hide']:

                if cat in self.categories:

                    del self.categories[cat]

        else:
            raise Exception("Controller cannot be null")

        self.public_torrents_root_directory = CC.PUBLIC_TORRENT_ROOT_FOLDER
        self.og_torrent_root_directory = self.preferences['save_path']
        self.torrent_root_directory = self.preferences['save_path']

        if CC.USE_TORRENT_ROOT_FOLDER:
            self.og_torrent_root_directory = CC.TORRENT_ROOT_FOLDER
            self.torrent_root_directory = CC.TORRENT_ROOT_FOLDER


        if CC.IS_PROFILE_MODE:

            self.torrent_root_directory = CD.join_path_remote(self.torrent_root_directory, self._controller.get_client_id(False)) 


        self.magnets = set()
        self.files = set()

        self.setWindowTitle("Input Dialog")
        self.text_edit = QW.QTextEdit(self)
        self.text_edit.setPlaceholderText("Put magnet links or file paths here, 1 per line.")

        self.button_browse_file = QW.QPushButton("Browse")
        self.button_browse_file.clicked.connect(self._add_choose_torrent_file)

        self.label_management_mode = QW.QLabel("Torrent Management Mode: ", self)
        self.dropdown_management_mode = QW.QComboBox(self)
        self.dropdown_management_mode.addItems(["Automatic", "Manual"])
        if CC.IS_PROFILE_MODE:
            self.dropdown_management_mode.setCurrentIndex(1)
            self.dropdown_management_mode.setEnabled(False)
        self.dropdown_management_mode.currentIndexChanged.connect(
            self._torrent_management_mode_changed
        )

        self.label_category = QW.QLabel("Category: ", self)
        self.dropdown_category = QW.QComboBox(self)
        self.dropdown_category.addItems(["None"] + list(self.categories.keys()))
        self.dropdown_category.currentIndexChanged.connect(self._torrent_category_changed)

        self.label_save_location = QW.QLabel("Save files to location: {}".format(self.torrent_root_directory), self)
        self.textbox_save_location = QW.QLineEdit(self)
        self.textbox_save_location .textChanged.connect(self._save_path_text_changed)

        self.label_rename_torrent = QW.QLabel("Rename Torrent: ", self)
        self.textbox_rename_torrent = QW.QLineEdit(self)

        self.checkbox_start_torrent = QW.QCheckBox("Start Torrent", self)
        self.checkbox_start_torrent.setChecked(True)
        self.checkbox_start_torrent.setToolTip("""Starts downloading the torrent automatically.""")
        self.checkbox_skip_hash_check = QW.QCheckBox("Skip Hash Check", self)
        self.checkbox_skip_hash_check.setToolTip("""Skips checking the content hash.
Lets you start seeding / using data without performing the hash check.
Carries the risk of downloading or seeding bad / corrupted data.""")
        self.checkbox_sequential_download = QW.QCheckBox("Download In Sequential Order", self)
        self.checkbox_sequential_download.setToolTip("""Downloads the torrent pieces in order. 
This IS REQUIRED if you want to watch a video or audio file while it downloads.
If you do not plan on watching something while it downloads you should uncheck this option.""")
        self.checkbox_first_and_last_piece = QW.QCheckBox(
            "Download First And Last Pieces First", self
        )
        self.checkbox_first_and_last_piece.setToolTip("""Downloads the first and last pieces of the torrent first.
This is only useful for single-file torrents.
This may will help or may be required to watch a video or audio file while it downloads.""")
        self.checkbox_use_set_public_path = QW.QCheckBox(
            "Use Set Public Path", self
        )
        self.checkbox_use_set_public_path.setEnabled(not not self.public_torrents_root_directory)
        self.checkbox_use_set_public_path.stateChanged.connect(self._use_public_check_changed)
        self.checkbox_use_set_public_path.setToolTip("""If a public path has been set in the settings, put the torrent into this folder.""")
        self.label_final_save_location = QW.QLabel(self)

        self.button_box = QW.QDialogButtonBox(
            QW.QDialogButtonBox.Ok | QW.QDialogButtonBox.Cancel, self
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QW.QVBoxLayout(self)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.button_browse_file)
        layout_2 = QW.QHBoxLayout()
        layout_2.addWidget(self.label_management_mode)
        layout_2.addWidget(self.dropdown_management_mode)
        layout.addLayout(layout_2)
        layout_2 = QW.QHBoxLayout()
        layout_2.addWidget(self.label_category)
        layout_2.addWidget(self.dropdown_category)
        layout.addLayout(layout_2)
        layout.addWidget(self.label_save_location)
        layout.addWidget(self.textbox_save_location)
        layout.addWidget(self.label_final_save_location)
        layout.addWidget(self.checkbox_use_set_public_path)
        layout.addWidget(self.label_rename_torrent)
        layout.addWidget(self.textbox_rename_torrent)
        layout.addWidget(self.checkbox_start_torrent)
        layout.addWidget(self.checkbox_skip_hash_check)
        layout.addWidget(self.checkbox_sequential_download)
        layout.addWidget(self.checkbox_first_and_last_piece)
        layout.addWidget(self.button_box)

        self.installEventFilter(self)

        self._torrent_management_mode_changed()
        self._torrent_category_changed()

    def _save_path_text_changed(self):
        self.label_final_save_location.setText(self.get_final_save_path())

    def _use_public_check_changed(self):

        if self.checkbox_use_set_public_path.isChecked():
            self.label_save_location.setText("Save files to location: {}".format(self.public_torrents_root_directory))
        else:
            self.label_save_location.setText("Save files to location: {}".format(self.torrent_root_directory))
        self._torrent_category_changed()
        self.label_final_save_location.setText(self.get_final_save_path())

    def _torrent_management_mode_changed(self):
        self.textbox_save_location.setEnabled(not self.is_automatic_torrent_mode())

        self._torrent_category_changed()
        self.label_final_save_location.setText(self.get_final_save_path())

    def _torrent_category_changed(self):
        _ = self.dropdown_category.currentText()

        if not self.is_automatic_torrent_mode():

            if CC.IS_PROFILE_MODE:
                if _ == "None":
                    return

                cat = self.categories.get(_, None)

                if cat:
                    cat_path :str= cat['savePath']

                    i = cat_path.replace("\\", "/").rfind("/")

                    if i != -1:

                        cat_path = cat_path[i + 1:]

                    self.textbox_save_location.setText(cat_path)
                
                else:
                    self.textbox_save_location.setText("")
                
                self.label_final_save_location.setText(self.get_final_save_path())

            return


        if _ == "None":
            self.textbox_save_location.setText(self.preferences["save_path"])
            return

        cat = self.categories.get(_, None)

        if cat:
            self.textbox_save_location.setText(cat["savePath"])

        else:
            self.textbox_save_location.setText(self.preferences["save_path"])

    def _add_choose_torrent_file(self):
        file_dialog = QW.QFileDialog(self)
        file_dialog.setFileMode(QW.QFileDialog.ExistingFiles)

        if file_dialog.exec_() != QW.QFileDialog.Accepted:
            return

        files = set(filter(lambda x: os.path.isfile(x), file_dialog.selectedFiles()))

        for i in files - self.files:
            self.files.add(i)
            self.text_edit.append(i)

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

    def is_automatic_torrent_mode(self):
        return not CC.IS_PROFILE_MODE and self.dropdown_management_mode.currentText() == "Automatic"

    def is_category_none(self):
        return self.dropdown_category.currentText() == "None"

    def get_torrent_category(self):
        if self.is_category_none():
            return None

        return self.dropdown_category.currentText()

    def get_final_save_path(self):
        save_path = self.textbox_save_location.text().strip()

        if self.is_automatic_torrent_mode():
            save_path = None

        else:
                
            if self.checkbox_use_set_public_path.isChecked() and self.public_torrents_root_directory:
                save_path = CD.join_path_remote(self.public_torrents_root_directory, self.textbox_save_location.text().strip())
            else:
                save_path = CD.join_path_remote(self.torrent_root_directory, self.textbox_save_location.text().strip())

        return save_path


    def get_magnet_links(self):
        text = self.text_edit.toPlainText()

        m = set(CC.MAGNET_LINK_REGEX.findall(text))
        f = set(filter(lambda x: os.path.isfile(x), text.split("\n")))

        rename_to = self.textbox_rename_torrent.text().strip()

        if not rename_to:
            rename_to = None

        save_path = self.get_final_save_path()

        logging.info(save_path)
        # return {}

        return {
            "urls": m,
            "torrent_files": f,
            "save_path": save_path,
            "category": self.get_torrent_category(),
            "is_skip_checking": self.checkbox_skip_hash_check.isChecked(),
            "is_paused": not self.checkbox_start_torrent.isChecked(),
            # "is_root_folder":None,
            "rename": rename_to,
            # "upload_limit":None,
            # "download_limit":None,
            "use_auto_torrent_management": self.is_automatic_torrent_mode(),
            "is_sequential_download": self.checkbox_sequential_download.isChecked(),
            "is_first_last_piece_priority": self.checkbox_first_and_last_piece.isChecked(),
            # "tags":None,
            # "content_layout":None,
            # "ratio_limit":None,
            # "seeding_time_limit":None,
            # "download_path":None,
            # "use_download_path":None,
            # "stop_condition":None,
        }
