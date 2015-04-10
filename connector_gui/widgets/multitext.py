import wx
import platform


class MultiText(wx.TextCtrl):

    def __init__(self, parent=None, size=(200, 200), fg_color="Black",
                 bg_color="White"):
        wx.TextCtrl.__init__(self, parent, -1, size=size,
                             style=wx.TE_MULTILINE|wx.BORDER_NONE | wx.TE_RICH)
        self.SetBackgroundColour(bg_color)

        if platform.system() in ["Darwin", "Linux"]:
            self.Disable()

        self.SetValue("Update Info: There is no log.")
        self.SetStyle(0, self.GetLineLength(0), wx.TextAttr(fg_color))