"""
Test script to verify fancy mode caustics animation is working.
"""

import sys
from pathlib import Path
from qt_compat import QtCore, QtGui, QtWidgets
from water_caustics_widget import WaterCausticsWidget, FullWindowCausticsOverlay

class TestWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fancy Mode Test")
        self.resize(800, 600)

        # Create central widget
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        central.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        central.setAutoFillBackground(False)

        layout = QtWidgets.QVBoxLayout(central)

        # Add some test UI elements
        self.label = QtWidgets.QLabel("Fancy Mode Test - Watch for animated caustics in background")
        self.label.setStyleSheet("color: white; font-size: 16px;")
        layout.addWidget(self.label)

        # Add a white box to test contrast
        test_box = QtWidgets.QListWidget()
        test_box.addItem("Test Item 1")
        test_box.addItem("Test Item 2")
        test_box.setStyleSheet("""
            QListWidget {
                background-color: white;
                color: black;
                border: 2px solid blue;
            }
        """)
        layout.addWidget(test_box)

        layout.addStretch()

        # Status label
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("color: white; font-size: 12px;")
        layout.addWidget(self.status_label)

        # Create caustics overlay
        self.caustics_overlay = FullWindowCausticsOverlay(central)
        self.caustics_overlay.setGeometry(central.rect())
        self.caustics_overlay.lower()

        # Start animation immediately for testing
        print("Starting caustics animation...")
        self.caustics_overlay.start_animation()

        # Timer to check animation state
        self.check_timer = QtCore.QTimer()
        self.check_timer.timeout.connect(self.check_animation_state)
        self.check_timer.start(500)  # Check every 500ms

        self.frame_count = 0

    def check_animation_state(self):
        """Check if animation is running."""
        self.frame_count += 1

        caustics_widget = self.caustics_overlay.caustics
        is_timer_active = caustics_widget.timer.isActive()
        is_visible = caustics_widget.isVisible()
        overlay_visible = self.caustics_overlay.isVisible()

        status = f"Frame: {self.frame_count} | "
        status += f"Timer Active: {is_timer_active} | "
        status += f"Widget Visible: {is_visible} | "
        status += f"Overlay Visible: {overlay_visible}"

        self.status_label.setText(status)

        print(f"[Frame {self.frame_count}]")
        print(f"  Caustics timer active: {is_timer_active}")
        print(f"  Caustics widget visible: {is_visible}")
        print(f"  Caustics overlay visible: {overlay_visible}")
        print(f"  Caustics widget size: {caustics_widget.size()}")
        print(f"  Overlay size: {self.caustics_overlay.size()}")

        if self.frame_count > 20:  # Stop checking after 10 seconds
            self.check_timer.stop()
            print("\n=== FINAL DIAGNOSIS ===")
            if not is_timer_active:
                print("ERROR: Animation timer is not running!")
            if not is_visible:
                print("ERROR: Caustics widget is not visible!")
            if not overlay_visible:
                print("ERROR: Overlay is not visible!")
            if is_timer_active and is_visible and overlay_visible:
                print("SUCCESS: Animation should be running properly")

    def resizeEvent(self, event):
        """Update overlay on resize."""
        super().resizeEvent(event)
        central = self.centralWidget()
        if central:
            self.caustics_overlay.setGeometry(central.rect())
            self.caustics_overlay.lower()

def main():
    app = QtWidgets.QApplication(sys.argv)

    # Set dark background
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1a1a1a;
        }
        QWidget {
            background-color: transparent;
        }
    """)

    window = TestWindow()
    window.show()

    print("Test window opened. Check for:")
    print("1. Animated water caustics in background")
    print("2. White box should be opaque")
    print("3. Caustics should be moving/animating")
    print("\nMonitoring animation state...\n")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
