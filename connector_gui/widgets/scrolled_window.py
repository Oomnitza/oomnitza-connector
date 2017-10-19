import wx


class ScrolledWindow(wx.PyScrolledWindow):

    def __init__(self, parent, size, fg_color, bg_color):
        wx.PyScrolledWindow.__init__(self, parent=parent)

        self.SetMinSize(size)
        self.SetForegroundColour(fg_color)
        self.SetBackgroundColour(bg_color)
