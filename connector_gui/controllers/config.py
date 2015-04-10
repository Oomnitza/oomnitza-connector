from connector_gui.views.config import ConfigView


class ConfigController:

    def __init__(self, model):
        self.model = model
        self.view = ConfigView(self, model)

    def edit_config(self, field, selected, value):
        self.model.set_config(field, selected, value)

    def save_config(self):
        self.model.save_config()
