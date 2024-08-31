"""
Welcome to SyftBox, where we make plugin management as easy as eating ice cream!

This is our main file. It's like the ringmaster of our circus, keeping all the 
plugin clowns in check.

Step 1: Import necessary modules
--------------------------------
We import the time module for our main loop and the PluginManager class which will
handle all our plugin-related operations.
"""

import time
from plugin_manager import PluginManager

def main():
    """
    Step 2: Define the main function
    --------------------------------
    This is the heart of our application. It sets up the PluginManager,
    loads plugins, starts the watchdog, and keeps the application running.
    """

    # Step 3: Create the PluginManager
    # --------------------------------
    # We create an instance of PluginManager, giving it the path to our plugins directory.
    # This is like hiring a zookeeper for our code animals (plugins).
    plugin_manager = PluginManager('./plugins')
    
    # Step 4: Load Plugins
    # --------------------
    # We tell our PluginManager to find and load all available plugins in the specified directory.
    # This is like the zookeeper rounding up all the animals for the day's show.
    plugin_manager.load_plugins()
    
    # Step 5: Start the Watchdog
    # --------------------------
    # We start a watchdog that will monitor our plugins directory for changes.
    # If any changes occur (like adding, modifying, or deleting plugin files),
    # the watchdog will notify the PluginManager to take appropriate action.
    # It's like having a guard dog that watches for any new or misbehaving animals.
    plugin_manager.start_watchdog()
    
    try:
        # Step 6: Enter the Main Loop
        # ---------------------------
        # This is where we keep our application running indefinitely.
        # In a more complex application, you might have more logic here.
        # For now, we're just taking a nap every second.
        while True:
            # Sleep for 1 second. This prevents the loop from consuming too much CPU.
            time.sleep(1)
    except KeyboardInterrupt:
        # Step 7: Handle Interruption
        # ---------------------------
        # If the user presses Ctrl+C, we catch the KeyboardInterrupt here.
        # This allows us to exit the program gracefully.
        print("Alright, alright, I'll stop. Sheesh.")
    finally:
        # Step 8: Cleanup
        # ---------------
        # Whether the program ends normally or due to an interruption,
        # we always want to clean up our resources.
        # This is like telling the zookeeper to make sure all the animals
        # are back in their cages before going home.
        plugin_manager.cleanup()

# Step 9: Run the Main Function
# -----------------------------
# This is a common Python idiom. It checks if this script is being run directly
# (as opposed to being imported as a module). If it is being run directly,
# it calls the main() function to start the application.
if __name__ == "__main__":
    main()

"""
Next Steps:
-----------
Congratulations! You've survived the main.py file of SyftBox. 
Here's what happens next:

1. The PluginManager takes over, loading plugins from the './plugins' directory.
2. Each plugin is initialized and starts running in its own thread.
3. The Watchdog keeps an eye on the plugins directory for any changes.
4. The main loop keeps the application alive, allowing plugins to run continuously.
5. When you stop the application (Ctrl+C), it cleans up all resources before exiting.

If you're not questioning your life choices yet, proceed to plugin_manager.py 
to dive deeper into how plugins are managed. May the force be with you!
"""
