
"""qt_compat.py — unified Qt import for PySide6 or PyQt6 with robust shims.

Use everywhere:
    from qt_compat import QtCore, QtGui, QtWidgets, Signal, Slot
"""

# Prefer PySide6; fall back to PyQt6.
try:
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore
    USING_PYSIDE6 = True
    USING_PYQT6 = False
    QT_BACKEND = "PySide6"
    Signal = QtCore.Signal
    Slot = QtCore.Slot
except ModuleNotFoundError:
    from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore
    USING_PYSIDE6 = False
    USING_PYQT6 = True
    QT_BACKEND = "PyQt6"

    # ---- Signals/Slots ----
    try:
        from PyQt6.QtCore import pyqtSignal as _pyqtSignal, pyqtSlot as _pyqtSlot  # type: ignore
        Signal = _pyqtSignal
        Slot = _pyqtSlot
        QtCore.Signal = _pyqtSignal          # type: ignore[attr-defined]
        QtCore.Slot = _pyqtSlot              # type: ignore[attr-defined]
    except Exception:
        pass

    # ---- QtCore.Qt enums that moved to nested enums ----
    try:
        _Qt = QtCore.Qt
        # Alignment
        if not hasattr(_Qt, 'AlignCenter'):
            _Qt.AlignCenter = _Qt.AlignmentFlag.AlignCenter
            _Qt.AlignLeft = _Qt.AlignmentFlag.AlignLeft
            _Qt.AlignRight = _Qt.AlignmentFlag.AlignRight
            _Qt.AlignTop = _Qt.AlignmentFlag.AlignTop
            _Qt.AlignBottom = _Qt.AlignmentFlag.AlignBottom
            _Qt.AlignVCenter = _Qt.AlignmentFlag.AlignVCenter
            _Qt.AlignHCenter = _Qt.AlignmentFlag.AlignHCenter

        # Orientation
        if not hasattr(_Qt, 'Horizontal'):
            _Qt.Horizontal = _Qt.Orientation.Horizontal
            _Qt.Vertical = _Qt.Orientation.Vertical

        # Context menu policy
        if not hasattr(_Qt, 'CustomContextMenu'):
            _Qt.CustomContextMenu = _Qt.ContextMenuPolicy.CustomContextMenu
            _Qt.NoContextMenu = _Qt.ContextMenuPolicy.NoContextMenu

        # Drop action (used for drag/drop lists)
        if not hasattr(_Qt, 'MoveAction'):
            _Qt.MoveAction = _Qt.DropAction.MoveAction

        # Mouse buttons
        if not hasattr(_Qt, 'LeftButton'):
            _Qt.LeftButton = _Qt.MouseButton.LeftButton
            _Qt.RightButton = _Qt.MouseButton.RightButton
            _Qt.MiddleButton = _Qt.MouseButton.MiddleButton
            _Qt.NoButton = _Qt.MouseButton.NoButton

        # Keyboard keys (used by picker)
        if not hasattr(_Qt, 'Key_Backspace'):
            _Qt.Key_Backspace = _Qt.Key.Key_Backspace
            _Qt.Key_S = _Qt.Key.Key_S
            _Qt.Key_Q = _Qt.Key.Key_Q
            _Qt.Key_Escape = _Qt.Key.Key_Escape
            _Qt.Key_F = _Qt.Key.Key_F
            _Qt.Key_R = _Qt.Key.Key_R
            _Qt.Key_Space = _Qt.Key.Key_Space

        # Cursor shapes
        if not hasattr(_Qt, 'PointingHandCursor'):
            _Qt.PointingHandCursor = _Qt.CursorShape.PointingHandCursor
            _Qt.CrossCursor = _Qt.CursorShape.CrossCursor
            _Qt.ClosedHandCursor = _Qt.CursorShape.ClosedHandCursor

        # Application attributes (these were removed in Qt6, skip if not available)
        if not hasattr(_Qt, 'AA_EnableHighDpiScaling'):
            if hasattr(_Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
                _Qt.AA_EnableHighDpiScaling = _Qt.ApplicationAttribute.AA_EnableHighDpiScaling
        if not hasattr(_Qt, 'AA_UseHighDpiPixmaps'):
            if hasattr(_Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
                _Qt.AA_UseHighDpiPixmaps = _Qt.ApplicationAttribute.AA_UseHighDpiPixmaps

        # Window flags / types
        if not hasattr(_Qt, 'FramelessWindowHint'):
            _Qt.FramelessWindowHint = _Qt.WindowType.FramelessWindowHint

        # Aspect ratio
        if not hasattr(_Qt, 'KeepAspectRatio'):
            _Qt.KeepAspectRatio = _Qt.AspectRatioMode.KeepAspectRatio

        # Transformation mode (for scaling pixmaps)
        if not hasattr(_Qt, 'SmoothTransformation'):
            _Qt.SmoothTransformation = _Qt.TransformationMode.SmoothTransformation
        if not hasattr(_Qt, 'FastTransformation'):
            _Qt.FastTransformation = _Qt.TransformationMode.FastTransformation

        # Item data roles (common subset)
        if not hasattr(_Qt, 'DisplayRole'):
            _Qt.DisplayRole = _Qt.ItemDataRole.DisplayRole
        if not hasattr(_Qt, 'DecorationRole'):
            _Qt.DecorationRole = _Qt.ItemDataRole.DecorationRole
        if not hasattr(_Qt, 'EditRole'):
            _Qt.EditRole = _Qt.ItemDataRole.EditRole
        if not hasattr(_Qt, 'ToolTipRole'):
            _Qt.ToolTipRole = _Qt.ItemDataRole.ToolTipRole
        if not hasattr(_Qt, 'UserRole'):
            _Qt.UserRole = _Qt.ItemDataRole.UserRole

        # Widget attribute
        if not hasattr(_Qt, 'WA_TransparentForMouseEvents'):
            _Qt.WA_TransparentForMouseEvents = _Qt.WidgetAttribute.WA_TransparentForMouseEvents

        # Window type for tooltips
        if not hasattr(_Qt, 'ToolTip'):
            _Qt.ToolTip = _Qt.WindowType.ToolTip
    except Exception:
        pass

    # ---- QtWidgets class enum shims ----
    try:
        _QF = QtWidgets.QFrame
        _QF.StyledPanel = getattr(_QF, 'StyledPanel', _QF.Shape.StyledPanel)
        _QF.NoFrame = getattr(_QF, 'NoFrame', _QF.Shape.NoFrame)
        _QF.Panel = getattr(_QF, 'Panel', _QF.Shape.Panel)
        _QF.Box = getattr(_QF, 'Box', _QF.Shape.Box)
        _QF.HLine = getattr(_QF, 'HLine', _QF.Shape.HLine)
        _QF.VLine = getattr(_QF, 'VLine', _QF.Shape.VLine)
        _QF.WinPanel = getattr(_QF, 'WinPanel', _QF.Shape.WinPanel)
        _QF.Plain = getattr(_QF, 'Plain', _QF.Shadow.Plain)
        _QF.Raised = getattr(_QF, 'Raised', _QF.Shadow.Raised)
        _QF.Sunken = getattr(_QF, 'Sunken', _QF.Shadow.Sunken)
    except Exception:
        pass

    try:
        _AIV = QtWidgets.QAbstractItemView
        _AIV.SingleSelection = getattr(_AIV, 'SingleSelection', _AIV.SelectionMode.SingleSelection)
        _AIV.ExtendedSelection = getattr(_AIV, 'ExtendedSelection', _AIV.SelectionMode.ExtendedSelection)
        _AIV.NoEditTriggers = getattr(_AIV, 'NoEditTriggers', _AIV.EditTrigger.NoEditTriggers)
        _AIV.SelectedClicked = getattr(_AIV, 'SelectedClicked', _AIV.EditTrigger.SelectedClicked) if hasattr(_AIV, 'EditTrigger') else getattr(_AIV, 'SelectedClicked', None)
        _AIV.SelectRows = getattr(_AIV, 'SelectRows', _AIV.SelectionBehavior.SelectRows)
        _AIV.SelectItems = getattr(_AIV, 'SelectItems', _AIV.SelectionBehavior.SelectItems)
        _AIV.DragDrop = getattr(_AIV, 'DragDrop', _AIV.DragDropMode.DragDrop)
        _AIV.DragOnly = getattr(_AIV, 'DragOnly', _AIV.DragDropMode.DragOnly)
        _AIV.DropOnly = getattr(_AIV, 'DropOnly', _AIV.DragDropMode.DropOnly)
        _AIV.NoDragDrop = getattr(_AIV, 'NoDragDrop', _AIV.DragDropMode.NoDragDrop)
    except Exception:
        pass

    try:
        _HV = QtWidgets.QHeaderView
        _HV.Stretch = getattr(_HV, 'Stretch', _HV.ResizeMode.Stretch)
        _HV.ResizeToContents = getattr(_HV, 'ResizeToContents', _HV.ResizeMode.ResizeToContents)
        _HV.Interactive = getattr(_HV, 'Interactive', _HV.ResizeMode.Interactive)
    except Exception:
        pass

    try:
        _FD = QtWidgets.QFileDialog
        _FD.DontUseNativeDialog = getattr(_FD, 'DontUseNativeDialog', _FD.Option.DontUseNativeDialog)
        _FD.ReadOnly = getattr(_FD, 'ReadOnly', _FD.Option.ReadOnly)
    except Exception:
        pass

    try:
        _TW = QtWidgets.QTabWidget
        _TW.North = getattr(_TW, 'North', _TW.TabPosition.North)
        _TW.South = getattr(_TW, 'South', _TW.TabPosition.South)
        _TW.East = getattr(_TW, 'East', _TW.TabPosition.East)
        _TW.West = getattr(_TW, 'West', _TW.TabPosition.West)
    except Exception:
        pass

    try:
        _SP = QtWidgets.QSizePolicy
        _SP.Fixed = getattr(_SP, 'Fixed', _SP.Policy.Fixed)
        _SP.Minimum = getattr(_SP, 'Minimum', _SP.Policy.Minimum)
        _SP.Maximum = getattr(_SP, 'Maximum', _SP.Policy.Maximum)
        _SP.Preferred = getattr(_SP, 'Preferred', _SP.Policy.Preferred)
        _SP.Expanding = getattr(_SP, 'Expanding', _SP.Policy.Expanding)
        _SP.MinimumExpanding = getattr(_SP, 'MinimumExpanding', _SP.Policy.MinimumExpanding)
        _SP.Ignored = getattr(_SP, 'Ignored', _SP.Policy.Ignored)
    except Exception:
        pass

    try:
        _CB = QtWidgets.QComboBox
        _CB.NoInsert = getattr(_CB, 'NoInsert', _CB.InsertPolicy.NoInsert)
        _CB.InsertAtTop = getattr(_CB, 'InsertAtTop', _CB.InsertPolicy.InsertAtTop)
        _CB.InsertAtBottom = getattr(_CB, 'InsertAtBottom', _CB.InsertPolicy.InsertAtBottom)
        _CB.InsertAlphabetically = getattr(_CB, 'InsertAlphabetically', _CB.InsertPolicy.InsertAlphabetically)
    except Exception:
        pass

    try:
        _LE = QtWidgets.QLineEdit
        _LE.Normal = getattr(_LE, 'Normal', _LE.EchoMode.Normal)
        _LE.NoEcho = getattr(_LE, 'NoEcho', _LE.EchoMode.NoEcho)
        _LE.Password = getattr(_LE, 'Password', _LE.EchoMode.Password)
        _LE.PasswordEchoOnEdit = getattr(_LE, 'PasswordEchoOnEdit', _LE.EchoMode.PasswordEchoOnEdit)
    except Exception:
        pass

    try:
        _ASA = QtWidgets.QAbstractScrollArea
        _ASA.AdjustIgnored = getattr(_ASA, 'AdjustIgnored', _ASA.SizeAdjustPolicy.AdjustIgnored)
        _ASA.AdjustToContents = getattr(_ASA, 'AdjustToContents', _ASA.SizeAdjustPolicy.AdjustToContents)
        _ASA.AdjustToContentsOnFirstShow = getattr(_ASA, 'AdjustToContentsOnFirstShow', _ASA.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
    except Exception:
        pass

    # ---- Qt ScrollBarPolicy compatibility ----
    try:
        _Qt = QtCore.Qt
        if not hasattr(_Qt, 'ScrollBarAlwaysOff'):
            _Qt.ScrollBarAlwaysOff = _Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        if not hasattr(_Qt, 'ScrollBarAlwaysOn'):
            _Qt.ScrollBarAlwaysOn = _Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        if not hasattr(_Qt, 'ScrollBarAsNeeded'):
            _Qt.ScrollBarAsNeeded = _Qt.ScrollBarPolicy.ScrollBarAsNeeded
    except Exception:
        pass

    # ---- Qt CheckState compatibility ----
    try:
        _Qt = QtCore.Qt
        if not hasattr(_Qt, 'Checked'):
            _Qt.Checked = _Qt.CheckState.Checked
        if not hasattr(_Qt, 'Unchecked'):
            _Qt.Unchecked = _Qt.CheckState.Unchecked
        if not hasattr(_Qt, 'PartiallyChecked'):
            _Qt.PartiallyChecked = _Qt.CheckState.PartiallyChecked
    except Exception:
        pass

    # ---- Qt WindowModality compatibility ----
    try:
        _Qt = QtCore.Qt
        if not hasattr(_Qt, 'ApplicationModal'):
            _Qt.ApplicationModal = _Qt.WindowModality.ApplicationModal
        if not hasattr(_Qt, 'WindowModal'):
            _Qt.WindowModal = _Qt.WindowModality.WindowModal
        if not hasattr(_Qt, 'NonModal'):
            _Qt.NonModal = _Qt.WindowModality.NonModal
    except Exception:
        pass

    try:
        _FL = QtWidgets.QFormLayout
        _FL.AllNonFixedFieldsGrow = getattr(_FL, 'AllNonFixedFieldsGrow', _FL.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        _FL.ExpandingFieldsGrow = getattr(_FL, 'ExpandingFieldsGrow', _FL.FieldGrowthPolicy.ExpandingFieldsGrow)
        _FL.FieldsStayAtSizeHint = getattr(_FL, 'FieldsStayAtSizeHint', _FL.FieldGrowthPolicy.FieldsStayAtSizeHint)
    except Exception:
        pass

    try:
        _GV = QtWidgets.QGraphicsView
        _GV.AnchorUnderMouse = getattr(_GV, 'AnchorUnderMouse', _GV.ViewportAnchor.AnchorUnderMouse)
        _GV.AnchorViewCenter = getattr(_GV, 'AnchorViewCenter', _GV.ViewportAnchor.AnchorViewCenter)
        _GV.NoAnchor = getattr(_GV, 'NoAnchor', _GV.ViewportAnchor.NoAnchor)
        _GV.SmartViewportUpdate = getattr(_GV, 'SmartViewportUpdate', _GV.ViewportUpdateMode.SmartViewportUpdate)
        _GV.FullViewportUpdate = getattr(_GV, 'FullViewportUpdate', _GV.ViewportUpdateMode.FullViewportUpdate)
        _GV.NoDrag = getattr(_GV, 'NoDrag', _GV.DragMode.NoDrag)
        _GV.ScrollHandDrag = getattr(_GV, 'ScrollHandDrag', _GV.DragMode.ScrollHandDrag)
        _GV.RubberBandDrag = getattr(_GV, 'RubberBandDrag', _GV.DragMode.RubberBandDrag)
    except Exception:
        pass

    # ---- QtGui QFontDatabase compatibility ----
    # In PyQt6, QFontDatabase methods are static; in PySide6 they're instance methods
    # Wrap to support both patterns without calling during import
    if USING_PYQT6:
        try:
            _OrigQFontDatabase = QtGui.QFontDatabase

            class _QFontDatabaseWrapper:
                def __init__(self):
                    pass

                def families(self):
                    # PyQt6: call as static method
                    return _OrigQFontDatabase.families()

                @staticmethod
                def families_static():
                    return _OrigQFontDatabase.families()

            QtGui.QFontDatabase = _QFontDatabaseWrapper  # type: ignore[misc]
        except Exception:
            pass

    # ---- QtGui class enum shims ----
    try:
        _QKS = QtGui.QKeySequence
        _QKS.Save = getattr(_QKS, 'Save', _QKS.StandardKey.Save)
        _QKS.Open = getattr(_QKS, 'Open', _QKS.StandardKey.Open)
        _QKS.New = getattr(_QKS, 'New', _QKS.StandardKey.New)
        _QKS.Quit = getattr(_QKS, 'Quit', _QKS.StandardKey.Quit)
        _QKS.Copy = getattr(_QKS, 'Copy', _QKS.StandardKey.Copy)
        _QKS.Cut = getattr(_QKS, 'Cut', _QKS.StandardKey.Cut)
        _QKS.Paste = getattr(_QKS, 'Paste', _QKS.StandardKey.Paste)
        _QKS.SelectAll = getattr(_QKS, 'SelectAll', _QKS.StandardKey.SelectAll)
    except Exception:
        pass

    try:
        _QP = QtGui.QPainter
        _QP.Antialiasing = getattr(_QP, 'Antialiasing', _QP.RenderHint.Antialiasing)
        _QP.SmoothPixmapTransform = getattr(_QP, 'SmoothPixmapTransform', _QP.RenderHint.SmoothPixmapTransform)
    except Exception:
        pass

    try:
        _MB = QtWidgets.QMessageBox
        _MB.Yes = getattr(_MB, 'Yes', _MB.StandardButton.Yes)
        _MB.No = getattr(_MB, 'No', _MB.StandardButton.No)
        _MB.Ok = getattr(_MB, 'Ok', _MB.StandardButton.Ok)
        _MB.Cancel = getattr(_MB, 'Cancel', _MB.StandardButton.Cancel)
        _MB.Retry = getattr(_MB, 'Retry', _MB.StandardButton.Retry) if hasattr(_MB, 'StandardButton') else getattr(_MB, 'Retry', None)
        _MB.Warning = getattr(_MB, 'Warning', _MB.Icon.Warning) if hasattr(_MB, 'Icon') else getattr(_MB, 'Warning', None)
        _MB.Information = getattr(_MB, 'Information', _MB.Icon.Information) if hasattr(_MB, 'Icon') else getattr(_MB, 'Information', None)
        _MB.Critical = getattr(_MB, 'Critical', _MB.Icon.Critical) if hasattr(_MB, 'Icon') else getattr(_MB, 'Critical', None)
    except Exception:
        pass
