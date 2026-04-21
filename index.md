# Code Index

Short overview of where the code lives and what it does.

## Root

- `README.md`: project overview for Rhino 8 and Grasshopper scripts.
- `index.md`: this quick code map.

## Main Folders

- `blocks/`: block-related tools.
  - `blocks/code/get-block-data.py`: Grasshopper Python 3 script that reads a block instance by GUID and returns block name, user text, geometry, and base plane.
  - `blocks/ui components/get-block-data.html`: UI/help asset for the block data tool.

- `cnc plates/`: CNC prep helpers for steel plates.
  - `make-cnc-layers-per-plate-th-v0.2.py`: creates dated CNC layer trees by selected plate thickness.

- `data/`: data capture and metadata utilities.
  - `data/fabrics/fabrics-store-pocket-data-to-notes.py`: Eto-based dialog for recording fabric pocket and seam data into document notes.

- `data management/`: object filtering and selection helpers.
  - `filter-select-dots.py`: finds and filters text dots by name/type metadata and supports selection workflows.

- `files/`: file import/report utilities.
  - `import dedup.py`: imports geometry while tracking existing object IDs to avoid duplicate results.

- `formfinding/`: tensile and mesh form-finding experiments/tools.
  - `glvn-ff-main-01.py` and related `glvn-*` scripts: form-finding solvers and surface/cable-link variants.
  - `smooth-mesh-to-tolerance.py`: mesh smoothing utility.

- `import/`: Rhino import cleanup tools, mainly for Revit/DWG workflows.
  - `revit-based-dwg-deblocking*.py`: explodes nested blocks, extracts raw geometry, and in some cases joins meshes / purges imports.

- `logger/`: work logging utilities tied to Rhino files.
  - `WorkLogger.py`: UI + JSON logger for tracking work sessions alongside a Rhino document.
  - `AutoLoader.py`: helper for loading or starting the logger workflow.

- `render/`: rendering/material helpers.
  - `match-material-color-to-object-color.py`: creates or reuses materials based on object display color.

- `rhino interface/`: small UI and display helpers.
  - `display-object-name-0.1.py`: prints selected object names.
  - `length_ft_in_fr.py` and `length_ft_in_fr_16.py`: length formatting helpers for feet/inches/fractions.

- `samples/`: reference/example Rhino Python scripts.
  - Contains small demos for annotation, points, curves, layers, import/export, and RhinoCommon interaction.

- `steel/`: steel geometry creation tools.
  - `generate-pipe-xs-0.01.py`: creates structural pipe geometry from selected pipe sizes and axis points.

- `sun/`: sun-study output tools.
  - `save_sun_image.py`: captures a sun-study image using Rhino sun panel settings and saved model context.

- `tools/`: general maintenance utilities.
  - `purge_blocks_list.py`: removes block definitions/instances and runs a purge cleanup.

## Summary

This repo is mostly a collection of standalone Rhino / Grasshopper scripts grouped by workflow: blocks, import cleanup, form-finding, fabrication, rendering, UI helpers, and project logging.
