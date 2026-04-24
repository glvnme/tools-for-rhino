# Code Index

Quick map of the repository so it is easier to find the right script before opening Rhino.

## Root

- `README.md`: project overview, environment notes, and featured tools
- `index.md`: this folder-by-folder code map

## Folder guide

### `blocks/`

- `blocks/code/get-block-data.py`: Grasshopper Rhino 8 Python 3 script for reading block instance metadata, transformed geometry, and base plane from a GUID
- `blocks/ui components/get-block-data.html`: help or UI asset for the block data tool

### `cnc plates/`

- `make-cnc-layers-per-plate-th-v0.2.py`: builds CNC layer structures grouped by plate thickness

### `data/`

- `data/fabrics/fabrics-store-pocket-data-to-notes.py`: Eto dialog for capturing fabric pocket and seam data into Rhino document notes

### `data management/`

- `filter-select-dots.py`: collects text dots, groups/filter them by value and metadata, and supports selection workflows

### `files/`

- `import dedup.py`: imports external geometry while tracking existing object IDs to avoid duplicate additions

### `formfinding/`

- `glvn-ff-main-01.py`: tensile form-finding workflow with Eto settings and reaction display options
- `glvn-ff-main-surface-01.py`: surface-oriented form-finding variant
- `glvn-ff-main-surface-links-01-1.py`: surface + link based study variant
- `glvn-ff-main-surface-links-cable_links_01-2.py`: cable-link variation of the form-finding solver
- `glvn-ff-main-surface-links-cable_links_-ridge-01-3.py`: ridge-focused cable-link variation
- `smooth-mesh-to-tolerance.py`: mesh smoothing utility

### `import/`

- `revit-based-dwg-deblocking.py`: base deblocking workflow for imported DWG/Revit geometry
- `revit-based-dwg-deblocking-single.py`: single-target deblocking variant
- `revit-based-dwg-deblocking-multiple.py`: multiple-target deblocking variant
- `revit-based-dwg-deblocking-multiple+meshes.py`: multiple-target variant with mesh handling
- `revit-based-dwg-deblocking-multiple+meshes+purge.py`: cleanup variant with mesh handling and purge steps

### `logger/`

- `WorkLogger.py`: JSON-backed work logger tied to the active Rhino file
- `AutoLoader.py`: helper for loading or starting the work logger

### `render/`

- `match-material-color-to-object-color.py`: creates or reuses render materials based on object display color

### `rhino interface/`

- `display-object-name-0.1.py`: prints selected object names
- `length_ft_in_fr.py`: converts lengths to feet-inch-fraction strings
- `length_ft_in_fr_16.py`: feet-inch-fraction formatter tuned to sixteenth-inch output

### `samples/`

- Rhino Python and RhinoCommon examples for annotations, points, curves, layers, imports/exports, and basic scripting patterns

### `steel/`

- `generate-pipe-xs-0.01.py`: creates structural pipe geometry from predefined STD and XS sizes

### `sun/`

- `save_sun_image.py`: captures a sun-study image using Rhino sun settings and saved model context

### `tools/`

- `purge_blocks_list.py`: removes selected block definitions or instances and runs cleanup/purge steps

## Reading order

If you are new to the repo, a good sequence is:

1. Read `README.md`
2. Scan this index
3. Open the target script and read the header/comments before running it
