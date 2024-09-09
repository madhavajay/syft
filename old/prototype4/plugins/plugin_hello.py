import rumps

def run():
    response = rumps.Window("What's your name?", "Hello Plugin", default_text="World").run()
    name = response.text if response.text else "World"
    rumps.notification("Hello Plugin", "", f"Hello, {name}!")