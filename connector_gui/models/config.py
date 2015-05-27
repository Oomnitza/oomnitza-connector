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
            if not selected in self.observers['enabled']:
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
                    if not field in self.config[section]:
                        section_config[section].append((field, dynamic_config[section][field]))

        format_config = format_sections_for_ini(section_config)
        wrap_config = ""

        for line in format_config.split("\n"):
            if line.count("=") == 1:
                field, value = line.split("=")
                field = field.rstrip()
                value = value.lstrip()
                if "[u'" in value and "']" in value:
                    if value.count(",") > 0:
                        value = value.replace("[u'", "")
                        value = value.replace("']", "")
                        value = value.replace("u'", "")
                        value = value.replace("'", "")
                        values = value.split(",")
                        val_str = ""
                        for val in values:
                            val_str += "\"{0}\",".format(val.lstrip())
                        value = "[{0}]".format(val_str[:-1])
                    else:
                        value = value.replace("[u'", "")
                        value = value.replace("']", "")
                        value = '["{0}"]'.format(value)
                elif "{u'" in value and "'}" in value:
                    values = value.replace("{", "").replace("}", "").split(",")
                    val_str = ""
                    for val in values:
                        if val.count(":") == 1:
                            k, v = val.split(":")
                            k = k.lstrip().rstrip().replace("u'", "").replace("'", "")
                            v = v.lstrip().rstrip().replace("u'", "").replace("'", "")
                            val_str += '"{0}":"{1}",'.format(k, v)
                    value = '{%s}' % val_str[:-1]
                line = "{0} = {1}".format(field, value)
            elif line.count("=") == 0 and line and not '[' in line and ']' not in line:
                line = "{0} =".format(line)
            wrap_config += "{0}\n".format(line)

        with open(path, 'w') as config_file:
            config_file.write(wrap_config)

        self.config_copy = self.parse_config()
        self.notify_observers('enabled')