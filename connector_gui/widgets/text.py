import wx


class Text(wx.TextCtrl):
    def __init__(self, parent, value, safe_mode=False):
        if safe_mode:
            wx.TextCtrl.__init__(self, parent, -1, size=(220, -1),
                                 style=wx.TE_PASSWORD | wx.TE_RICH)
        else:
            wx.TextCtrl.__init__(self, parent, -1, size=(220, -1),
                                 style=wx.TE_RICH)
        self.SetValue(value)