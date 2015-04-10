import wx


class LoginDialog(wx.Dialog):

	def __init__(self):
		wx.Dialog.__init__(self, None, size=(300, 215), title="Credential")

		self.sizer = wx.BoxSizer(wx.VERTICAL)

		top_panel = wx.Panel(self, -1)
		top_panel.SetBackgroundColour('#FFFFFF')
		bottom_panel = wx.Panel(self, -1)
		bottom_panel.SetBackgroundColour('#E8E8E8')

		top_sizer = wx.GridBagSizer(5, 5)
		title_label = wx.StaticText(top_panel, label="Enter Username and Password")
		title_label.SetForegroundColour("#3366CC")
		title_font = wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.BOLD)
		title_label.SetFont(title_font)
		description_label = wx.StaticText(top_panel, label="Enter the name and password of\nadministrator account.")
		user_label = wx.StaticText(top_panel, label="Username")
		self.user_text = wx.TextCtrl(top_panel, size=(200, -1))
		password_label = wx.StaticText(top_panel, label="Password")
		self.password_text = wx.TextCtrl(top_panel, size=(200, -1), style=wx.TE_PASSWORD)
		password_text_font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD)
		self.password_text.SetFont(password_text_font)
		top_sizer.Add(title_label, pos=(0, 0), span=(1, 2), flag=wx.LEFT | wx.TOP, border=15)
		top_sizer.Add(description_label, pos=(1, 0), span=(1, 2), flag=wx.LEFT, border=15)
		top_sizer.Add(user_label, pos=(2, 0), flag=wx.LEFT, border=15)
		top_sizer.Add(self.user_text, pos=(2, 1))
		top_sizer.Add(password_label, pos=(3, 0), flag=wx.LEFT, border=15)
		top_sizer.Add(self.password_text, pos=(3, 1))

		bottom_sizer = wx.GridBagSizer(5, 5)
		ok_btn = wx.Button(bottom_panel, wx.ID_OK, size=(65, 25))
		cancel_btn = wx.Button(bottom_panel, wx.ID_CANCEL, size=(65, 25))
		bottom_sizer.Add(ok_btn, pos=(0, 10), flag=wx.TOP | wx.BOTTOM, border=10)
		bottom_sizer.Add(cancel_btn, pos=(0, 11), flag=wx.TOP | wx.BOTTOM, border=10)

		self.sizer.Add(top_panel, 1, wx.EXPAND)
		self.sizer.Add(bottom_panel, 0, wx.EXPAND)
		top_panel.SetSizer(top_sizer)
		bottom_panel.SetSizer(bottom_sizer)
		self.SetSizer(self.sizer)

	def get_username(self):
		return self.user_text.GetValue()

	def get_password(self):
		return self.password_text.GetValue()
