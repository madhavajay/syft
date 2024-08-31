import rumps
import os
import importlib

class SimplePluginManager:
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.plugins = []

    def load_plugins(self):
        for filename in os.listdir(self.plugin_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]
                module = importlib.import_module(f"plugins.{module_name}")
                if hasattr(module, 'run'):
                    self.plugins.append(module.run)

    def run_plugins(self):
        for plugin in self.plugins:
            plugin()

class SimpleApp(rumps.App):
    def __init__(self):
        super(SimpleApp, self).__init__("SimpleApp")
        self.plugin_manager = SimplePluginManager("plugins")
        self.plugin_manager.load_plugins()
        self.menu = ["Run Plugins"]

    @rumps.clicked("Run Plugins")
    def run_plugins(self, _):
        self.plugin_manager.run_plugins()

if __name__ == "__main__":
    SimpleApp().run()