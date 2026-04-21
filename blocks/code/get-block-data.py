"""
Grasshopper Rhino 8 Python 3 script: get block data from a block instance GUID.

How to use
1. Drop a Python 3 component onto the Grasshopper canvas in Rhino 8.
2. Create one input and name it `G`.
3. Set input `G` to:
   - Type hint: `Guid`
   - Access: `Item`
4. Create seven outputs with these exact names:
   - `Name`
   - `Keys`
   - `Values`
   - `Geometry`
   - `BasePlane`
   - `BlockLayerPath`
   - `ObjectLayerPaths`
5. Copy the script below into the Python 3 component editor.
6. Plug in the GUID of a block instance from the Rhino document.

What each output returns
- `Name`: block definition name
- `Keys`: user text keys stored on the block definition
- `Values`: user text values stored on the block definition
- `Geometry`: all block geometry transformed into world/model space
- `BasePlane`: placement plane of the selected block instance
- `BlockLayerPath`: full parent layer path of the placed block instance
- `ObjectLayerPaths`: full layer path for each item in `Geometry`, in matching order

Notes
- This expects the GUID of a placed block instance, not regular geometry.
- If your Grasshopper input is still the default `x`, this script also accepts `x`.
- If metadata is stored on the placed instance instead of the block definition,
  replace `idef.GetUserStrings()` with `instance.Attributes.GetUserStrings()`.
"""

import Rhino
import System
from Rhino.DocObjects import InstanceObject
from Rhino.Geometry import Plane


def get_layer_full_path(doc, layer_index):
    if layer_index < 0:
        return None

    layer = doc.Layers.FindIndex(layer_index)
    if layer is None:
        return None

    return layer.FullPath


def collect_block_geometry(doc, idef, accumulated_xform, geometry_list, object_layer_paths):
    objects = idef.GetObjects()
    if not objects:
        return

    for obj in objects:
        if obj is None:
            continue

        if isinstance(obj, InstanceObject):
            nested_xform = accumulated_xform * obj.InstanceXform
            collect_block_geometry(
                doc,
                obj.InstanceDefinition,
                nested_xform,
                geometry_list,
                object_layer_paths,
            )
            continue

        geo = obj.Geometry
        if geo is None:
            continue

        dup = geo.Duplicate()
        if dup is None:
            continue

        dup.Transform(accumulated_xform)
        geometry_list.append(dup)
        object_layer_paths.append(get_layer_full_path(doc, obj.Attributes.LayerIndex))


Name = None
Keys = []
Values = []
Geometry = []
BasePlane = None
BlockLayerPath = None
ObjectLayerPaths = []

guid_in = globals().get("G", globals().get("guid", globals().get("x", None)))

if guid_in is None:
    raise Exception("No input found. Rename the input to 'G' or use 'guid' or the default input name 'x'.")

doc = Rhino.RhinoDoc.ActiveDoc
if doc is None:
    raise Exception("No active Rhino document.")

if isinstance(guid_in, str):
    guid_in = System.Guid.Parse(guid_in)

if guid_in == System.Guid.Empty:
    raise Exception("Input GUID is empty.")

rh_obj = doc.Objects.FindId(guid_in)
if rh_obj is None:
    raise Exception("Object not found.")

if not isinstance(rh_obj, InstanceObject):
    raise Exception("GUID is not a block instance.")

instance = rh_obj
idef = instance.InstanceDefinition

if idef is None:
    raise Exception("Instance definition not found.")

Name = idef.Name
BlockLayerPath = get_layer_full_path(doc, instance.Attributes.LayerIndex)

user_strings = idef.GetUserStrings()
if user_strings:
    for key in user_strings.AllKeys:
        Keys.append(key)
        Values.append(user_strings[key])

BasePlane = Plane.WorldXY
BasePlane.Transform(instance.InstanceXform)

collect_block_geometry(doc, idef, instance.InstanceXform, Geometry, ObjectLayerPaths)
