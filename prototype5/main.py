"""
Welcome to SyftBox, where we make plugin management as easy as eating ice cream!

This is our main file. It's like the ringmaster of our circus, keeping all the 
plugin clowns in check.
"""

import time
from plugin_manager import PluginManager

def main():
    # First, we create our plugin manager. It's like a zookeeper for our code animals.
    plugin_manager = PluginManager('./plugins')
    
    # Now we tell our zookeeper to round up all the code animals (plugins).
    plugin_manager.load_plugins()
    
    # Start the watchdog. It's like a guard dog, but for files. Woof!
    plugin_manager.start_watchdog()
    
    try:
        # This is where we pretend to do important stuff.
        # In reality, we're just taking a nap. Shhh, don't tell anyone!
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Uh oh, someone pressed Ctrl+C. Party's over, folks!
        print("Alright, alright, I'll stop. Sheesh.")
    finally:
        # Time to clean up. It's like telling your code to brush its teeth before bed.
        plugin_manager.cleanup()

if __name__ == "__main__":
    main()

"""
Next Steps:
-----------
Congratulations! You've survived the main.py file of SyftBox. If you're not questioning 
your life choices yet, proceed to plugin_manager.py. May the force be with you.
"""
