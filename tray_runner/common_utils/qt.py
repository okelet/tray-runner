"""
tray_runner.qt_utils modules.

Borrowed and modified from https://gist.github.com/cpbotha/1b42a20c8f3eb9bb7cb8
"""
import logging
from typing import Dict, Optional, Type, Union

from PySide6.QtCore import QMetaObject, Qt
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QWidget


class UiLoader(QUiLoader):  # pylint: disable=too-few-public-methods
    """
    Subclass :class:`~PySide.QtUiTools.QUiLoader` to create the user interface
    in a base instance.
    Unlike :class:`~PySide.QtUiTools.QUiLoader` itself this class does not
    create a new instance of the top-level widget, but creates the user
    interface in an existing instance of the top-level class.
    This mimics the behavior of :func:`PyQt4.uic.loadUi`.
    """

    def __init__(self, base_instance: Optional[QWidget] = None, custom_widgets: Optional[Dict[str, Type]] = None):
        """
        Create a loader for the given ``base_instance``.
        The user interface is created in ``base_instance``, which must be an
        instance of the top-level class in the user interface to load, or a
        subclass thereof.
        ``custom_widgets`` is a dictionary mapping from class name to class object
        for widgets that you've promoted in the Qt Designer interface. Usually,
        this should be done by calling registerCustomWidget on the QUiLoader, but
        with PySide 1.1.2 on Ubuntu 12.04 x86_64 this causes a segfault.
        ``parent`` is the parent object of this loader.
        """

        QUiLoader.__init__(self, base_instance)
        self.base_instance = base_instance
        self.custom_widgets = custom_widgets or {}

    def createWidget(self, class_name: str, parent: Optional[QWidget] = None, name: Optional[str] = ""):  # pylint: disable=invalid-name
        """
        Function that is called for each widget defined in ui file,
        overridden here to populate base_instance instead.
        """

        if parent is None and self.base_instance:
            # supposed to create the top-level widget, return the base instance
            # instead
            return self.base_instance

        if class_name in self.availableWidgets() and name:
            # create a new widget for child widgets
            widget = QUiLoader.createWidget(self, class_name, parent, name)

        else:
            # if not in the list of availableWidgets, must be a custom widget
            # this will raise KeyError if the user has not supplied the
            # relevant class_name in the dictionary, or TypeError, if
            # custom_widgets is None
            try:
                widget = self.custom_widgets[class_name](parent)

            except (TypeError, KeyError) as ex:
                raise Exception("No custom widget " + class_name + " found in custom_widgets param of UiLoader __init__.") from ex

        if self.base_instance and name:
            # set an attribute for the new child widget on the base
            # instance, just like PyQt4.uic.loadUi does.
            setattr(self.base_instance, name, widget)

            # this outputs the various widget names, e.g.
            # sampleGraphicsView, dockWidget, samplesTableView etc.
            # print(name)

        return widget


def load_ui(ui_file, base_instance: Optional[QWidget] = None, custom_widgets: Optional[Dict[str, Type]] = None, working_directory: Optional[str] = None) -> QWidget:
    """
    Dynamically load a user interface from the given ``ui_file``.
    ``ui_file`` is a string containing a file name of the UI file to load.
    If ``base_instance`` is ``None``, a new instance of the top-level widget
    will be created.  Otherwise, the user interface is created within the given
    ``base_instance``.  In this case ``base_instance`` must be an instance of the
    top-level widget class in the UI file to load, or a subclass thereof.  In
    other words, if you've created a ``QMainWindow`` interface in the designer,
    ``base_instance`` must be a ``QMainWindow`` or a subclass thereof, too.  You
    cannot load a ``QMainWindow`` UI file with a plain
    :class:`~PySide.QtGui.QWidget` as ``base_instance``.
    ``custom_widgets`` is a dictionary mapping from class name to class object
    for widgets that you've promoted in the Qt Designer interface. Usually,
    this should be done by calling registerCustomWidget on the QUiLoader, but
    with PySide 1.1.2 on Ubuntu 12.04 x86_64 this causes a segfault.
    :method:`~PySide.QtCore.QMetaObject.connectSlotsByName()` is called on the
    created user interface, so you can implement your slots according to its
    conventions in your widget class.
    Return ``base_instance``, if ``base_instance`` is not ``None``. Otherwise,
    return the newly created instance of the user interface.
    """

    loader = UiLoader(base_instance, custom_widgets)

    if working_directory is not None:
        loader.setWorkingDirectory(working_directory)

    widget = loader.load(ui_file)
    QMetaObject.connectSlotsByName(widget)
    return widget


def checkbox_tristate_from_val(val: Optional[bool]) -> Qt.CheckState:
    """
    Converts an optional boolean value to a CheckState.
    """
    if val is None:
        return Qt.CheckState.PartiallyChecked
    if val:
        return Qt.CheckState.Checked
    return Qt.CheckState.Unchecked


def checkbox_tristate_to_val(check_state: Qt.CheckState) -> Union[bool, None]:
    """
    Converts a CheckState value to a boolean value or None.
    """
    if check_state == Qt.CheckState.Checked:
        return True
    if check_state == Qt.CheckState.Unchecked:
        return False
    return None


def set_warning_style(widget: QWidget, level: int) -> None:
    """
    Sets the background and foreground colors of a widget according to a level from logging.
    """
    base_style_sheet = "background-color : {bg}; color : {fg}; border-radius: 4px;"
    if level == logging.DEBUG:
        widget.setStyleSheet(base_style_sheet.format(bg="#dddbdc", fg="black"))
    elif level == logging.INFO:
        widget.setStyleSheet(base_style_sheet.format(bg="#beebf5", fg="black"))
    elif level == logging.WARNING:
        widget.setStyleSheet(base_style_sheet.format(bg="#fdc5b6", fg="black"))
    elif level == logging.ERROR:
        widget.setStyleSheet(base_style_sheet.format(bg="#d68e99", fg="black"))
    elif level == logging.CRITICAL:
        widget.setStyleSheet(base_style_sheet.format(bg="#d68e99", fg="black"))
