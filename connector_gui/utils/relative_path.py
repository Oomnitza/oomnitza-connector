import os
import sys

def relative_path(filename):
    """
    Dynamic file path depends on running in a PyInstaller bundle
    or normal Python environment
    """
    return os.path.join(getattr(sys, '_MEIPASS', os.path.abspath(".")), filename)
