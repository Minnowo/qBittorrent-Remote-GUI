import os
import math

import qtpy

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from ..core import CoreData as CD

def iter_qtreewidget_items(qtreewidget: QW.QTreeWidget):
    root_item = qtreewidget.invisibleRootItem()

    for i in range(root_item.childCount()):
        yield root_item.child(i)


def get_flipped_check_state(state: QC.Qt.CheckState):
    if state == QC.Qt.CheckState.Checked:
        return QC.Qt.CheckState.Unchecked

    return QC.Qt.CheckState.Checked


def set_check_item_all_sub_items(
    item: QW.QTreeWidgetItem | QW.QListWidgetItem, checked: QC.Qt.CheckState
):
    for index in range(item.childCount()):
        i = item.child(index)

        if i.flags() & QC.Qt.ItemFlag.ItemIsUserCheckable:
            i.setCheckState(0, checked)

        set_check_item_all_sub_items(i, checked)


def enable_hi_dpi() -> None:
    """Allow to HiDPI.

    This function must be set before instantiation of QApplication..
    For Qt6 bindings, HiDPI “just works” without using this function.
    """

    if hasattr(QC.Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QG.QGuiApplication.setAttribute(QC.Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    if hasattr(QC.Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QG.QGuiApplication.setAttribute(QC.Qt.ApplicationAttribute.AA_EnableHighDpiScaling)

    if hasattr(QC.Qt, "HighDpiScaleFactorRoundingPolicy"):
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
        QG.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            QC.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

def get_darkModePalette( app=None ) :

    BACKGROUND = QG.QColor( 53, 53, 53 )
    BACKGROUND_DARK = QG.QColor( 42, 42, 42 )
    BACKGROUND_LIGHT = QG.QColor( 66, 66, 66 )

    FOREGROUND = QG.QColor( 255, 255, 255 )
    FOREGROUND_DISABLED = QG.QColor( 127, 127, 127 )

    HIGHLIGHT = QG.QColor( 42, 130, 218 )
    HIGHLIGHT_DISABLED = QG.QColor( 80, 80, 80 )

    LINK = QG.QColor( 42, 130, 218 )
    DARK = QG.QColor( 35, 35, 35 )
    SHADOW = QG.QColor( 20, 20, 20 )
    BRIGHT_TEXT = QC.Qt.red
    
    darkPalette = app.palette()

    darkPalette.setColor(QG.QPalette.Window, BACKGROUND )
    darkPalette.setColor(QG.QPalette.Base, BACKGROUND_DARK )
    darkPalette.setColor(QG.QPalette.AlternateBase, BACKGROUND_LIGHT )

    darkPalette.setColor(QG.QPalette.WindowText, FOREGROUND )
    darkPalette.setColor(QG.QPalette.Disabled, QG.QPalette.WindowText, FOREGROUND_DISABLED )

    darkPalette.setColor(QG.QPalette.ToolTipBase, BACKGROUND )
    darkPalette.setColor(QG.QPalette.ToolTipText, FOREGROUND )
    darkPalette.setColor(QG.QPalette.Disabled, QG.QPalette.ToolTipText, FOREGROUND_DISABLED )

    darkPalette.setColor(QG.QPalette.Text, FOREGROUND )
    darkPalette.setColor(QG.QPalette.Disabled, QG.QPalette.Text, FOREGROUND_DISABLED )

    darkPalette.setColor(QG.QPalette.Dark, DARK )
    darkPalette.setColor(QG.QPalette.Shadow, SHADOW )

    darkPalette.setColor(QG.QPalette.BrightText, BRIGHT_TEXT )
    darkPalette.setColor(QG.QPalette.Link, LINK )
    darkPalette.setColor(QG.QPalette.Highlight, HIGHLIGHT )
    darkPalette.setColor(QG.QPalette.Disabled, QG.QPalette.Highlight, HIGHLIGHT_DISABLED )

    darkPalette.setColor(QG.QPalette.Button, BACKGROUND )
    darkPalette.setColor(QG.QPalette.ButtonText, FOREGROUND )
    darkPalette.setColor(QG.QPalette.Disabled, QG.QPalette.ButtonText, FOREGROUND_DISABLED )

    darkPalette.setColor(QG.QPalette.HighlightedText, FOREGROUND )
    darkPalette.setColor(QG.QPalette.Disabled, QG.QPalette.HighlightedText, FOREGROUND_DISABLED )

    return darkPalette


class InfiniteProgressBar(QW.QProgressBar):
    def __init__(self, step_amount=10,timer_speed_ms=100):
        super().__init__()

        self.timer_delay = timer_speed_ms
        self.step_amount = step_amount

        self.timer = QC.QTimer(self)
        self.timer.timeout.connect(self.update_progress)

        self.progress_value = 0

    def update_progress(self):
        if self.step_amount < 0:
            self.progress_value = (int(self.progress_value + self.never_reach_100_func(self.progress_value)) ) % 100
        else:
            self.progress_value = (self.progress_value + self.step_amount) % 100
        self.setValue(self.progress_value)

    def stop_progress(self):
        self.timer.stop()

    def start_progress(self):
        self.timer.start(self.timer_delay)

    def reset_progress(self):
        self.progress_value = 0
        self.reset()


    def never_reach_100_func(self, x):

        if x <= 0:
            return 1.0
        elif x >= 100:
            return 0.0

        scaling_factor =  5 
        decay_rate = x / 5750   

        return scaling_factor * math.exp(-decay_rate * x)
