# tools-for-rhino

Open-source Rhino 8 and Grasshopper scripts for architectural and geometry workflows.

## Current tools

### `blocks/get-block-data.py`

Grasshopper Rhino 8 Python 3 script that reads a block instance by GUID and returns:

- block definition name
- user text keys
- user text values
- transformed block geometry
- block base plane

## Usage

1. Open Rhino 8 and Grasshopper.
2. Drop a Python 3 component onto the Grasshopper canvas.
3. Add one input named `G`.
4. Set input `G` to:
   - Type hint: `Guid`
   - Access: `Item`
5. Add five outputs named:
   - `Name`
   - `Keys`
   - `Values`
   - `Geometry`
   - `BasePlane`
6. Paste the script from `blocks/get-block-data.py` into the Python 3 component.
7. Provide the GUID of a placed block instance from the Rhino document.

## Notes

- This script expects a placed block instance, not regular Rhino geometry.
- It works in Rhino 8 Python 3.
- More utilities can be added here over time under topic-based folders.

### `WorkSession/export-visible-to-3dm.py`

Rhino 8 ScriptEditor / EditPythonScript utility that:

- collects all currently visible objects from the active document
- includes Worksession reference objects
- bakes visible block instances into plain geometry
- recreates the used layer hierarchy
- writes a standalone `.3dm` with source IDs stored as user text
