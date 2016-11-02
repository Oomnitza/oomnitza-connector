import wx

from utils.relative_path import relative_path


class DataViewer(wx.TreeCtrl):

    def __init__(self, parent=None, size=(200, 200), mappings={},
                 connectors={}, fg_color="Black", bg_color="White"):
        wx.TreeCtrl.__init__(self, parent=parent, id=-1, size=size,
                             style=wx.TR_HAS_BUTTONS |
                                   wx.TR_FULL_ROW_HIGHLIGHT |
                                   wx.TR_HIDE_ROOT | wx.NO_BORDER)

        self.SetForegroundColour(fg_color)
        self.SetBackgroundColour(bg_color)
        self.tree_nodes_mappings = {}

        icon_list = wx.ImageList(16, 16)
        self.enabled_icon_id = icon_list.Add(wx.Bitmap(relative_path('connector_gui/images/enabled.png')))
        self.scheduled_icon_id = icon_list.Add(wx.Bitmap(relative_path('connector_gui/images/scheduled.png')))
        self.disabled_icon_id = icon_list.Add(wx.Bitmap(relative_path('connector_gui/images/disabled.png')))
        self.expanded_icon_id = icon_list.Add(wx.Bitmap(relative_path('connector_gui/images/expanded.png')))
        self.collapsed_icon_id = icon_list.Add(wx.Bitmap(relative_path('connector_gui/images/collapsed.png')))
        self.AssignImageList(icon_list)

        self.root = self.AddRoot('')
        self.connectors = self.AppendItem(self.root, 'Connectors')
        self.tree_nodes_mappings['connectors'] = self.connectors
        self.SetFocusedItem(self.connectors)
        self.SetItemImage(self.connectors, self.expanded_icon_id,
                          wx.TreeItemIcon_Normal)
        self.oomnitza = self.AppendItem(self.root, 'Oomnitza Connection')
        self.tree_nodes_mappings['oomnitza connection'] = self.oomnitza

        for connector in sorted(connectors.keys()):
            if 'enable' not in connectors[connector]:
                # Don't display non-connector sections in the tree
                continue

            if connector in mappings:
                item = self.AppendItem(self.connectors, mappings[connector])
                self.tree_nodes_mappings[mappings[connector].lower()] = item
            else:
                item = self.AppendItem(self.connectors, connector)
                self.tree_nodes_mappings[connector.lower()] = item

            if 'enable' in connectors[connector] and \
                            connectors[connector]['enable'].lower() == 'true':
                self.SetItemImage(item, self.enabled_icon_id,
                                  wx.TreeItemIcon_Normal)
            else:
                self.SetItemImage(item, self.disabled_icon_id,
                                  wx.TreeItemIcon_Normal)

        self.ExpandAll()
        self.Bind(wx.EVT_TREE_ITEM_COLLAPSED, self.collapse_tree)
        self.Bind(wx.EVT_TREE_ITEM_EXPANDED, self.expand_tree)

    def collapse_tree(self, event):
        self.SetItemImage(self.connectors, self.collapsed_icon_id,
                          wx.TreeItemIcon_Normal)

    def expand_tree(self, event):
        self.SetItemImage(self.connectors, self.expanded_icon_id,
                          wx.TreeItemIcon_Normal)

    def update_status(self, config):
        child, cookie = self.GetFirstChild(self.connectors)
        while child.IsOk():
            if config[self.GetItemText(child).lower()]['enable'] == 'True':
                self.SetItemImage(child, self.enabled_icon_id, wx.TreeItemIcon_Normal)
            else:
                self.SetItemImage(child, self.disabled_icon_id, wx.TreeItemIcon_Normal)
            child, cookie = self.GetNextChild(self.connectors, cookie)

    def set_focused_item(self, item_label):
        self.SetFocusedItem(self.get_item_by_label(item_label))

    def get_item_by_label(self, search_label):
        return self.tree_nodes_mappings[search_label]



