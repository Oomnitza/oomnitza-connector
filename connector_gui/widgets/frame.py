import wx


class Frame(wx.Frame):

    def __init__(self, parent=None, id=-1, title="", size=(500, 300),
                 fg_color="Black", bg_color="White", task_server=None):
        self.task_server = task_server
        wx.Frame.__init__(self, parent=parent, id=id, title=title, size=size)

    def set_title(self, title):
        self.SetName(title)

    def set_size(self, size):
        self.SetSize(size)

    def set_background_color(self, bg_color):
        self.SetBackgroundColour(bg_color)

    def set_foreground_color(self, fg_color):
        self.SetForegroundColour(fg_color)


