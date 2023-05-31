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
