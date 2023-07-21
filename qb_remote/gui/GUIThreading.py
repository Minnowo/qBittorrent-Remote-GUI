import os
from typing import Optional
import PySide6.QtCore

import qtpy

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from ..core import CoreData as CD

class WorkerThread(QC.QThread):

    finished2 = QC.Signal(object)

    def __init__(self, callback, *args):
        super().__init__()
        self.callback = callback
        self.args = args
        self.result = None

    def run(self):

        self.result = self.callback(*self.args)

        self.finished2.emit(self.result)

        
