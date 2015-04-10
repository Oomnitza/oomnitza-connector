import wx
import os
import json
import sys
import time
import datetime
import platform
import plistlib
import argparse
import shlex
import subprocess
import threading
import thread
import wx.lib.masked
from Queue import Queue
from lib import config
from lib.config import parse_config
from lib.connector import run_connector
from connector_gui.utils.create_task_xml import create_task_xml
from connector_gui.utils.relative_path import relative_path
from connector_gui.widgets.frame import Frame
from connector_gui.widgets.panel import Panel
from connector_gui.widgets.image import Image
from connector_gui.widgets.button import Button
from connector_gui.widgets.text import Text
from connector_gui.widgets.listbox import ListBox
from connector_gui.widgets.listctrl import ListCtrl
from connector_gui.widgets.multitext import MultiText
from connector_gui.widgets.data_viewer import DataViewer
from connector_gui.widgets.tabbed_window import TabbedWindow
from connector_gui.widgets.scrolled_window import ScrolledWindow
from connector_gui.widgets.tabbed_panel import TabbedPanel
from connector_gui.widgets.login_dialog import LoginDialog


uppath = lambda _path, n: os.sep.join(_path.split(os.sep)[:-n])
base_dir = {'Darwin': uppath(os.path.abspath(sys.executable), 4), 'Windows': os.path.dirname(sys.executable), 'Linux': os.path.dirname(sys.executable)}

class ConfigView:

    def __init__(self, controller, model):
        self.model = model
        self.controller = controller
        self.style = self.load_style(platform.system().lower())
        self.running_status = {}
        self.threads = {}
        self.app = None
        self.frame = None
        self.init_page = None
        self.setting_page = None
        self.current_panel = {}
        self.scheduled_time = {}
        self.main_sizer = None
        self.data_viewer = None
        self.notebook = None
        self.cancel_btn = None
        self.apply_btn = None
        self.run_btn = None
        self.ok_btn = None

        self.app = wx.App()
        self.frame = Frame()
        #favicon = wx.Icon(relative_path('connector_gui/images/connector.ico'), wx.BITMAP_TYPE_ICO, 16, 16)
        favicon = wx.Icon(relative_path('connector.ico'), wx.BITMAP_TYPE_ICO, 16, 16)
        self.frame.SetIcon(favicon)
        self.frame.SetMaxSize(self.style['window']['size'])
        self.frame.SetMinSize(self.style['window']['size'])
        self.frame.set_title(self.style['window']['title'])
        self.frame.set_size(self.style['window']['size'])
        self.frame.set_foreground_color(self.style['window']['fg_color'])
        self.frame.set_background_color(self.style['window']['bg_color'])
        self.frame.Show()
        self.create_view()

        self.app.MainLoop()

    def create_view(self):
        # Create a container for presenting left side main menu
        menu = Panel(parent=self.frame,
                     size=self.style['menu']['size'],
                     fg_color=self.style['menu']['fg_color'],
                     bg_color=self.style['menu']['bg_color'])

        # Create a container for presenting init menu page
        self.init_page = ScrolledWindow(parent=self.frame,
                                   size=self.style['content']['size'],
                                   fg_color=self.style['content']['fg_color'],
                                   bg_color=self.style['content']['bg_color'])

        # Create a container for presenting settings pages
        self.setting_page = ScrolledWindow(parent=self.frame,
                                      size=self.style['content']['size'],
                                      fg_color=self.style['content']['fg_color'],
                                      bg_color=self.style['content']['bg_color'])
        self.setting_page.Hide()

        # Create sizers for layout
        self.main_sizer = wx.GridBagSizer(hgap=self.style['sizer']['hgap'],
                                          vgap=self.style['sizer']['vgap'])
        menu_sizer = wx.BoxSizer(wx.VERTICAL)
        content_sizer = wx.BoxSizer(wx.VERTICAL)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Create a image control to show up oomnitza logo in left side menu
        #logo = Image(menu, relative_path('connector_gui/images/oomnitza_logo.png'), 1, 1)
        logo = Image(menu, relative_path('oomnitza_logo.png'), 1, 1)

        menu_mappings = self.load_style('metadata')['menu']
        menu_connectors = self.model.get_config()
        menu_connectors_copy = menu_connectors.copy()
        if 'oomnitza' in menu_connectors_copy:
            del menu_connectors_copy['oomnitza']
        self.data_viewer = DataViewer(parent=menu,
                                      size=self.style['menu']['tree']['size'],
                                      mappings=menu_mappings,
                                      connectors=menu_connectors_copy,
                                      fg_color=self.style['menu']['tree']['fg_color'],
                                      bg_color=self.style['menu']['tree']['bg_color'])

        self.frame.Bind(wx.EVT_TREE_SEL_CHANGED,
                        self.menu_selection,
                        self.data_viewer)

        # Create button controls
        self.ok_btn = Button(self.frame, "OK")
        self.run_btn = Button(self.frame, "Run")
        self.stop_btn = Button(self.frame, "Stop")
        self.apply_btn = Button(self.frame, "Apply")
        self.cancel_btn = Button(self.frame, "Cancel")
        self.frame.Bind(wx.EVT_BUTTON, self.close, self.cancel_btn)
        self.frame.Bind(wx.EVT_BUTTON, lambda evt, run_btn=self.run_btn, selected='all':
                        self.on_stop(evt, run_btn, selected, None, 'all'), self.stop_btn)
        selected = []
        for connector in menu_connectors_copy:
            if menu_connectors_copy[connector]['enable'] == 'True':
                selected.append(connector)
        self.frame.Bind(wx.EVT_BUTTON, lambda evt, selected=selected,
                        stop_btn=self.stop_btn: self.run(evt, selected, stop_btn, None, 'all'), self.run_btn)
        self.frame.Bind(wx.EVT_BUTTON, self.save, self.apply_btn)
        self.frame.Bind(wx.EVT_BUTTON, self.save_and_close, self.ok_btn)
        self.ok_btn.SetDefault()
        self.stop_btn.Hide()
        self.apply_btn.Disable()
        self.model.add_observers(self.apply_btn, 'changed')

        # Arrange items with using sizer
        self.main_sizer.Add(menu, pos=(0, 0))
        self.main_sizer.Add(content_sizer, pos=(0, 1), span=(1, 5), flag=wx.EXPAND)
        self.main_sizer.Add(self.cancel_btn, pos=(1, 2), flag=wx.TOP,
                            border=self.style['bottom']['button']['border'])
        self.main_sizer.Add(self.apply_btn, pos=(1, 3), flag=wx.TOP,
                            border=self.style['bottom']['button']['border'])
        self.main_sizer.Add(button_sizer, pos=(1, 4), flag=wx.TOP,
                            border=self.style['bottom']['button']['border'])
        self.main_sizer.Add(self.ok_btn, pos=(1, 5), flag=wx.TOP,
                            border=self.style['bottom']['button']['border'])
        self.main_sizer.AddGrowableCol(1)
        self.main_sizer.AddGrowableRow(1)

        content_sizer.Add(self.init_page, 1, wx.EXPAND)
        content_sizer.Add(self.setting_page, 1, wx.EXPAND)

        button_sizer.Add(self.stop_btn, 1, wx.EXPAND)
        button_sizer.Add(self.run_btn, 1, wx.EXPAND)

        menu_sizer.Add(logo, flag=wx.LEFT | wx.TOP | wx.BOTTOM,
                       border=20)
        menu_sizer.Add(self.data_viewer, 1, flag=wx.EXPAND | wx.LEFT, border=15)

        # Associate container and sizer
        self.frame.SetSizer(self.main_sizer)
        menu.SetSizer(menu_sizer)
        self.frame.Bind(wx.EVT_CLOSE, self.close)
        self.frame.Layout()

        # Initialize the content
        self.on_init_page()

    def create_setting_view(self, panel, config, fields_display_order,
                            field_mappings, selected):


        sizer = wx.BoxSizer(wx.VERTICAL)
        sub_sizer = wx.GridBagSizer(hgap=self.style['sizer']['hgap'],
                                vgap=self.style['sizer']['vgap'])
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sub_panel = Panel(parent=panel,
                          size=self.style['content']['sub_panel']['size'],
                          fg_color=self.style['content']['sub_panel']['fg_color'],
                          bg_color=self.style['content']['sub_panel']['bg_color'])

        rows = 2
        cols = 4

        if 'enable' in config:
            enabled_label = wx.StaticText(sub_panel, -1, field_mappings['enable'])
            enabled_checkbox = wx.CheckBox(sub_panel, -1)
            sub_sizer.Add(enabled_label, pos=(rows, cols), flag=wx.RIGHT, border=5)
            sub_sizer.Add(enabled_checkbox, pos=(rows, cols+1))
            if config['enable'] == "True":
                enabled_checkbox.SetValue(True)
            else:
                enabled_checkbox.SetValue(False)
            self.frame.Bind(wx.EVT_CHECKBOX, lambda evt, field="enable",
                            selected=selected: \
                            self.checkbox_checked_event(evt, field, selected),
                            enabled_checkbox)
            rows += 1

            for field in fields_display_order:
                if field in config:
                    if type(config[field]) == list:
                        label = wx.StaticText(sub_panel, -1, field_mappings[field])
                        listbox = ListBox(sub_panel)
                        sub_sizer.Add(label, pos=(rows, cols))
                        sub_sizer.Add(listbox, pos=(rows, cols+1), span=(4, 1))
                        sub_sizer.Add(listbox.get_add_btn(), pos=(rows, cols+2))
                        sub_sizer.Add(listbox.get_del_btn(), pos=(rows+1, cols+2))
                        sub_sizer.Add(listbox.get_rename_btn(), pos=(rows+2, cols+2))
                        sub_sizer.Add(listbox.get_clear_btn(), pos=(rows+3, cols+2))

                        copy_fields_mapping = {v: k for k, v in field_mappings.items()}

                        self.frame.Bind(wx.EVT_BUTTON, lambda evt, listbox=listbox,
                            field=copy_fields_mapping[label.GetLabel()],
                            selected=selected: self.on_add(evt, listbox, field, selected),
                            listbox.get_add_btn())
                        self.frame.Bind(wx.EVT_BUTTON, lambda evt, listbox=listbox,
                            title=copy_fields_mapping[label.GetLabel()],
                            select=selected: self.on_delete(evt, listbox, title, select),
                            listbox.get_del_btn())
                        self.frame.Bind(wx.EVT_BUTTON, lambda evt, listbox=listbox,
                            title=copy_fields_mapping[label.GetLabel()],
                            select=selected: self.on_rename(evt, listbox, title, select),
                            listbox.get_rename_btn())
                        self.frame.Bind(wx.EVT_BUTTON, lambda evt, listbox=listbox,
                            title=copy_fields_mapping[label.GetLabel()],
                            select=selected: self.on_clear(evt, listbox, title, select),
                            listbox.get_clear_btn())
                        self.frame.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt, listbox=listbox,
                            title=copy_fields_mapping[label.GetLabel()],
                            select=selected: self.on_rename(evt, listbox, title, select))

                        for item in config[field]:
                            if item != "":
                                listbox.Append(str(item))
                        rows += 1
                    elif type(config[field]) == dict:
                        label = wx.StaticText(sub_panel, -1, field_mappings[field])
                        listctrl = ListCtrl(sub_panel, field_mappings[field], config[field])
                        sub_sizer.Add(label, pos=(rows, cols))
                        sub_sizer.Add(listctrl, pos=(rows, cols+1))
                        sub_sizer.Add(listctrl.get_add_btn(), pos=(rows, cols+2))
                        copy_fields_mapping = {v: k for k, v in field_mappings.items()}
                        self.frame.Bind(wx.EVT_BUTTON, lambda evt, listctrl=listctrl.item, \
                            index=listctrl.index: self.on_add_row(evt, listctrl, index), listctrl.add_btn)
                        self.frame.Bind(wx.EVT_LIST_END_LABEL_EDIT, lambda evt, listctrl=listctrl.item, \
                            title=copy_fields_mapping[label.GetLabel()], \
                            selected=selected: self.on_end_label_edit(evt, listctrl, title, selected), listctrl.item)
                        rows += 1
                    else:
                        if field in ["default_role", "default_position"]:
                            text = Text(sub_panel, field_mappings[field])
                            text.SetToolTipString("Please check the Oomnitza site to get information about setting.")
                        else:
                            if config[field] in ['True', 'true', True, 'False', 'false', False]:
                                text = wx.ComboBox(sub_panel, choices=['True', 'False'])
                                text.SetValue(field_mappings[field].title())
                                self.frame.Bind(wx.EVT_COMBOBOX, lambda evt, field=field, selected=\
                                                selected:self.dropdown_changed_event(evt, field, selected), text)
                            else:
                                text = Text(sub_panel, field_mappings[field])
                        label = wx.StaticText(sub_panel, -1, field_mappings[field])
                        text.SetValue(str(config[field]))
                        sub_sizer.Add(label, pos=(rows, cols))
                        sub_sizer.Add(text, pos=(rows, cols+1))
                        copy_fields_mapping = {v: k for k, v in field_mappings.items()}
                        self.frame.Bind(wx.EVT_TEXT, lambda evt, field=copy_fields_mapping[label.GetLabel()],
                                selected=selected: self.text_changed_event(evt, field, selected), text)
                        rows += 1
        config = self.model.get_config()
        test_btn = Button(panel, "Test Connection",
                          size=self.style['content']['sub_panel']['button']['size'])
        test_btn.SetToolTipString("Please enable connector before performing test of connection.")
        self.model.add_observers(test_btn, 'enabled', selected)
        run_btn = Button(panel, "Run Connector",
                          size=self.style['content']['sub_panel']['button']['size'])
        self.model.add_observers(run_btn, 'enabled', selected)
        stop_btn = Button(panel, "Stop Connector",
                          size=self.style['content']['sub_panel']['button']['size'])
        if config[selected]['enable'] == 'True':
            test_btn.Enable()
            run_btn.Enable()
        else:
            test_btn.Disable()
            run_btn.Disable()
            
        if selected in self.running_status:
            if self.running_status[selected] is True:
                run_btn.Show()
                stop_btn.Hide()
            else:
                run_btn.Hide()
                stop_btn.Show()
        else:
            run_btn.Show()
            stop_btn.Hide()

        self.frame.Bind(wx.EVT_BUTTON, lambda evt, selected=selected:
                        self.test_connection(evt, selected), test_btn)
        self.frame.Bind(wx.EVT_BUTTON, lambda evt, run_btn=run_btn, selected=selected, panel=panel:
                        self.on_stop(evt, run_btn, selected, panel), stop_btn)
        self.frame.Bind(wx.EVT_BUTTON, lambda evt, selected=selected,
                        stop_btn=stop_btn, panel=panel, mode='single': self.run(evt, selected, stop_btn, panel, mode), run_btn)
        sizer.Add(sub_panel, 1)
        sizer.Add(button_sizer, 0, flag=wx.ALIGN_RIGHT | wx.RIGHT, border=20)
        button_sizer.Add(test_btn, 0, flag=wx.BOTTOM, border=20)
        button_sizer.Add(run_btn, 0, flag=wx.BOTTOM, border=20)
        button_sizer.Add(stop_btn, 0, flag=wx.BOTTOM, border=20)

        # Associate container and sizer
        panel.SetSizer(sizer)
        sub_panel.SetSizer(sub_sizer)
        panel.Layout()

    def create_scheduler_view(self, panel, selected):
        if platform.system() == 'Darwin':
            # Create a sizer for setting page layout
            sizer = wx.BoxSizer(wx.VERTICAL)
            sub_sizer = wx.GridBagSizer(hgap=self.style['sizer']['hgap'],
                                    vgap=self.style['sizer']['vgap'])

            sub_panel = Panel(parent=panel,
                              size=self.style['content']['sub_panel']['size'],
                              fg_color=self.style['content']['sub_panel']['fg_color'],
                              bg_color=self.style['content']['sub_panel']['bg_color'])

            rows = 2
            cols = 4

            # Create combobox controls for cron job setting
            min_label = wx.StaticText(sub_panel, -1, "Minutes")
            min_combobox = wx.ComboBox(sub_panel, choices=[str(x) for x in range(60)]+['/',',','*','-'])
            hour_label = wx.StaticText(sub_panel, -1, "Hours")
            hour_combobox = wx.ComboBox(sub_panel, choices=[str(x) for x in range(24)]+['/',',','*','-'])
            day_label = wx.StaticText(sub_panel, -1, "Day of Month")
            day_combobox = wx.ComboBox(sub_panel, choices=[str(x) for x in range(1,32)]+['/',',','*','-','?','L'])
            month_label = wx.StaticText(sub_panel, -1, "Month")
            month_combobox = wx.ComboBox(sub_panel, choices=[str(x) for x in range(1,13)]+['/',',','*','-'])
            weekday_label = wx.StaticText(sub_panel, -1, "Day of Week")
            weekday_combobox = wx.ComboBox(sub_panel, choices=[str(x) for x in range(7)]+['/',',','*','-','?','L'])

            time_labels = [min_label, hour_label, day_label,
                           month_label, weekday_label]
            time_widgets = [min_combobox, hour_combobox, day_combobox,
                            month_combobox, weekday_combobox]
            set_btn = Button(panel, "Set",
                             size=self.style['content']['sub_panel']['button']['size'])

            time_objects = {
                "minute": min_combobox,
                "hour": hour_combobox,
                "day": day_combobox,
                "month": month_combobox,
                "weekday": weekday_combobox
            }

            self.frame.Bind(wx.EVT_BUTTON, lambda evt, time_widgets=time_objects,
                            selected=selected:\
                            self.set_launchd(evt, time_widgets, selected), set_btn)

            for i in range(5):
                sub_sizer.Add(time_labels[i], pos=(rows, cols), flag=wx.LEFT)
                sub_sizer.Add(time_widgets[i], pos=(rows, cols+1), flag=wx.LEFT)
                rows += 1

            sizer.Add(sub_panel, 1)
            sizer.Add(set_btn, 0, flag=wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, border=20)

            # Associate container and sizer
            panel.SetSizer(sizer)
            sub_panel.SetSizer(sub_sizer)
            panel.Layout()

        elif platform.system() == 'Windows':

            sub_panel = Panel(parent=panel,
                              size=self.style['content']['sub_panel']['size'],
                              fg_color=self.style['content']['sub_panel']['fg_color'],
                              bg_color=self.style['content']['sub_panel']['bg_color'])

            rows = 0
            cols = 0
            time_widgets = {}

            # Create sizers for setting page layout
            sizer = wx.BoxSizer(wx.VERTICAL)
            sub_sizer = wx.GridBagSizer(hgap=self.style['sizer']['hgap'],
                                        vgap=self.style['sizer']['vgap'])
            radio_menu_sizer = wx.GridBagSizer(hgap=self.style['sizer']['hgap'],
                                               vgap=self.style['sizer']['vgap'])
            datetime_sizer = wx.BoxSizer(wx.HORIZONTAL)
            scheduler_sizer = wx.BoxSizer(wx.VERTICAL)

            # Create panels for presenting selected radio settings
            daily_panel = Panel(parent=sub_panel,
                                size=self.style['content']['sub_panel']['size'],
                                fg_color=self.style['content']['sub_panel']['fg_color'],
                                bg_color=self.style['content']['sub_panel']['bg_color'])
            daily_panel.Hide()
            self.current_panel['daily'] = daily_panel.GetId()
            daily_setting_sizer = wx.GridBagSizer(hgap=self.style['sizer']['hgap'],
                                                  vgap=self.style['sizer']['vgap'])

            daily_recur_label = wx.StaticText(daily_panel, -1, "Recur every: ")
            daily_recur_text = wx.TextCtrl(daily_panel, -1, size=(50, -1))
            daily_recur_text.SetValue("1")
            time_widgets['daily_recur'] = daily_recur_text
            days_label = wx.StaticText(daily_panel, -1, " days")
            daily_setting_sizer.Add(daily_recur_label, pos=(0, 0), flag=wx.LEFT, border=10)
            daily_setting_sizer.Add(daily_recur_text, pos=(0, 1))
            daily_setting_sizer.Add(days_label, pos=(0, 2))
            daily_panel.SetSizer(daily_setting_sizer)

            weekly_panel = Panel(parent=sub_panel,
                                 size=self.style['content']['sub_panel']['size'],
                                 fg_color=self.style['content']['sub_panel']['fg_color'],
                                 bg_color=self.style['content']['sub_panel']['bg_color'])
            weekly_panel.Hide()
            self.current_panel['weekly'] = weekly_panel.GetId()
            weekly_setting_sizer = wx.GridBagSizer(hgap=self.style['sizer']['hgap'],
                                                   vgap=self.style['sizer']['vgap'])
            weekly_subsizer_row1 = wx.BoxSizer(wx.HORIZONTAL)
            weekly_subsizer_row2 = wx.BoxSizer(wx.HORIZONTAL)
            weekly_subsizer_row3 = wx.BoxSizer(wx.HORIZONTAL)
            weekly_recur_label = wx.StaticText(weekly_panel, -1, "Recur every: ")
            weekly_recur_text = wx.TextCtrl(weekly_panel, -1, size=(50, -1))
            weekly_recur_text.SetValue("1")
            time_widgets['weekly_recur'] = weekly_recur_text
            weeks_label = wx.StaticText(weekly_panel, -1, " week(s) on: ")
            weekly_subsizer_row1.Add(weekly_recur_label, 1)
            weekly_subsizer_row1.Add(weekly_recur_text, 1)
            weekly_subsizer_row1.Add(weeks_label, 2)
            weekly_setting_sizer.Add(weekly_subsizer_row1, pos=(0, 0), flag=wx.LEFT, border=10)
            weekly_setting_sizer.Add(weekly_subsizer_row2, pos=(1, 0), flag=wx.LEFT, border=10)
            weekly_setting_sizer.Add(weekly_subsizer_row3, pos=(2, 0), flag=wx.LEFT, border=10)
            days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
            rows = 1
            cols = 0
            time_widgets['weekdays'] = []
            temp_sizer = weekly_subsizer_row2
            for day in days:
                label = wx.StaticText(weekly_panel, -1, day)
                checkbox = wx.CheckBox(weekly_panel, -1)
                time_widgets['weekdays'].append([label, checkbox])
                temp_sizer.Add(checkbox, 1, wx.EXPAND)
                temp_sizer.Add(label, 2, wx.EXPAND)
                cols += 2
                if days.index(day) == 3:
                    rows += 1
                    cols = 0
                    temp_sizer = weekly_subsizer_row3

            weekly_panel.SetSizer(weekly_setting_sizer)

            monthly_panel = Panel(parent=sub_panel,
                                 size=self.style['content']['sub_panel']['size'],
                                 fg_color=self.style['content']['sub_panel']['fg_color'],
                                 bg_color=self.style['content']['sub_panel']['bg_color'])
            monthly_panel.Hide()
            self.current_panel['monthly'] = monthly_panel.GetId()
            monthly_setting_sizer = wx.GridBagSizer(hgap=self.style['sizer']['hgap'],
                                                    vgap=self.style['sizer']['vgap'])

            monthly_months_label = wx.StaticText(monthly_panel, -1, "Months: ")
            monthly_days_label = wx.StaticText(monthly_panel, -1, "Days: ")
            monthly_setting_sizer.Add(monthly_months_label, pos=(0, 0), flag=wx.LEFT, border=10)
            monthly_setting_sizer.Add(monthly_days_label, pos=(1, 0), flag=wx.LEFT, border=10)
            months = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 
                      'December']
            monthly_months_dropdown = wx.CheckListBox(monthly_panel, -1, size=(100, 50), choices=months)
            monthly_days_dropdown = wx.CheckListBox(monthly_panel, -1, size=(100, 50), choices=[str((x + 1)) for x in range(31)])
            time_widgets['days'] = monthly_days_dropdown
            time_widgets['months'] = monthly_months_dropdown
            monthly_setting_sizer.Add(monthly_months_dropdown, pos=(0, 1))
            monthly_setting_sizer.Add(monthly_days_dropdown, pos=(1, 1))
            monthly_panel.SetSizer(monthly_setting_sizer)

            scheduler_sizer.Add(daily_panel, 1, wx.EXPAND)
            scheduler_sizer.Add(weekly_panel, 1, wx.EXPAND)
            scheduler_sizer.Add(monthly_panel, 1, wx.EXPAND)

            # Arrange widgets on the page
            rows = 0
            cols = 0
            time_widgets['period'] = []
            for period in ["One time", "Daily", "Weekly", "Monthly"]:
                label = wx.StaticText(sub_panel, -1, period)
                radio = wx.RadioButton(sub_panel, -1)
                time_widgets['period'].append([label, radio])
                if period == "One time":
                    radio.SetValue(True)
                radio_menu_sizer.Add(radio, pos=(rows, cols))
                radio_menu_sizer.Add(label, pos=(rows, cols+1))
                self.frame.Bind(wx.EVT_RADIOBUTTON, lambda evt, panel=sub_panel,
                                selected=label.GetLabel().lower():
                                self.scheduler_selection(evt, panel, selected), radio)
                rows += 1

            sub_sizer.Add(radio_menu_sizer, pos=(2, 3), span=(2, 0))
            datetime_label = wx.StaticText(sub_panel, -1, "Start: ")
            date_picker = wx.DatePickerCtrl(sub_panel, -1)
            blank_label = wx.StaticText(sub_panel, -1, " ")
            time_picker = wx.lib.masked.TimeCtrl(sub_panel, -1)

            datetime_sizer.Add(datetime_label, 1)
            datetime_sizer.Add(date_picker, 2)
            datetime_sizer.Add(blank_label, 0)
            datetime_sizer.Add(time_picker, 2)

            sub_sizer.Add(datetime_sizer, pos=(2, 4), flag=wx.LEFT, border=10)
            sub_sizer.Add(scheduler_sizer, pos=(3, 4))

            set_btn = Button(panel, "Set",
                             size=self.style['content']['sub_panel']['button']['size'])

            time_widgets['start_date'] = date_picker
            time_widgets['start_time'] = time_picker

            self.frame.Bind(wx.EVT_BUTTON, lambda evt, time_widgets=time_widgets,
                            selected=selected:\
                            self.set_task_scheduler(evt, time_widgets, selected), set_btn)

            sizer.Add(sub_panel, 1)
            sizer.Add(set_btn, 0, flag=wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, border=20)

            # Associate container and sizer
            panel.SetSizer(sizer)
            sub_panel.SetSizer(sub_sizer)
            panel.Layout()

    def set_task_scheduler(self, event, time_widgets, selected):
        dlg = LoginDialog()
        ret_code = dlg.ShowModal()

        if ret_code == wx.ID_OK:
            username = dlg.get_username()
            password = dlg.get_password()
            period = ""
            if not username or not password:
                wx.MessageBox('User name and password are required!', 'Scheduled Unsuccessful',
                               wx.OK | wx.ICON_INFORMATION)
            else:
                options = {}
                period_choice = ''

                task_name = 'oomnitza.%s' % (selected)
                options['command'] = sys.executable
                options['arguments'] = 'upload %s' % (selected)
                options['user'] = username

                start_date = time_widgets['start_date'].GetValue()
                ymd = map(int, start_date.FormatISODate().split('-'))
                start_date = datetime.date(*ymd)

                start_time = str(time_widgets['start_time'].GetValue())
                start_time = datetime.datetime.strptime(start_time, "%I:%M:%S %p")
                start_time = start_time.strftime("%H:%M:%S")

                options['start_time'] = '%sT%s' % (start_date, start_time)
                print options['start_time']

                for period_set in time_widgets['period']:
                    if period_set[1].GetValue():
                        period = period_set[0].GetLabel()

                if period == "One time":
                    period_choice = 'once'

                elif period == "Daily":
                    period_choice = 'daily'
                    options['recur'] = time_widgets['daily_recur'].GetValue()

                elif period == "Weekly":
                    period_choice = 'weekly'
                    options['recur'] = time_widgets['weekly_recur'].GetValue()

                    weekdays = []
                    mappings = {'sun': 'Sunday',
                        'mon': 'Monday',
                        'tue': 'Tuesday',
                        'wed': 'Wednesday',
                        'thu': 'Thursday',
                        'fri': 'Friday',
                        'sat': 'Saturday'}
                    for day_set in time_widgets['weekdays']:
                        if day_set[1].IsChecked():
                            weekdays.append(mappings[day_set[0].GetLabel().lower()])
                    options['days'] = weekdays

                elif period == "Monthly":
                    period_choice = 'monthly'
                    options['months'] = time_widgets['months'].GetCheckedStrings()
                    options['days'] = time_widgets['days'].GetCheckedStrings()

                task_xml_file = create_task_xml(period_choice, options)
                command = "schtasks /CREATE /f /xml %s /ru %s /rp %s /tn %s" \
                          % (task_xml_file, username, password, task_name)

                status = os.system(command)

                if status == 0:
                    wx.MessageBox('Task is scheduled.', 'Scheduled Successful',
                                  wx.OK | wx.ICON_INFORMATION)
                else:
                    wx.MessageBox('Scheduled failure!\nPlease check your user name and password.', 'Scheduled Unsuccessful',
                                  wx.OK | wx.ICON_INFORMATION)

    def scheduler_selection(self, event, panel, selected):
        selected_widgets = []
        unselected_widgets = []
        for key in self.current_panel:
            if key == selected:
                selected_widgets.append(self.current_panel[key])
            else:
                unselected_widgets.append(self.current_panel[key])
        for child in panel.GetChildren():
            if child.GetId() in selected_widgets:
                child.Show()
                child.Layout()
            elif child.GetId() in unselected_widgets:
                child.Hide()
        panel.Layout()

    def set_launchd(self, event, time_widgets, selected):
        dlg = LoginDialog()
        ret_code = dlg.ShowModal()

        if ret_code == wx.ID_OK:
            username = dlg.get_username()
            password = dlg.get_password()
            dlg.Destroy()
            if not username or not password:
                wx.MessageBox('User name and password are required!', 'Scheduled Unsuccessful',
                               wx.OK | wx.ICON_INFORMATION)
            else:
                minute = time_widgets['minute'].GetValue()
                hour = time_widgets['hour'].GetValue()
                day = time_widgets['day'].GetValue()
                month = time_widgets['month'].GetValue()
                weekday = time_widgets['weekday'].GetValue()

                arguments = []
                arguments.append(sys.executable)
                # connector_path = relative_path("connector.py")
                # arguments.append(connector_path)
                arguments.append('upload')
                arguments.append(selected)

                filename = 'com.oomnitza.%s' % (selected)
                filepath = '/tmp/' + filename + '.plist'
                plist = {'ProgramArguments': arguments, 'KeepAlive': {'SuccessfulExit': False},
                         'Label': filename, 'Minute': minute, 'Hour': hour, 'Day': day,
                         'Month': month, 'Weekday': weekday}
                with open(filepath, "wb") as f:
                    plistlib.writePlist(plist, f)

                command = "echo %s sudo -S mv " % (password) + filepath + " /Library/LaunchDaemons/" + filename + ".plist"
                args = shlex.split(command)

                status = subprocess.call(args)
                if status == 0:
                    wx.MessageBox('Task is scheduled.', 'Scheduled Successful',
                                  wx.OK | wx.ICON_INFORMATION)
                else:
                    wx.MessageBox('Scheduled failure!\nPlease check your user name and password.', 'Scheduled Unsuccessful',
                                  wx.OK | wx.ICON_INFORMATION)

    def create_log_view(self, panel, selected):
        sizer = wx.GridBagSizer(hgap=self.style['sizer']['hgap'],
                                vgap=self.style['sizer']['vgap'])
        sub_sizer = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(panel, -1, "Logs")

        # Create a multi-line control for displaying system log
        multitext = MultiText(panel, size=self.style['content']['multitext']['size'],
                              fg_color=self.style['content']['multitext']['fg_color'],
                              bg_color=self.style['content']['multitext']['bg_color'])

        # Create a clear button
        clear_btn = Button(panel, "Clear")
        self.frame.Bind(wx.EVT_BUTTON, lambda evt, panel=panel,
                        multitext_id=multitext.GetId(), selected=selected: \
                        self.clear_log(evt, panel, multitext_id, selected), clear_btn)

        # Create a reload button
        reload_btn = Button(panel, "Reload")
        self.frame.Bind(wx.EVT_BUTTON, lambda evt, panel=panel,
                        multitext_id=multitext.GetId(),
                        clear_btn=clear_btn, selected=selected:\
                        self.reload_log(evt, panel, multitext_id, clear_btn, selected),
                        reload_btn)

        logs = ""
        try:
            #log_file = open(relative_path('{0}.log'.format(selected)), "r")
            log_file = open(os.path.join(base_dir[platform.system()], '{0}.log'.format(selected)), "r")
            for line in log_file.readlines():
                if line != "\n" and line != "":
                    logs += line
        except IOError:
            pass

        if logs:
            multitext.SetValue(logs)
        else:
            clear_btn.Disable()

        rows = 1
        cols = 2

        sizer.Add(sub_sizer, pos=(rows, cols))
        sub_sizer.Add(label, 0)
        sub_sizer.Add(clear_btn, 0, wx.LEFT, 260)
        sub_sizer.Add(reload_btn, 0)
        rows += 1
        sizer.Add(multitext, pos=(rows, cols), span=(1, 5))

        # Associate container and sizer
        panel.SetSizer(sizer)
        panel.Layout()

    def clear_log(self, event, panel, multitext_id, selected):
        dlg = wx.MessageDialog(None, "Are you sure you want to clear the logs?",
                               "Clear Log", wx.YES_NO | wx.ICON_QUESTION)
        if (dlg.ShowModal() == wx.ID_YES):
            for child in panel.GetChildren():
                if child.GetId() == multitext_id:
                    #open(relative_path("{0}.log".format(selected)), "w").close()
                    open(os.path.join(base_dir[platform.system()], '{0}.log'.format(selected)), "w").close()
                    event.GetEventObject().Disable()
                    self.reload_log(event, panel, multitext_id,
                                    event.GetEventObject(), selected)
        dlg.Destroy()

    def reload_log(self, event, panel, multitext_id, clear_btn, selected):
        for child in panel.GetChildren():
            if child.GetId() == multitext_id:
                logs = ""
                #log_file = open(relative_path("{0}.log".format(selected)), "r")
                log_file = open(os.path.join(base_dir[platform.system()], '{0}.log'.format(selected)), "r")
                for line in log_file.readlines():
                    if line != "\n" and line != "":
                        logs += line

                child.SetValue("")
                if logs:
                    child.SetValue(logs)
                    clear_btn.Enable()
                else:
                    child.SetForegroundColour(self.style['content']['multitext']['fg_color'])
                    child.SetValue("Update Info: There is no log.")

    def menu_selection(self, event):
        selected = self.data_viewer.GetItemText(event.GetItem()).lower()
        if selected == "oomnitza connection":
            self.on_setting_page('oomnitza')
        elif selected == "connectors":
            self.on_init_page()
        else:
            self.on_setting_page(selected)

    def on_init_page(self):
        # Hide setting page
        self.setting_page.Hide()

        # Create a sizer for init page layout
        sizer = wx.GridBagSizer(hgap=self.style['sizer']['hgap'],
                                vgap=self.style['sizer']['vgap'])

        # Create a label for init page title
        rows = 0
        cols = 0

        title = wx.StaticText(self.init_page, -1, "Connectors List")
        description = wx.StaticText(self.init_page, -1,\
        "Configure each connector before running it.\n"\
        "Please refer to https://github.com/oomnitza for additional information.")

        # Create a tree control to be the menu of init page
        init_page_menu = wx.TreeCtrl(self.init_page, -1,
            style=wx.TR_HAS_BUTTONS | wx.TR_HIDE_ROOT | wx.NO_BORDER)
        init_page_menu.SetMinSize((200, 370))
        init_page_menu.SetBackgroundColour(self.style['content']['tree']['bg_color'])
        init_page_menu.SetForegroundColour(self.style['content']['tree']['fg_color'])
        root = init_page_menu.AddRoot("")
        menu_font = wx.Font(self.style['content']['tree']['font_size'], 
                            wx.DEFAULT, wx.NORMAL, wx.BOLD, True)

        config = self.model.get_config()
        menu_mappings = self.load_style('metadata')['menu']

        for integration in sorted(config.keys()):
            if integration in menu_mappings:
                init_page_menu.AppendItem(root, menu_mappings[integration])
        init_page_menu.SetFont(menu_font)
        self.frame.Bind(wx.EVT_TREE_SEL_CHANGED, self.menu_selection, init_page_menu)

        # Arrange items with using sizer
        sizer.Add(title, pos=(rows, cols), flag=wx.LEFT | wx.TOP,
                  border=self.style['content']['padding'])
        rows += 1
        sizer.Add(description, pos=(rows, cols), flag=wx.LEFT,
                  border=self.style['content']['padding'])
        rows += 1
        sizer.Add(init_page_menu, pos=(rows, cols), flag=wx.LEFT | wx.TOP,
                  border=self.style['content']['padding'])
        rows += 1

        # Associate container and sizer
        self.init_page.SetSizer(sizer)

        # Switch to init page and refresh page
        self.init_page.Show()
        self.main_sizer.Layout()

    def on_setting_page(self, selected):
        # Hide init page
        self.init_page.Hide()

        # Clear previous setting page content
        for child in self.setting_page.GetChildren():
            child.Destroy()

        config = self.model.get_config()
        fields_display_order = self.load_style('metadata')['fields_display_order']
        field_mappings = self.load_style('metadata')['field_mappings']

        sizer = wx.GridBagSizer(hgap=self.style['sizer']['hgap'],
                                vgap=self.style['sizer']['vgap'])
        rows = 0
        cols = 0

        if selected == "oomnitza":

            title = wx.StaticText(self.setting_page, -1, "Oomnitza Connection")
            description = wx.StaticText(self.setting_page, -1,\
            "Configure Oomnitza connection before running connectors.\n"\
            "Please refer to https://github.com/oomnitza for additional information.")

            sizer.Add(title, pos=(rows, cols), span=(1, 2),
                      flag=wx.LEFT | wx.TOP,
                      border=self.style['content']['padding'])
            rows += 1
            sizer.Add(description, pos=(rows, cols), span=(1, 2),
                      flag=wx.LEFT | wx.BOTTOM,
                      border=self.style['content']['padding'])
            rows += 1
            for field in fields_display_order:
                if field in config[selected]:
                    label = wx.StaticText(self.setting_page, -1, field_mappings[field])
                    if config[selected][field] in ['True', 'true', True, 'False', 'false', False]:
                        text = wx.ComboBox(self.setting_page, choices=['True', 'False'])
                        text.SetValue(config[selected][field].title())
                        self.frame.Bind(wx.EVT_COMBOBOX, lambda evt, field=field, selected=\
                                        selected:self.dropdown_changed_event(evt, field, selected), text)
                    else:
                        text = Text(self.setting_page, str(config[selected][field]))
                    sizer.Add(label, pos=(rows, cols), flag=wx.LEFT,
                              border=self.style['content']['padding'])
                    sizer.Add(text, pos=(rows, cols+1), flag=wx.LEFT,
                              border=self.style['content']['padding'])

                    copy_fields_mapping = {v: k for k, v in field_mappings.items()}
                    self.frame.Bind(wx.EVT_TEXT, lambda evt, \
                                    field=copy_fields_mapping[label.GetLabel()], \
                                    selected=selected: \
                                    self.text_changed_event(evt, field, selected), text)
                    rows += 1
            self.setting_page.SetSizer(sizer)
        else:
            tabbed_window = TabbedWindow(self.setting_page,
                                         size=self.style['content']['panel']['size'])

            setting_panel = TabbedPanel(tabbed_window)
            scheduler_panel = TabbedPanel(tabbed_window)
            log_panel = TabbedPanel(tabbed_window)

            tabbed_window.AddPage(setting_panel, "Setting")
            tabbed_window.AddPage(scheduler_panel, "Scheduler")
            tabbed_window.AddPage(log_panel, "Logs")

            self.create_setting_view(setting_panel, config[selected],
                                     fields_display_order,
                                     field_mappings, selected)
            self.create_scheduler_view(scheduler_panel, selected)
            self.create_log_view(log_panel, selected)

            sizer.Add(tabbed_window, pos=(rows, cols), flag=wx.EXPAND)

        # Switch to setting page and refresh page
        self.setting_page.Show()
        self.main_sizer.Layout()

    def perform_syncing(self, oomnitza_connector, connector, options, selected, run_btn, stop_btn):
        run_connector(oomnitza_connector, connector, options)
        self.running_status[selected] = True
        run_btn.Show()
        stop_btn.Hide()
        self.frame.GetSizer().Layout()

    def run(self, event, selected, stop_btn, panel=None, mode='all'):
        run_btn = event.GetEventObject()
        dlg = wx.MessageDialog(None, "Would you like to start the sync process?", "Run Connector")
        ret_code = dlg.ShowModal()

        if ret_code == wx.ID_OK:
            if not selected is None:
                stop_btn.Show()
                run_btn.Hide()

                parser = argparse.ArgumentParser()
                parser.add_argument("action", nargs='?', default='gui', choices=['gui', 'upload', 'generate-ini'], help="Action to perform.")
                parser.add_argument("connectors", nargs='*', default=[], help="Connectors to run.")
                parser.add_argument('--testmode', action='store_true', help="Run connectors in test mode.")
                parser.add_argument('--ini', type=str, default=os.path.join(os.path.dirname(sys.executable), "config.ini"), help="Config file to use.")
                #parser.add_argument('--ini', type=str, default=os.path.join(config.ROOT, "config.ini"), help="Config file to use.")
                parser.add_argument('--logging-config', type=str, default="USE_DEFAULT", help="Use to override logging config file to use.")

                args = parser.parse_args()

                connectors = parse_config(args)
                oomnitza_connector = connectors.pop('oomnitza')["__connector__"]
                options = {}

                if mode == 'all':
                    for select in selected:
                        self.running_status['all_' + select] = False
                        t = threading.Thread(target=self.perform_syncing, args=(oomnitza_connector, connectors[select], options, 'all_' + select, run_btn, stop_btn,))
                        self.threads['all_' + select] = t
                        t.daemon = True
                        t.start()
                else:
                    self.running_status[selected] = False
                    t = threading.Thread(target=self.perform_syncing, args=(oomnitza_connector, connectors[selected], options, selected, run_btn, stop_btn,))
                    self.threads[selected] = t
                    t.daemon = True
                    t.start()

                self.frame.GetSizer().Layout()
                if not panel is None:
                    panel.GetSizer().Layout()

    def on_stop(self, event, run_btn, selected, panel=None, mode=None):
        stop_btn = event.GetEventObject()
        dlg = wx.MessageDialog(None, "Do you want to stop the process of uploading?", "Warning")
        ret_code = dlg.ShowModal()

        if ret_code == wx.ID_OK:
            if mode == 'all':
                for select in self.running_status:
                    if 'all_' in select:
                        self.running_status[select] = True
            else:
                self.running_status[selected] = True
                self.threads[selected].join()
            stop_btn.Hide()
            run_btn.Show()
            self.frame.Layout()
            if not panel is None:
                panel.Layout()

    def close(self, event):
        """
        Stop the task queue, terminate processes and close the window.
        """
        #flag = True
        #for key in self.running_status:
        #    if self.running_status[key] is False:
        #        flag = False
        #        break
        #if not flag:
        #    wx.MessageBox('Please stop the process of uploading before closing application!', 'Warning',
        #            wx.OK | wx.ICON_INFORMATION)

        #else:
        self.frame.Destroy()

    def on_add(self, event, listbox, field, selected):
        text = wx.GetTextFromUser('Enter a new item', 'Insert dialog')
        if text != '':
            listbox.Append(text)
        self.controller.edit_config(field, selected, listbox.GetStrings())

    def on_add_row(self, event, listctrl, index):
        new_index = listctrl.InsertStringItem(index, "Please Insert Key...")
        listctrl.SetStringItem(new_index, 1, "Please Insert Value...")

    def on_end_label_edit(self, event, listctrl, field, selected, field_mappings):
        edit_col = event.GetItem().GetColumn()
        edit_text = event.GetItem().GetText()
        if edit_col == 0:
            exist = False
            copy_fields_mapping = {v: k for k, v in field_mappings.items()}
            compare_value = listctrl.GetItem(event.GetItem().GetId(), 1).GetText()
            if edit_text:
                for value in copy_fields_mapping:
                    if value == compare_value:
                        #self.top_frame.config[selected][field] = self.top_frame.config[selected][field].pop(edit_text)
                        #self.top_frame.config[selected][field][edit_text] = compare_value
                        exist = True
                if not exist:
                    pass
                    #self.top_frame.config[selected][field][edit_text] = compare_value
        elif edit_col == 1:
            exist = False
            compare_key = listctrl.GetItem(event.GetItem().GetId(), 0).GetText()
            for key in field_mappings:
                if key == compare_key:
                    #self.top_frame.config[selected][field][compare_key] = edit_text
                    exist = True
            if not exist and compare_key:
                pass
                #self.top_frame.config[selected][field][compare_key] = edit_text

    def on_rename(self, event, listbox, field, selected):
        sel = listbox.GetSelection()
        text = listbox.GetString(sel)
        renamed = wx.GetTextFromUser('Rename item', 'Rename dialog', text)
        if renamed != '':
            listbox.Delete(sel)
            listbox.Insert(renamed, sel)
        self.controller.edit_config(field, selected, listbox.GetStrings())

    def on_delete(self, event, listbox, field, selected):
        sel = listbox.GetSelection()
        if sel != -1:
            listbox.Delete(sel)
        self.controller.edit_config(field, selected, listbox.GetStrings())

    def on_clear(self, event, listbox, field, selected):
        listbox.Clear()
        self.controller.edit_config(field, selected, listbox.GetStrings())

    def save(self, event):
        self.controller.save_config()
        self.data_viewer.update_status(self.model.get_config())
        self.apply_btn.Disable()

    def save_and_close(self, event):
        self.save(event)
        self.close(event)

    def text_changed_event(self, event, field, selected):
        value = event.GetEventObject().GetValue()
        self.controller.edit_config(field, selected, value)

    def dropdown_changed_event(self, event, field, selected):
        value = event.GetEventObject().GetValue()
        self.controller.edit_config(field, selected, value)

    def checkbox_checked_event(self, event, field, selected):
        sender = event.GetEventObject()
        if sender.GetValue():
            self.controller.edit_config(field, selected, "True")
        else:
            self.controller.edit_config(field, selected, "False")

    def test_connection(self, event, selected):
        try:
            parser = argparse.ArgumentParser()
            parser.add_argument("action", nargs='?', default='gui', choices=['gui', 'upload', 'generate-ini'], help="Action to perform.")
            parser.add_argument("connectors", nargs='*', default=[], help="Connectors to run.")
            parser.add_argument('--testmode', action='store_true', help="Run connectors in test mode.")
            parser.add_argument('--ini', type=str, default=os.path.join(os.path.dirname(sys.executable), "config.ini"), help="Config file to use.")
            #parser.add_argument('--ini', type=str, default=os.path.join(config.ROOT, "config.ini"), help="Config file to use.")
            parser.add_argument('--logging-config', type=str, default="USE_DEFAULT", help="Use to override logging config file to use.")

            args = parser.parse_args()

            connectors = parse_config(args)
            connector = connectors[selected]['__connector__']
            response = connector.test_connection({})

            if response['error']:
                wx.MessageBox('Connection failure (%s)!\nPlease verify your settings.' %(response['error']), 'Test Unsuccessful',
                          wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox('Connection is established.', 'Test Successful',
                          wx.OK | wx.ICON_INFORMATION)
        except:
            wx.MessageBox('Connection failure!\nPlease verify your settings.', 'Test Unsuccessful',
                          wx.OK | wx.ICON_INFORMATION)

    def load_style(self, type):
        path = relative_path('%s.json' % (type))
        #path = relative_path('connector_gui/styles/%s.json' % (type))

        with open(path) as json_file:
            style = json.load(json_file)

        return style



