import wx
import wx.lib.mixins.listctrl


class EditableListCtrl(wx.ListCtrl, wx.lib.mixins.listctrl.TextEditMixin):
    def __init__(self, parent, ID=wx.ID_ANY, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0):
        wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
        wx.lib.mixins.listctrl.TextEditMixin.__init__(self)

class ListCtrl(wx.ListCtrl):

    def __init__(self, parent, title, data):
        self.index = 0
        self.item = EditableListCtrl(parent, -1, size=(220, 120),
                                     style=wx.LC_REPORT | wx.LC_NO_HEADER)
        self.add_btn = wx.Button(parent, -1, "Add")
        self.item.InsertColumn(0, 'Key', width=150)
        self.item.InsertColumn(1, 'Value', width=150)

        for key in data:
            index = self.item.InsertStringItem(self.index, key)
            self.item.SetStringItem(index, 1, data[key])
            self.index += 1

    def get_add_btn(self):
        return self.add_btn
