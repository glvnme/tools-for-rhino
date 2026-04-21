"""
Rhino 8 script: export all currently visible objects in the active document
to a new standalone Rhino 3DM file.

What it does
- Collects globally visible objects from the active document.
- Includes Worksession reference objects.
- Places active-file layers under a new parent layer named after the active file.
- Keeps referenced Worksession layers exactly as they appear in the current model.
- Bakes block instances into plain geometry for a self-contained result.
- Stores source IDs as object user text for traceability.
- Shows estimated per-source file-size contribution stats before asking to open.

Notes
- "Visible" means visible in the document state: object visible and layer visible.
  It does not try to match clipping or occlusion in a specific viewport.
- Size percentages are estimates inferred from per-source standalone exports.
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


def get_model_label(file_path, fallback_name):
    if file_path:
        name = os.path.splitext(os.path.basename(file_path))[0]
        if name:
            return name

    if fallback_name:
        name = os.path.splitext(os.path.basename(fallback_name))[0]
        if name:
            return name

    return "ActiveModel"


def get_active_source_info(doc):
    label = get_model_label(doc.Path, doc.Name)
    if doc.Path:
        key = doc.Path
    else:
        key = "active::{0}".format(label)

    return {
        "key": key,
        "label": label,
        "path": doc.Path,
        "is_active": True,
        "serial": None,
    }


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


def ask_open_in_new_instance(message):
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


def create_export_item(geometry, source_attrs, metadata, source_info):
    return {
        "geometry": geometry,
        "attributes": source_attrs.Duplicate(),
        "metadata": metadata,
        "source_key": source_info["key"],
        "source_label": source_info["label"],
        "source_path": source_info["path"],
        "source_serial": source_info["serial"],
        "is_active_source": source_info["is_active"],
    }


def get_reference_source_info(doc, serial_number, ref_path_cache):
    if serial_number in ref_path_cache:
        model_path = ref_path_cache[serial_number]
    else:
        model_path = None
        if serial_number:
            try:
                model_path = doc.Worksession.ModelPathFromSerialNumber(serial_number)
            except Exception:
                model_path = None
        ref_path_cache[serial_number] = model_path

    label = get_model_label(model_path, "Reference_{0}".format(serial_number))
    key = model_path or "reference::{0}".format(serial_number)

    return {
        "key": key,
        "label": label,
        "path": model_path,
        "is_active": False,
        "serial": serial_number,
    }


def get_source_info_for_object(doc, rh_obj, active_source_info, ref_path_cache):
    if getattr(rh_obj, "IsReference", False):
        serial_number = getattr(rh_obj, "ReferenceModelSerialNumber", 0)
        return get_reference_source_info(doc, serial_number, ref_path_cache)
    return active_source_info


def collect_plain_object(source_doc, rh_obj, source_info, items):
    geometry = duplicate_geometry(rh_obj.Geometry)
    if geometry is None:
        return 0

    source_layer = get_layer_by_index(source_doc, rh_obj.Attributes.LayerIndex)
    metadata = {
        "ExportSourceKind": "object",
        "ExportSourceObjectId": rh_obj.Id,
        "ExportSourceLayerPath": source_layer.FullPath if source_layer else "",
        "ExportSourceIsReference": rh_obj.IsReference,
        "ExportSourceModel": source_info["label"],
        "ExportSourceModelPath": source_info["path"] or "",
    }
    items.append(create_export_item(geometry, rh_obj.Attributes, metadata, source_info))
    return 1


def collect_instance_definition(
    source_doc,
    instance_definition,
    accumulated_xform,
    source_instance_id,
    source_info,
    items,
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
            count += collect_instance_definition(
                source_doc,
                child.InstanceDefinition,
                nested_xform,
                source_instance_id,
                source_info,
                items,
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
            "ExportSourceIsReference": source_info["is_active"] is False,
            "ExportSourceModel": source_info["label"],
            "ExportSourceModelPath": source_info["path"] or "",
        }
        items.append(create_export_item(geometry, child.Attributes, metadata, source_info))
        count += 1

    return count


def collect_export_items(source_doc):
    active_source_info = get_active_source_info(source_doc)
    ref_path_cache = {}
    items = []

    source_count = 0
    block_count = 0

    for rh_obj in get_doc_object_list(source_doc):
        source_count += 1
        source_info = get_source_info_for_object(
            source_doc, rh_obj, active_source_info, ref_path_cache
        )

        if isinstance(rh_obj, Rhino.DocObjects.InstanceObject):
            block_count += 1
            collect_instance_definition(
                source_doc,
                rh_obj.InstanceDefinition,
                rh_obj.InstanceXform,
                rh_obj.Id,
                source_info,
                items,
            )
            continue

        collect_plain_object(source_doc, rh_obj, source_info, items)

    return active_source_info, items, source_count, block_count


def ensure_active_parent_layer(target_doc, layer_name):
    if not layer_name:
        return -1

    layer = Rhino.DocObjects.Layer()
    layer.Name = layer_name

    new_index = target_doc.Layers.Add(layer)
    if new_index >= 0:
        return new_index

    try:
        return target_doc.Layers.FindByFullPath(layer_name, -1)
    except Exception:
        return -1


def ensure_layer(
    source_doc,
    target_doc,
    source_layer_index,
    layer_map,
    active_parent_index,
    nest_under_active_parent,
):
    cache_key = (source_layer_index, nest_under_active_parent)
    if cache_key in layer_map:
        return layer_map[cache_key]

    source_layer = get_layer_by_index(source_doc, source_layer_index)
    if source_layer is None:
        if nest_under_active_parent and active_parent_index >= 0:
            return active_parent_index
        return 0

    parent_target_index = -1
    parent_id = getattr(source_layer, "ParentLayerId", System.Guid.Empty)
    if parent_id != System.Guid.Empty:
        parent_layer = source_doc.Layers.FindId(parent_id)
        if parent_layer is not None:
            parent_target_index = ensure_layer(
                source_doc,
                target_doc,
                parent_layer.Index,
                layer_map,
                active_parent_index,
                nest_under_active_parent,
            )

    layer_copy = duplicate_layer(source_layer)
    if layer_copy is None:
        if nest_under_active_parent and active_parent_index >= 0:
            return active_parent_index
        return 0

    if parent_target_index >= 0:
        parent_target_layer = target_doc.Layers[parent_target_index]
        layer_copy.ParentLayerId = parent_target_layer.Id
    elif nest_under_active_parent and active_parent_index >= 0:
        active_parent_layer = target_doc.Layers[active_parent_index]
        layer_copy.ParentLayerId = active_parent_layer.Id
    else:
        layer_copy.ParentLayerId = System.Guid.Empty

    if hasattr(layer_copy, "RenderMaterialIndex"):
        layer_copy.RenderMaterialIndex = -1
    if hasattr(layer_copy, "LinetypeIndex"):
        layer_copy.LinetypeIndex = -1

    new_index = target_doc.Layers.Add(layer_copy)
    if new_index < 0:
        try:
            new_index = target_doc.Layers.FindByFullPath(layer_copy.FullPath, -1)
        except Exception:
            new_index = 0

    layer_map[cache_key] = new_index
    return new_index


def make_object_attributes(
    source_doc, target_doc, item, layer_map, active_parent_index
):
    attrs = item["attributes"].Duplicate()
    attrs.LayerIndex = ensure_layer(
        source_doc,
        target_doc,
        item["attributes"].LayerIndex,
        layer_map,
        active_parent_index,
        item["is_active_source"],
    )

    if hasattr(attrs, "RemoveFromAllGroups"):
        attrs.RemoveFromAllGroups()

    if hasattr(attrs, "MaterialIndex"):
        attrs.MaterialIndex = -1
    if hasattr(attrs, "LinetypeIndex"):
        attrs.LinetypeIndex = -1

    for key, value in item["metadata"].items():
        if value is None:
            continue
        attrs.SetUserString(key, str(value))

    return attrs


def add_geometry_object(target_doc, geometry, attributes):
    try:
        return target_doc.Objects.Add(geometry, attributes)
    except Exception:
        return System.Guid.Empty


def write_items_to_doc(source_doc, target_doc, items, active_layer_name):
    layer_map = {}
    active_parent_index = -1

    if any(item["is_active_source"] for item in items):
        active_parent_index = ensure_active_parent_layer(target_doc, active_layer_name)

    count = 0
    for item in items:
        geometry = duplicate_geometry(item["geometry"])
        if geometry is None:
            continue

        attrs = make_object_attributes(
            source_doc, target_doc, item, layer_map, active_parent_index
        )
        result_id = add_geometry_object(target_doc, geometry, attrs)
        if result_id != System.Guid.Empty:
            count += 1

    return count


def format_bytes(size_in_bytes):
    units = ["B", "KB", "MB", "GB"]
    value = float(size_in_bytes)
    unit_index = 0

    while value >= 1024.0 and unit_index < len(units) - 1:
        value /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return "{0} {1}".format(int(value), units[unit_index])
    return "{0:.2f} {1}".format(value, units[unit_index])


def fit_table_text(value, width):
    text = value or ""
    if len(text) <= width:
        return text.ljust(width)
    if width <= 3:
        return text[:width]
    return (text[: width - 3] + "...").ljust(width)


def get_temp_stats_folder():
    temp_root = System.IO.Path.GetTempPath()
    folder_name = "rhino_export_stats_{0}".format(System.Guid.NewGuid().ToString("N"))
    return System.IO.Path.Combine(temp_root, folder_name)


def save_doc_and_get_size(target_doc, file_path):
    success = target_doc.SaveAs(file_path, EXPORT_VERSION)
    if not success:
        raise RuntimeError("Rhino could not save a temporary stats file.")
    return os.path.getsize(file_path)


def compute_source_contribution_stats(source_doc, items, active_layer_name):
    grouped = {}
    for item in items:
        key = item["source_key"]
        if key not in grouped:
            grouped[key] = {
                "label": item["source_label"],
                "path": item["source_path"],
                "items": [],
            }
        grouped[key]["items"].append(item)

    if not grouped:
        return []

    temp_folder = get_temp_stats_folder()
    System.IO.Directory.CreateDirectory(temp_folder)

    try:
        baseline_doc = Rhino.RhinoDoc.CreateHeadless(None)
        try:
            copy_model_settings(source_doc, baseline_doc)
            baseline_path = System.IO.Path.Combine(temp_folder, "baseline.3dm")
            baseline_size = save_doc_and_get_size(baseline_doc, baseline_path)
        finally:
            baseline_doc.Dispose()

        stats = []
        ordered_groups = sorted(grouped.values(), key=lambda group: group["label"].lower())

        for index, group in enumerate(ordered_groups):
            group_doc = Rhino.RhinoDoc.CreateHeadless(None)
            try:
                copy_model_settings(source_doc, group_doc)
                object_count = write_items_to_doc(
                    source_doc, group_doc, group["items"], active_layer_name
                )
                group_path = System.IO.Path.Combine(
                    temp_folder, "group_{0:03d}.3dm".format(index)
                )
                group_size = save_doc_and_get_size(group_doc, group_path)
                adjusted_size = max(0, group_size - baseline_size)

                stats.append(
                    {
                        "label": group["label"],
                        "path": group["path"],
                        "object_count": object_count,
                        "estimated_bytes": adjusted_size,
                    }
                )
            finally:
                group_doc.Dispose()
    finally:
        try:
            System.IO.Directory.Delete(temp_folder, True)
        except Exception:
            pass

    total_estimated_bytes = 0
    for stat in stats:
        total_estimated_bytes += stat["estimated_bytes"]

    if total_estimated_bytes <= 0:
        total_estimated_bytes = 0
        for stat in stats:
            total_estimated_bytes += stat["object_count"]
        for stat in stats:
            if total_estimated_bytes > 0:
                stat["percent"] = 100.0 * stat["object_count"] / float(total_estimated_bytes)
            else:
                stat["percent"] = 0.0
    else:
        for stat in stats:
            stat["percent"] = 100.0 * stat["estimated_bytes"] / float(total_estimated_bytes)

    stats.sort(key=lambda stat: (-stat["percent"], stat["label"].lower()))
    return stats


def build_completion_message(
    output_path,
    output_size,
    exported_count,
    source_count,
    block_count,
    source_stats,
):
    lines = []
    lines.append("Saved file:")
    lines.append(output_path)
    lines.append("")
    lines.append(
        "Exported {0} objects from {1} visible source objects.".format(
            exported_count, source_count
        )
    )
    lines.append("Final file size: {0}".format(format_bytes(output_size)))

    if block_count > 0:
        lines.append(
            "Flattened {0} visible block instance{1}.".format(
                block_count, "" if block_count == 1 else "s"
            )
        )

    if source_stats:
        lines.append("")
        lines.append("Estimated source share of exported model:")
        name_width = 28
        size_width = 12
        percent_width = 8
        header = "{0}  {1}  {2}".format(
            "File".ljust(name_width),
            "Size".rjust(size_width),
            "%".rjust(percent_width),
        )
        divider = "{0}  {1}  {2}".format(
            "-" * name_width,
            "-" * size_width,
            "-" * percent_width,
        )
        lines.append(header)
        lines.append(divider)
        for stat in source_stats:
            lines.append(
                "{0}  {1}  {2}".format(
                    fit_table_text(stat["label"], name_width),
                    format_bytes(stat["estimated_bytes"]).rjust(size_width),
                    ("{0:.1f}%".format(stat["percent"])).rjust(percent_width),
                )
            )

    lines.append("")
    lines.append("Open it in a new Rhino instance now?")
    return "\n".join(lines)


def main():
    doc = get_active_doc()
    output_path = prompt_output_path(doc)
    if not output_path:
        print("Export cancelled.")
        return

    active_source_info, items, source_count, block_count = collect_export_items(doc)

    if not items:
        print("No visible objects were exported.")
        return

    target_doc = Rhino.RhinoDoc.CreateHeadless(None)

    try:
        copy_model_settings(doc, target_doc)
        exported_count = write_items_to_doc(
            doc, target_doc, items, active_source_info["label"]
        )

        if exported_count == 0:
            print("No visible objects were exported.")
            return

        success = target_doc.SaveAs(output_path, EXPORT_VERSION)
        if not success:
            raise RuntimeError("Rhino could not save the exported file.")
    finally:
        target_doc.Dispose()

    output_size = os.path.getsize(output_path)
    source_stats = compute_source_contribution_stats(
        doc, items, active_source_info["label"]
    )

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

    completion_message = build_completion_message(
        output_path,
        output_size,
        exported_count,
        source_count,
        block_count,
        source_stats,
    )

    if ask_open_in_new_instance(completion_message):
        open_file_in_new_rhino_instance(output_path)
        print("Opened exported file in a new Rhino instance.")


if __name__ == "__main__":
    main()
