"""
Rhino 8 script: export all currently visible objects in the active document
to a new standalone Rhino 3DM file.

What it does
- Collects globally visible objects from the active document.
- Includes Worksession reference objects.
- Bakes block instances into plain geometry for a self-contained result.
- Recreates the layer hierarchy used by the exported geometry.
- Stores source IDs as object user text for traceability.

Notes
- "Visible" means visible in the document state: object visible and layer visible.
  It does not try to match clipping or occlusion in a specific viewport.
- Render materials, custom linetypes, groups, and annotation styles are not fully
  reconstructed in the target file.
- The script is written to stay friendly to Rhino 8 CPython 3 and legacy
  IronPython-style execution in the ScriptEditor / EditPythonScript workflows.
"""

import os

import Rhino
import System
import rhinoscriptsyntax as rs


EXPORT_VERSION = 8


def get_active_doc():
    doc = Rhino.RhinoDoc.ActiveDoc
    if doc is None:
        raise RuntimeError("No active Rhino document.")
    return doc


def prompt_output_path(doc):
    base_name = "visible-export.3dm"
    if doc.Name:
        stem = os.path.splitext(doc.Name)[0]
        if stem:
            base_name = stem + "_visible.3dm"

    folder = None
    if doc.Path:
        folder = os.path.dirname(doc.Path)

    return rs.SaveFileName(
        "Save visible objects as Rhino file",
        "Rhino 3D Models (*.3dm)|*.3dm||",
        folder,
        base_name,
        "3dm",
    )


def ask_open_in_new_instance(output_path):
    message = "Saved file:\n{0}\n\nOpen it in a new Rhino instance now?".format(
        output_path
    )
    return rs.MessageBox(message, 4 + 32, "Export Complete") == 6


def get_rhino_executable_path():
    process = System.Diagnostics.Process.GetCurrentProcess()
    main_module = getattr(process, "MainModule", None)
    if main_module is None:
        return None
    return main_module.FileName


def open_file_in_new_rhino_instance(output_path):
    rhino_exe = get_rhino_executable_path()
    if not rhino_exe:
        raise RuntimeError("Could not determine the Rhino executable path.")

    start_info = System.Diagnostics.ProcessStartInfo()
    start_info.FileName = rhino_exe
    start_info.Arguments = '"{0}"'.format(output_path)
    start_info.WorkingDirectory = os.path.dirname(output_path)
    start_info.UseShellExecute = True

    started = System.Diagnostics.Process.Start(start_info)
    if started is None:
        raise RuntimeError("Rhino did not start a new instance.")


def copy_model_settings(source_doc, target_doc):
    target_doc.ModelUnitSystem = source_doc.ModelUnitSystem
    target_doc.ModelAbsoluteTolerance = source_doc.ModelAbsoluteTolerance
    target_doc.ModelRelativeTolerance = source_doc.ModelRelativeTolerance
    target_doc.ModelAngleToleranceDegrees = source_doc.ModelAngleToleranceDegrees

    target_doc.PageUnitSystem = source_doc.PageUnitSystem
    target_doc.PageAbsoluteTolerance = source_doc.PageAbsoluteTolerance
    target_doc.PageRelativeTolerance = source_doc.PageRelativeTolerance
    target_doc.PageAngleToleranceDegrees = source_doc.PageAngleToleranceDegrees


def get_doc_object_list(doc):
    settings = Rhino.DocObjects.ObjectEnumeratorSettings()

    if hasattr(settings, "ActiveObjects"):
        settings.ActiveObjects = True
    if hasattr(settings, "ReferenceObjects"):
        settings.ReferenceObjects = True
    if hasattr(settings, "VisibleFilter"):
        settings.VisibleFilter = True
    if hasattr(settings, "DeletedObjects"):
        settings.DeletedObjects = False
    if hasattr(settings, "HiddenObjects"):
        settings.HiddenObjects = False
    if hasattr(settings, "IdefObjects"):
        settings.IdefObjects = False
    if hasattr(settings, "IncludeGrips"):
        settings.IncludeGrips = False
    if hasattr(settings, "IncludeLights"):
        settings.IncludeLights = False
    if hasattr(settings, "NormalObjects"):
        settings.NormalObjects = True
    if hasattr(settings, "LockedObjects"):
        settings.LockedObjects = True

    objects = []
    for rh_obj in doc.Objects.GetObjectList(settings):
        if rh_obj is None:
            continue
        if rh_obj.IsDeleted:
            continue
        objects.append(rh_obj)
    return objects


def get_layer_by_index(doc, layer_index):
    if layer_index < 0:
        return None
    return doc.Layers.FindIndex(layer_index)


def is_layer_visible(doc, layer_index):
    layer = get_layer_by_index(doc, layer_index)
    if layer is None:
        return True

    current = layer
    while current is not None:
        try:
            if not current.IsVisible:
                return False
        except Exception:
            pass

        parent_id = getattr(current, "ParentLayerId", System.Guid.Empty)
        if parent_id == System.Guid.Empty:
            break
        current = doc.Layers.FindId(parent_id)

    return True


def duplicate_geometry(geometry):
    if geometry is None:
        return None

    if hasattr(geometry, "Duplicate"):
        dup = geometry.Duplicate()
        if dup is not None:
            return dup

    return None


def duplicate_layer(source_layer):
    if source_layer is None:
        return None

    if hasattr(source_layer, "Duplicate"):
        dup = source_layer.Duplicate()
        if dup is not None:
            return dup

    layer = Rhino.DocObjects.Layer()
    layer.Name = source_layer.Name
    layer.Color = source_layer.Color
    layer.IsVisible = source_layer.IsVisible
    layer.IsLocked = source_layer.IsLocked

    for attr_name in ("PlotColor", "PlotWeight", "PersistentVisibility", "PersistentLocking"):
        if hasattr(source_layer, attr_name) and hasattr(layer, attr_name):
            try:
                setattr(layer, attr_name, getattr(source_layer, attr_name))
            except Exception:
                pass

    return layer


def ensure_layer(source_doc, target_doc, source_layer_index, layer_map):
    if source_layer_index in layer_map:
        return layer_map[source_layer_index]

    source_layer = get_layer_by_index(source_doc, source_layer_index)
    if source_layer is None:
        return 0

    parent_target_index = -1
    parent_id = getattr(source_layer, "ParentLayerId", System.Guid.Empty)
    if parent_id != System.Guid.Empty:
        parent_layer = source_doc.Layers.FindId(parent_id)
        if parent_layer is not None:
            parent_target_index = ensure_layer(
                source_doc, target_doc, parent_layer.Index, layer_map
            )

    layer_copy = duplicate_layer(source_layer)
    if layer_copy is None:
        return 0

    if parent_target_index >= 0:
        parent_target_layer = target_doc.Layers[parent_target_index]
        layer_copy.ParentLayerId = parent_target_layer.Id
    else:
        layer_copy.ParentLayerId = System.Guid.Empty

    if hasattr(layer_copy, "RenderMaterialIndex"):
        layer_copy.RenderMaterialIndex = -1
    if hasattr(layer_copy, "LinetypeIndex"):
        layer_copy.LinetypeIndex = -1

    new_index = target_doc.Layers.Add(layer_copy)
    if new_index < 0:
        try:
            new_index = target_doc.Layers.FindByFullPath(source_layer.FullPath, -1)
        except Exception:
            new_index = 0

    layer_map[source_layer_index] = new_index
    return new_index


def make_object_attributes(source_doc, target_doc, source_attrs, layer_map, metadata):
    attrs = source_attrs.Duplicate()
    attrs.LayerIndex = ensure_layer(
        source_doc, target_doc, source_attrs.LayerIndex, layer_map
    )

    if hasattr(attrs, "RemoveFromAllGroups"):
        attrs.RemoveFromAllGroups()

    if hasattr(attrs, "MaterialIndex"):
        attrs.MaterialIndex = -1
    if hasattr(attrs, "LinetypeIndex"):
        attrs.LinetypeIndex = -1

    if metadata:
        for key, value in metadata.items():
            if value is None:
                continue
            attrs.SetUserString(key, str(value))

    return attrs


def add_geometry_object(target_doc, geometry, attributes):
    try:
        return target_doc.Objects.Add(geometry, attributes)
    except Exception:
        return System.Guid.Empty


def export_plain_object(source_doc, target_doc, rh_obj, layer_map):
    geometry = duplicate_geometry(rh_obj.Geometry)
    if geometry is None:
        return 0

    source_layer = get_layer_by_index(source_doc, rh_obj.Attributes.LayerIndex)
    metadata = {
        "ExportSourceKind": "object",
        "ExportSourceObjectId": rh_obj.Id,
        "ExportSourceLayerPath": source_layer.FullPath if source_layer else "",
        "ExportSourceIsReference": rh_obj.IsReference,
    }
    attrs = make_object_attributes(
        source_doc, target_doc, rh_obj.Attributes, layer_map, metadata
    )
    result_id = add_geometry_object(target_doc, geometry, attrs)
    if result_id == System.Guid.Empty:
        return 0
    return 1


def export_instance_definition(
    source_doc,
    target_doc,
    instance_definition,
    accumulated_xform,
    layer_map,
    source_instance_id,
    source_is_reference,
):
    if instance_definition is None:
        return 0

    count = 0
    definition_objects = instance_definition.GetObjects()
    if not definition_objects:
        return 0

    for child in definition_objects:
        if child is None:
            continue
        if hasattr(child, "IsHidden") and child.IsHidden:
            continue
        if hasattr(child.Attributes, "Visible") and not child.Attributes.Visible:
            continue

        if isinstance(child, Rhino.DocObjects.InstanceObject):
            nested_xform = accumulated_xform * child.InstanceXform
            count += export_instance_definition(
                source_doc,
                target_doc,
                child.InstanceDefinition,
                nested_xform,
                layer_map,
                source_instance_id,
                source_is_reference,
            )
            continue

        if not is_layer_visible(source_doc, child.Attributes.LayerIndex):
            continue

        geometry = duplicate_geometry(child.Geometry)
        if geometry is None:
            continue

        geometry.Transform(accumulated_xform)

        child_layer = get_layer_by_index(source_doc, child.Attributes.LayerIndex)
        metadata = {
            "ExportSourceKind": "block_member",
            "ExportSourceObjectId": child.Id,
            "ExportSourceBlockInstanceId": source_instance_id,
            "ExportSourceLayerPath": child_layer.FullPath if child_layer else "",
            "ExportSourceIsReference": source_is_reference,
        }
        attrs = make_object_attributes(
            source_doc, target_doc, child.Attributes, layer_map, metadata
        )
        result_id = add_geometry_object(target_doc, geometry, attrs)
        if result_id != System.Guid.Empty:
            count += 1

    return count


def export_visible_objects(source_doc, target_doc):
    layer_map = {}
    objects = get_doc_object_list(source_doc)

    exported_count = 0
    source_count = 0
    block_count = 0

    for rh_obj in objects:
        source_count += 1

        if isinstance(rh_obj, Rhino.DocObjects.InstanceObject):
            block_count += 1
            exported_count += export_instance_definition(
                source_doc,
                target_doc,
                rh_obj.InstanceDefinition,
                rh_obj.InstanceXform,
                layer_map,
                rh_obj.Id,
                rh_obj.IsReference,
            )
            continue

        exported_count += export_plain_object(
            source_doc, target_doc, rh_obj, layer_map
        )

    return source_count, block_count, exported_count


def main():
    doc = get_active_doc()
    output_path = prompt_output_path(doc)
    if not output_path:
        print("Export cancelled.")
        return

    target_doc = Rhino.RhinoDoc.CreateHeadless(None)

    try:
        copy_model_settings(doc, target_doc)
        source_count, block_count, exported_count = export_visible_objects(doc, target_doc)

        if exported_count == 0:
            print("No visible objects were exported.")
            return

        success = target_doc.SaveAs(output_path, EXPORT_VERSION)
        if not success:
            raise RuntimeError("Rhino could not save the exported file.")

        print(
            "Saved {0} objects from {1} visible source objects to:\n{2}".format(
                exported_count, source_count, output_path
            )
        )
        if block_count > 0:
            print(
                "Flattened {0} visible block instance{1} into plain geometry.".format(
                    block_count, "" if block_count == 1 else "s"
                )
            )

        if ask_open_in_new_instance(output_path):
            open_file_in_new_rhino_instance(output_path)
            print("Opened exported file in a new Rhino instance.")
    finally:
        target_doc.Dispose()


if __name__ == "__main__":
    main()
