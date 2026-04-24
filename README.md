# rhino-codes

Open-source Rhino and Grasshopper scripts for architecture, fabrication, geometry processing, and Rhino workflow automation.

This repository is a working collection of standalone utilities rather than a single packaged application. Most files are meant to be run directly inside Rhino, Grasshopper, or Rhino Python with minimal setup.

## What is here

- Rhino scripts for import cleanup, object management, rendering helpers, and UI tools
- Grasshopper-oriented Python utilities
- Fabrication and steel helpers
- Form-finding experiments and mesh processing tools
- Small samples and RhinoCommon references

## Environment

The repo is mixed on purpose:

- some scripts are written for Rhino 8 Python 3
- some are classic Rhino Python scripts that rely on `rhinoscriptsyntax`
- several tools use RhinoCommon and Eto for dialogs and UI

Check the imports and header comments in each script before running it. A few tools are tightly tied to saved Rhino documents, document notes, block definitions, or specific project conventions.

## Repo layout

- `blocks/`
  - block inspection helpers and related UI assets
- `cnc plates/`
  - CNC layer and plate-prep utilities
- `data/`
  - metadata capture tools
- `data management/`
  - selection, filtering, and object-query helpers
- `files/`
  - import and deduplication workflows
- `formfinding/`
  - mesh and tensile form-finding experiments
- `import/`
  - Revit/DWG cleanup and deblocking utilities
- `logger/`
  - work logging tools that write alongside Rhino files
- `render/`
  - display and material helpers
- `rhino interface/`
  - lightweight Rhino UI and formatting tools
- `samples/`
  - reference scripts and RhinoCommon examples
- `steel/`
  - structural steel geometry helpers
- `sun/`
  - sun-study capture/output tools
- `tools/`
  - general cleanup and maintenance scripts

For a quick per-folder index, see [index.md](index.md).

## Featured scripts

### `blocks/code/get-block-data.py`

Grasshopper Rhino 8 Python 3 script that reads a placed block instance by GUID and returns:

- definition name
- user text keys and values
- transformed block geometry
- base plane

Basic setup in Grasshopper:

1. Add a Python 3 component.
2. Create one input named `G`.
3. Set `G` to `Guid` with `Item` access.
4. Create outputs named `Name`, `Keys`, `Values`, `Geometry`, and `BasePlane`.
5. Paste in the script and supply a placed block instance GUID.

### `logger/WorkLogger.py`

Rhino + Eto work logger that stores JSON log data next to the active Rhino file. Useful for time tracking, checkpoint notes, and lightweight project activity history.

### `formfinding/glvn-ff-main-01.py`

Interactive tensile form-finding tool with Eto-based settings and Rhino geometry processing for fabric and cable studies.

### `import/revit-based-dwg-deblocking-multiple+meshes+purge.py`

Import cleanup workflow for DWG/Revit-derived content, including block explosion, mesh handling, and cleanup/purge steps.

## How to use this repo

There is no install step for the repo as a whole. Pick a script and run it in the environment it expects:

- Rhino Python editor
- Grasshopper Python 3 component
- Rhino command/script runner

Good first checks before running any script:

1. Read the first 30 to 50 lines for imports, comments, and assumptions.
2. Confirm whether it expects Rhino 8 Python 3 or classic Rhino Python behavior.
3. Make sure the current Rhino document is saved if the script writes files or logs.
4. Duplicate important project files before using destructive cleanup scripts.

## Notes

- Folder names intentionally match workflow topics, including spaces in several directory names.
- Script naming is practical rather than standardized; version suffixes usually reflect in-progress iterations.
- `samples/` is reference material, while the other folders are project-facing utilities.

## License

Released under the MIT License. See [LICENSE](LICENSE).
