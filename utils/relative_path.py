import os
import sys


def relative_path(filename):
    """
    Dynamic file path depends on running in a PyInstaller bundle
    or normal Python environment
    """
    return os.path.join(getattr(sys, '_MEIPASS', os.path.abspath(".")), filename)


def relative_app_path(filename):
    # determine if application is a script file or frozen exe
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(application_path, filename)
