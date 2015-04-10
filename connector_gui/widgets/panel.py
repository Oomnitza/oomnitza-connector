import wx


class Panel(wx.Panel):

    def __init__(self, parent=None, size=(200, 200), fg_color="Black", bg_color="White"):
        wx.Panel.__init__(self, parent=parent, id=-1, size=size)

        self.SetForegroundColour(fg_color)
        self.SetBackgroundColour(bg_color)
