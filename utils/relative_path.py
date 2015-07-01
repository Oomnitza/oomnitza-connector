import os
import sys

"""
If we are running in a |PyInstaller| bundle, PyInstaller adds the attributes 'frozen' and '_MEIPASS' to the sys.
'frozen': It's used to learn the app is running "live" (from source) or "frozen" (part of bundle)
'_MEIPASS': It contains the path to the folder containing your script and any other files or folders bundled with it
"""

def relative_path(filename):
    """
    This is used to convert the path of the bundle data file with binary.
    :return
    """
    return os.path.join(getattr(sys, '_MEIPASS', os.path.abspath(".")), filename)


def relative_app_path(filename):
    """
    This is used to convert the path of the file in directory connector.
    :return
    """
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(application_path, filename)
