import sys
import json
import ConfigParser

from lib.config import format_sections_for_ini
from utils.relative_path import relative_app_path

path = relative_app_path('config.ini')


class ConfigModel:

    def __init__(self):
        self.config = self.parse_config()
        self.config_copy = self.parse_config()
        self.observers = {}
        self.observers['changed'] = []
        self.observers['enabled'] = {}

    def add_observers(self, observer, type, selected=None):
        if type == 'changed':
            self.observers['changed'].append(observer)
        elif type == 'enabled' and not selected is None:
            if selected not in self.observers['enabled']:
                self.observers['enabled'][selected] = []
            self.observers['enabled'][selected].append(observer)

    def notify_observers(self, type):
        if type == 'changed':
            for observer in self.observers['changed']:
                observer.update(self.compare_config())
        elif type == 'enabled':
            for selected in self.observers['enabled']:
                if self.config_copy[selected]['enable'] in ['True', 'true', True]:
                    for observer in self.observers['enabled'][selected]:
                        try:
                            observer.update(False)
                        except:
                            continue
                else:
                    for observer in self.observers['enabled'][selected]:
                        try:
                            observer.update(True)
                        except:
                            continue

    def compare_config(self):
        for integration in self.config:
            for key in self.config[integration]:
                if self.config[integration][key] != self.config_copy[integration][key]:
                    return False
        return True

    def get_config(self):
        return self.config

    def get_config_copy(self):
        return self.config_copy

    def set_config(self, field, selected, value):
        self.config[selected][field] = value
        self.notify_observers('changed')

    def parse_config(self):
        """
        Parse connector configuration and generate a result in dictionary
        format which includes integration names and the required info for
        pulling out data
        """
        config_parser = ConfigParser.ConfigParser()
        config_parser.optionxform = str
        config_parser.read(path)

        config = {}

        for section in config_parser.sections():
            config[section] = {}
            for option in config_parser.options(section):
                try:
                    config[section][option] = json.loads(config_parser.get(section, option))
                    if isinstance(config[section][option], list):
                        if len(config[section][option]) >= 1 and \
                                isinstance(config[section][option][0], int):
                            config[section][option] = config_parser.get(section, option)
                except:
                    config[section][option] = config_parser.get(section, option)

        return config

    def save_config(self):
        """
        Save connector configuration
        """
        section_config = {}

        for section in self.config:
            section_config[section] = []
            for field in self.config[section]:
                section_config[section].append((field, self.config[section][field]))

        dynamic_config = self.parse_config()
        for section in dynamic_config:
            if section in self.config:
                for field in dynamic_config[section]:
                    if field not in self.config[section]:
                        section_config[section].append((field, dynamic_config[section][field]))

        format_config = format_sections_for_ini(section_config)

        with open(path, 'w') as config_file:
            config_file.write(format_config)

        self.config_copy = self.parse_config()
        self.notify_observers('enabled')
