import wx


class Button(wx.Button):
    def __init__(self, parent=None, label="", size=(80, 25)):
        wx.Button.__init__(self, parent, -1, label, size=size)

    def update(self, changed):
        if not changed:
            self.Enable()
        else:
            self.Disable()
