import wx

from connector_gui.widgets import frame

class App(wx.App):
    def __init__(self, redirect=True, filename=None,
                 use_best_visual=False, clear_sig_int=True, task_server=None):
        self.task_server = task_server
        wx.App.__init__(self, redirect, filename, use_best_visual, clear_sig_int)

    def OnInit(self):
        self.frame = frame.Frame(task_server=self.task_server)
        self.frame.Show(True)
        return True

    def get_frame(self):
        return self.frame
