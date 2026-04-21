import Rhino
import scriptcontext as sc
import os

# POINT THIS TO YOUR MAIN LOGGER SCRIPT
SCRIPT_PATH = r"C:\Users\fargrik\AppData\Roaming\McNeel\Rhinoceros\8.0\scripts\logger\WorkLogger.py"

def run_the_logger():
    if os.path.exists(SCRIPT_PATH):
        Rhino.RhinoApp.RunScript('_-RunPythonScript "{}"'.format(SCRIPT_PATH), False)

def OnEndOpenDocument(sender, e):
    # This triggers when a file finishes opening
    run_the_logger()

def OnNewDocument(sender, e):
    # This triggers when you create a new empty file
    run_the_logger()

# Check if we have already assigned the event watcher so we don't duplicate it
if "MyWorkLog_Watcher" not in sc.sticky:
    # 1. Add the events
    Rhino.RhinoDoc.EndOpenDocument += OnEndOpenDocument
    Rhino.RhinoDoc.NewDocument += OnNewDocument
    
    # 2. Mark as running
    sc.sticky["MyWorkLog_Watcher"] = True
    
    # 3. Run it once for the currently open file
    run_the_logger()
    
    print("Work Logger Auto-Loader Active.")