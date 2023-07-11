import qtpy

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG


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


def get_darkModePalette( app=None ) :
    
    darkPalette = app.palette()
    darkPalette.setColor(QG.QPalette.Window, QG.QColor( 53, 53, 53 ) )
    darkPalette.setColor(QG.QPalette.WindowText,QC.Qt.white )
    darkPalette.setColor(QG.QPalette.Disabled, QG.QPalette.WindowText, QG.QColor( 127, 127, 127 ) )
    darkPalette.setColor(QG.QPalette.Base, QG.QColor( 42, 42, 42 ) )
    darkPalette.setColor(QG.QPalette.AlternateBase, QG.QColor( 66, 66, 66 ) )
    darkPalette.setColor(QG.QPalette.ToolTipBase, QC.Qt.white )
    darkPalette.setColor(QG.QPalette.ToolTipText, QC.Qt.white )
    darkPalette.setColor(QG.QPalette.Text, QC.Qt.white )
    darkPalette.setColor(QG.QPalette.Disabled, QG.QPalette.Text, QG.QColor( 127, 127, 127 ) )
    darkPalette.setColor(QG.QPalette.Dark, QG.QColor( 35, 35, 35 ) )
    darkPalette.setColor(QG.QPalette.Shadow, QG.QColor( 20, 20, 20 ) )
    darkPalette.setColor(QG.QPalette.Button, QG.QColor( 53, 53, 53 ) )
    darkPalette.setColor(QG.QPalette.ButtonText, QC.Qt.white )
    darkPalette.setColor(QG.QPalette.Disabled, QG.QPalette.ButtonText, QG.QColor( 127, 127, 127 ) )
    darkPalette.setColor(QG.QPalette.BrightText, QC.Qt.red )
    darkPalette.setColor(QG.QPalette.Link, QG.QColor( 42, 130, 218 ) )
    darkPalette.setColor(QG.QPalette.Highlight, QG.QColor( 42, 130, 218 ) )
    darkPalette.setColor(QG.QPalette.Disabled, QG.QPalette.Highlight, QG.QColor( 80, 80, 80 ) )
    darkPalette.setColor(QG.QPalette.HighlightedText, QC.Qt.white )
    darkPalette.setColor(QG.QPalette.Disabled, QG.QPalette.HighlightedText, QG.QColor( 127, 127, 127 ), )
    
    return darkPalette