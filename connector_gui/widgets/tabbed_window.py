import wx
import wx.aui


class TabbedWindow(wx.aui.AuiNotebook):

    def __init__(self, parent, size=(200, 200)):
        wx.aui.AuiNotebook.__init__(self, parent, -1, size=size, style=wx.BK_TOP)
