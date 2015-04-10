import wx


class ListBox(wx.ListBox):

    def __init__(self, parent=None, size=(220, 120)):
        wx.ListBox.__init__(self, parent, -1, size=size)
        self.add_btn = wx.Button(parent, -1, "Add")
        self.del_btn = wx.Button(parent, -1, "Delete")
        self.rename_btn = wx.Button(parent, -1, "Rename")
        self.clear_btn = wx.Button(parent, -1, "Clear")

    def get_add_btn(self):
        return self.add_btn

    def get_del_btn(self):
        return self.del_btn

    def get_rename_btn(self):
        return self.rename_btn

    def get_clear_btn(self):
        return self.clear_btn