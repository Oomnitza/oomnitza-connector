import wx

class TabbedPanel(wx.Panel):

    def __init__(self, parent, fg_color="Black"):
        wx.Panel.__init__(self, parent, -1)

        self.SetForegroundColour(fg_color)


