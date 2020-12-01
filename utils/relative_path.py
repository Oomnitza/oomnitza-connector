import os


def relative_app_path(filename):
    """
    This is used to convert the path of the file in directory connector.
    :return
    """
    application_path = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(application_path, filename)
