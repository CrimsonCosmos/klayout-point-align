# -*- mode: python ; coding: utf-8 -*-
# Alternative spec for ONE-FOLDER distribution (faster startup)
from PyInstaller.utils.hooks import collect_all

datas = [('Test_with_img.lys', '.'), ('Test.GDS', '.'), ('point_align_batch_runner_gui.py', '.'), ('example_points_for_manual.png', '.')]
binaries = []
hiddenimports = ['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
                 'shiboken6', 'point_align_batch_runner_gui',
                 'numpy._core._multiarray_umath', 'cv2', 'runpy']

# Only collect what we need
tmp_ret = collect_all('shiboken6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('numpy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('klayout_point_align')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Exclude all PySide6 modules we don't use
excludes = [
    'PyQt5', 'PyQt6',
    # PySide6 modules we don't need
    'PySide6.Qt3DAnimation', 'PySide6.Qt3DCore', 'PySide6.Qt3DExtras',
    'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DRender',
    'PySide6.QtAsyncio', 'PySide6.QtAxContainer', 'PySide6.QtBluetooth',
    'PySide6.QtCharts', 'PySide6.QtConcurrent', 'PySide6.QtDataVisualization',
    'PySide6.QtDBus', 'PySide6.QtDesigner', 'PySide6.QtGraphs',
    'PySide6.QtGraphsWidgets', 'PySide6.QtHelp', 'PySide6.QtHttpServer',
    'PySide6.QtLocation', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
    'PySide6.QtNetwork', 'PySide6.QtNetworkAuth', 'PySide6.QtNfc',
    'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets', 'PySide6.QtPdf',
    'PySide6.QtPdfWidgets', 'PySide6.QtPositioning', 'PySide6.QtPrintSupport',
    'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuick3D',
    'PySide6.QtQuickControls2', 'PySide6.QtQuickTest', 'PySide6.QtQuickWidgets',
    'PySide6.QtRemoteObjects', 'PySide6.QtScxml', 'PySide6.QtSensors',
    'PySide6.QtSerialBus', 'PySide6.QtSerialPort', 'PySide6.QtSpatialAudio',
    'PySide6.QtSql', 'PySide6.QtStateMachine', 'PySide6.QtSvg',
    'PySide6.QtSvgWidgets', 'PySide6.QtTest', 'PySide6.QtTextToSpeech',
    'PySide6.QtUiTools', 'PySide6.QtWebChannel', 'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineQuick', 'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebSockets', 'PySide6.QtWebView', 'PySide6.QtXml',
    # Numpy test modules we don't need
    'numpy.tests', 'numpy.testing', 'numpy.f2py.tests',
]

a = Analysis(
    ['align_gui_aqua_qt.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
    win_no_prefer_redirects=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],  # ← Empty! Don't bundle binaries into .exe
    exclude_binaries=True,  # ← Keep DLLs separate
    name='PointAlign',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)

# Build separate console runner for spawning subprocesses
console_a = Analysis(
    ['console_runner.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
    win_no_prefer_redirects=False,
)
console_pyz = PYZ(console_a.pure)

console_exe = EXE(
    console_pyz,
    console_a.scripts,
    [],
    exclude_binaries=True,
    name='console_runner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # ← Console mode for subprocess runner
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Create a COLLECT to bundle into folder
coll = COLLECT(
    exe,
    console_exe,  # Add console runner to output
    a.binaries,
    a.datas,
    console_a.binaries,
    console_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PointAlign_v1.1',
)
