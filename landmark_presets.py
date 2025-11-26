"""
Landmark Preset Management
Handles saving/loading/managing GDS landmark coordinate presets.
"""

import json
from pathlib import Path
from typing import Dict, List

class LandmarkPresetManager:
    """Manages landmark presets stored in a JSON file."""

    DEFAULT_PRESET_NAME = "[Default]"
    DEFAULT_COORDINATES = "(-50,60),(70,60),(-50,-60),(70,-60)"

    def __init__(self, presets_file: Path = None):
        if presets_file is None:
            import sys
            if getattr(sys, 'frozen', False):
                # Running as PyInstaller bundle - save next to .exe
                presets_file = Path(sys.executable).parent / "landmark_presets.json"
            else:
                # Running as script - use project directory
                presets_file = Path(__file__).parent / "landmark_presets.json"
        self.presets_file = presets_file
        self.presets: Dict[str, str] = {}
        self.load()

    def load(self):
        """Load presets from file."""
        # Always include default preset
        self.presets = {self.DEFAULT_PRESET_NAME: self.DEFAULT_COORDINATES}

        if self.presets_file.exists():
            try:
                with open(self.presets_file, 'r') as f:
                    data = json.load(f)
                    # Merge loaded presets with default
                    for name, coords in data.items():
                        if name != self.DEFAULT_PRESET_NAME:  # Don't override default
                            self.presets[name] = coords
            except Exception as e:
                print(f"Warning: Could not load landmark presets: {e}")

    def save(self):
        """Save presets to file."""
        try:
            # Save all presets except the default one
            save_data = {name: coords for name, coords in self.presets.items()
                        if name != self.DEFAULT_PRESET_NAME}

            with open(self.presets_file, 'w') as f:
                json.dump(save_data, f, indent=2)
        except Exception as e:
            print(f"Error saving landmark presets: {e}")

    def get_preset_names(self) -> List[str]:
        """Get list of all preset names."""
        # Ensure default is always first
        names = [self.DEFAULT_PRESET_NAME]
        names.extend([name for name in sorted(self.presets.keys())
                     if name != self.DEFAULT_PRESET_NAME])
        return names

    def get_coordinates(self, preset_name: str) -> str:
        """Get coordinates for a preset name."""
        return self.presets.get(preset_name, self.DEFAULT_COORDINATES)

    def add_preset(self, name: str, coordinates: str) -> bool:
        """Add or update a preset. Returns True if successful."""
        if name == self.DEFAULT_PRESET_NAME:
            return False  # Cannot modify default

        if not name.strip():
            return False  # Empty name not allowed

        # Validate coordinate format
        if not self.validate_coordinates(coordinates):
            return False

        self.presets[name] = coordinates
        self.save()
        return True

    @staticmethod
    def validate_coordinates(coords: str) -> bool:
        """
        Validate that coordinates are in the correct format.
        Expected: (x1,y1),(x2,y2),(x3,y3),(x4,y4)
        Returns True if valid, False otherwise.
        """
        import re

        # Normalize Unicode minus signs to ASCII hyphen-minus
        # U+2212 (MINUS SIGN), U+2013 (EN DASH), U+2014 (EM DASH)
        coords = coords.replace('\u2212', '-')  # Unicode minus sign
        coords = coords.replace('\u2013', '-')  # En dash
        coords = coords.replace('\u2014', '-')  # Em dash
        coords = coords.replace('−', '-')      # Another minus variant

        # Remove all whitespace for easier parsing
        coords_clean = coords.replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", "")

        # Pattern: exactly 4 coordinate pairs like (num,num),(num,num),(num,num),(num,num)
        # Numbers can be integers or floats, positive or negative
        # Allow formats like: 50, -50, 50.5, -50.5, .5, -.5
        number_pattern = r'[-+]?(?:\d+\.?\d*|\d*\.\d+)'
        pattern = rf'^\({number_pattern},{number_pattern}\),\({number_pattern},{number_pattern}\),\({number_pattern},{number_pattern}\),\({number_pattern},{number_pattern}\)$'

        return bool(re.match(pattern, coords_clean))

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
