"""
GDS Preset Management
Handles saving/loading/managing GDS file presets.
"""

import json
from pathlib import Path
from typing import Dict, List

class GDSPresetManager:
    """Manages GDS file presets stored in a JSON file."""

    DEFAULT_PRESET_NAME = "[Default - Test.GDS]"
    DEFAULT_GDS_PATH = "Test.GDS"

    def __init__(self, presets_file: Path = None):
        if presets_file is None:
            import sys
            if getattr(sys, 'frozen', False):
                # Running as PyInstaller bundle - save next to .exe
                presets_file = Path(sys.executable).parent / "gds_presets.json"
            else:
                # Running as script - use project directory
                presets_file = Path(__file__).parent / "gds_presets.json"
        self.presets_file = presets_file
        self.presets: Dict[str, str] = {}  # name -> file_path
        self.load()

    def load(self):
        """Load presets from file."""
        # Always include default preset
        self.presets = {self.DEFAULT_PRESET_NAME: self.DEFAULT_GDS_PATH}

        if self.presets_file.exists():
            try:
                with open(self.presets_file, 'r') as f:
                    data = json.load(f)
                    # Merge loaded presets with default
                    for name, path in data.items():
                        if name != self.DEFAULT_PRESET_NAME:  # Don't override default
                            self.presets[name] = path
            except Exception as e:
                print(f"Warning: Could not load GDS presets: {e}")

    def save(self):
        """Save presets to file."""
        try:
            # Save all presets except the default one
            save_data = {name: path for name, path in self.presets.items()
                        if name != self.DEFAULT_PRESET_NAME}

            with open(self.presets_file, 'w') as f:
                json.dump(save_data, f, indent=2)
        except Exception as e:
            print(f"Error saving GDS presets: {e}")

    def get_preset_names(self) -> List[str]:
        """Get list of all preset names."""
        # Ensure default is always first
        names = [self.DEFAULT_PRESET_NAME]
        names.extend([name for name in sorted(self.presets.keys())
                     if name != self.DEFAULT_PRESET_NAME])
        return names

    def get_gds_path(self, preset_name: str) -> str:
        """Get GDS file path for a preset name."""
        return self.presets.get(preset_name, self.DEFAULT_GDS_PATH)

    def add_preset(self, name: str, gds_path: str) -> bool:
        """Add or update a preset. Returns True if successful."""
        if name == self.DEFAULT_PRESET_NAME:
            return False  # Cannot modify default

        if not name.strip():
            return False  # Empty name not allowed

        # Store the GDS file path
        self.presets[name] = gds_path
        self.save()
        return True

    def delete_preset(self, name: str) -> bool:
        """Delete a preset. Returns True if successful."""
        if name == self.DEFAULT_PRESET_NAME:
            return False  # Cannot delete default

        if name in self.presets:
            del self.presets[name]
            self.save()
            return True
        return False

    def rename_preset(self, old_name: str, new_name: str) -> bool:
        """Rename a preset. Returns True if successful."""
        if old_name == self.DEFAULT_PRESET_NAME or new_name == self.DEFAULT_PRESET_NAME:
            return False  # Cannot rename default

        if old_name not in self.presets or not new_name.strip():
            return False

        if new_name in self.presets and new_name != old_name:
            return False  # Name already exists

        self.presets[new_name] = self.presets.pop(old_name)
        self.save()
        return True
