"""
Rhino 8 Python 3 script: compact viewport layer usage report.

What it does
- Looks only at geometry that is active, visible, and in the current active viewport.
- Estimates each object's contribution with a lightweight size metric.
- Ranks root layers and full sublayers by percentage of viewport geometry usage.
- Selects and zooms to the heaviest sublayer automatically.
- Shows a plain Rhino report dialog with the results.

Notes
- Percentages are approximate and based on geometric size, not file size.
- Visibility is tested against the active viewport frustum using object bounding boxes.
"""

from __future__ import division

import Rhino
import System
import rhinoscriptsyntax as rs


EPSILON = 1e-9
TOP_ROW_COUNT = 12


def get_active_doc():
    doc = Rhino.RhinoDoc.ActiveDoc
    if doc is None:
        raise RuntimeError("No active Rhino document.")
    return doc


def get_active_view(doc):
    view = doc.Views.ActiveView
    if view is None:
        raise RuntimeError("No active Rhino view.")
    return view


def get_layer_by_index(doc, layer_index):
    if layer_index < 0:
        return None
    return doc.Layers.FindIndex(layer_index)


def is_layer_visible_in_view(doc, layer_index, viewport_id):
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

        try:
            if hasattr(current, "PerViewportIsVisible"):
                if not current.PerViewportIsVisible(viewport_id):
                    return False
        except Exception:
            pass

        parent_id = getattr(current, "ParentLayerId", System.Guid.Empty)
        if parent_id == System.Guid.Empty:
            break
        current = doc.Layers.FindId(parent_id)

    return True


def get_bbox(geometry):
    bbox = geometry.GetBoundingBox(True)
    if bbox is None or not bbox.IsValid:
        return None
    return bbox


def is_object_visible_in_active_view(rh_obj, viewport):
    try:
        bbox = get_bbox(rh_obj.Geometry)
        if bbox is None:
            return False
        return viewport.IsVisible(bbox)
    except Exception:
        return False


def get_objects_in_active_view(doc, view):
    viewport = view.ActiveViewport
    viewport_id = viewport.Id

    settings = Rhino.DocObjects.ObjectEnumeratorSettings()
    if hasattr(settings, "ActiveObjects"):
        settings.ActiveObjects = True
    if hasattr(settings, "ReferenceObjects"):
        settings.ReferenceObjects = False
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
    if hasattr(settings, "LockedObjects"):
        settings.LockedObjects = True
    if hasattr(settings, "NormalObjects"):
        settings.NormalObjects = True

    result = []
    for rh_obj in doc.Objects.GetObjectList(settings):
        if rh_obj is None:
            continue
        if rh_obj.IsDeleted:
            continue
        if getattr(rh_obj, "IsReference", False):
            continue
        if not is_layer_visible_in_view(doc, rh_obj.Attributes.LayerIndex, viewport_id):
            continue
        if not is_object_visible_in_active_view(rh_obj, viewport):
            continue
        result.append(rh_obj)

    return result


def get_layer_path(doc, layer_index):
    layer = get_layer_by_index(doc, layer_index)
    if layer is None:
        return "Unassigned"
    return layer.FullPath or layer.Name or "Unassigned"


def get_root_layer(layer_path):
    if not layer_path:
        return "Unassigned"
    return layer_path.split("::")[0]


def union_bbox(existing_bbox, next_bbox):
    if next_bbox is None or not next_bbox.IsValid:
        return existing_bbox
    if existing_bbox is None or not existing_bbox.IsValid:
        return Rhino.Geometry.BoundingBox(next_bbox.Min, next_bbox.Max)

    merged = Rhino.Geometry.BoundingBox(existing_bbox.Min, existing_bbox.Max)
    merged.Union(next_bbox)
    return merged


def safe_area(geometry):
    try:
        props = Rhino.Geometry.AreaMassProperties.Compute(geometry)
        if props is not None:
            return props.Area
    except Exception:
        pass
    return 0.0


def safe_volume(geometry):
    try:
        props = Rhino.Geometry.VolumeMassProperties.Compute(geometry)
        if props is not None:
            return props.Volume
    except Exception:
        pass
    return 0.0


def safe_curve_length(curve):
    try:
        return curve.GetLength()
    except Exception:
        return 0.0


def compute_weight(geometry):
    bbox = get_bbox(geometry)
    bbox_diag = 0.0
    if bbox is not None:
        bbox_diag = bbox.Diagonal.Length

    if isinstance(geometry, Rhino.Geometry.Point):
        return 1.0

    if isinstance(geometry, Rhino.Geometry.PointCloud):
        return float(max(geometry.Count, 1))

    if isinstance(geometry, Rhino.Geometry.Curve):
        length = safe_curve_length(geometry)
        if length > EPSILON:
            return length
        return max(1.0, bbox_diag)

    if isinstance(geometry, Rhino.Geometry.Extrusion):
        volume = safe_volume(geometry)
        if volume > EPSILON:
            return volume
        area = safe_area(geometry)
        if area > EPSILON:
            return area
        return max(1.0, bbox_diag)

    if isinstance(geometry, Rhino.Geometry.Brep):
        volume = safe_volume(geometry)
        if volume > EPSILON:
            return volume
        area = safe_area(geometry)
        if area > EPSILON:
            return area
        return max(1.0, bbox_diag)

    if isinstance(geometry, Rhino.Geometry.Surface):
        area = safe_area(geometry)
        if area > EPSILON:
            return area
        return max(1.0, bbox_diag)

    if isinstance(geometry, Rhino.Geometry.Mesh):
        volume = safe_volume(geometry)
        if volume > EPSILON:
            return volume
        area = safe_area(geometry)
        if area > EPSILON:
            return area
        return float(max(geometry.Faces.Count, 1))

    if isinstance(geometry, Rhino.Geometry.Hatch):
        area = safe_area(geometry)
        if area > EPSILON:
            return area
        return max(1.0, bbox_diag)

    if isinstance(geometry, Rhino.Geometry.TextDot):
        return max(1.0, float(len(geometry.Text or "")), bbox_diag)

    if isinstance(geometry, Rhino.Geometry.AnnotationBase):
        text_value = ""
        if hasattr(geometry, "PlainText"):
            text_value = geometry.PlainText or ""
        elif hasattr(geometry, "Text"):
            text_value = geometry.Text or ""
        return max(1.0, float(len(text_value)), bbox_diag)

    return max(1.0, bbox_diag)


def format_percent(value):
    return "{0:.1f}%".format(value)


def make_bucket(name):
    return {
        "name": name,
        "weight": 0.0,
        "percent": 0.0,
        "object_ids": [],
        "bbox": None,
    }


def add_to_bucket(bucket, record):
    bucket["weight"] += record["weight"]
    bucket["object_ids"].append(record["id"])
    bucket["bbox"] = union_bbox(bucket["bbox"], record["bbox"])


def finalize_buckets(bucket_dict, total_weight):
    rows = list(bucket_dict.values())
    for row in rows:
        if total_weight > EPSILON:
            row["percent"] = 100.0 * row["weight"] / total_weight
        else:
            row["percent"] = 0.0

    rows.sort(key=lambda item: (-item["percent"], item["name"].lower()))
    return rows


def build_object_record(doc, rh_obj):
    geometry = rh_obj.Geometry
    return {
        "id": rh_obj.Id,
        "layer_path": get_layer_path(doc, rh_obj.Attributes.LayerIndex),
        "weight": compute_weight(geometry),
        "bbox": get_bbox(geometry),
    }


def analyze_objects(doc, objects):
    root_buckets = {}
    sublayer_buckets = {}
    total_weight = 0.0

    for rh_obj in objects:
        record = build_object_record(doc, rh_obj)
        root_layer = get_root_layer(record["layer_path"])

        total_weight += record["weight"]

        if root_layer not in root_buckets:
            root_buckets[root_layer] = make_bucket(root_layer)
        add_to_bucket(root_buckets[root_layer], record)

        if record["layer_path"] not in sublayer_buckets:
            sublayer_buckets[record["layer_path"]] = make_bucket(record["layer_path"])
        add_to_bucket(sublayer_buckets[record["layer_path"]], record)

    root_rows = finalize_buckets(root_buckets, total_weight)
    sublayer_rows = finalize_buckets(sublayer_buckets, total_weight)

    return {
        "total_objects": len(objects),
        "root_rows": root_rows,
        "sublayer_rows": sublayer_rows,
        "top_root": root_rows[0] if root_rows else None,
        "top_sublayer": sublayer_rows[0] if sublayer_rows else None,
    }


def select_and_zoom(doc, object_ids, bbox):
    doc.Objects.UnselectAll()

    for object_id in object_ids:
        try:
            doc.Objects.Select(object_id, True)
        except Exception:
            pass

    active_view = doc.Views.ActiveView
    if active_view is not None and bbox is not None and bbox.IsValid:
        try:
            active_view.ActiveViewport.ZoomBoundingBox(bbox)
        except Exception:
            pass

    doc.Views.Redraw()


def fit_table_text(value, width):
    text = value or ""
    if len(text) <= width:
        return text.ljust(width)
    if width <= 3:
        return text[:width]
    return (text[: width - 3] + "...").ljust(width)


def build_report_message(doc, view, analysis):
    lines = []
    lines.append("Viewport Layer Usage")
    lines.append("")
    lines.append("Document:")
    lines.append(doc.Name or "Untitled")
    lines.append("Active view: {0}".format(view.ActiveViewport.Name or "Active View"))
    lines.append("")

    if analysis["top_root"] is not None:
        lines.append(
            "Biggest root layer: {0} ({1})".format(
                analysis["top_root"]["name"],
                format_percent(analysis["top_root"]["percent"]),
            )
        )

    if analysis["top_sublayer"] is not None:
        lines.append(
            "Biggest sub layer: {0} ({1})".format(
                analysis["top_sublayer"]["name"],
                format_percent(analysis["top_sublayer"]["percent"]),
            )
        )

    lines.append("")
    lines.append("Approximate share of current active viewport geometry:")
    lines.append("")

    name_width = 46
    percent_width = 8

    lines.append("Root layers:")
    lines.append(
        "{0}  {1}".format(
            "Layer".ljust(name_width),
            "%".rjust(percent_width),
        )
    )
    lines.append(
        "{0}  {1}".format(
            "-" * name_width,
            "-" * percent_width,
        )
    )
    for row in analysis["root_rows"][:TOP_ROW_COUNT]:
        lines.append(
            "{0}  {1}".format(
                fit_table_text(row["name"], name_width),
                format_percent(row["percent"]).rjust(percent_width),
            )
        )

    lines.append("")
    lines.append("Sub layers:")
    lines.append(
        "{0}  {1}".format(
            "Layer".ljust(name_width),
            "%".rjust(percent_width),
        )
    )
    lines.append(
        "{0}  {1}".format(
            "-" * name_width,
            "-" * percent_width,
        )
    )
    for row in analysis["sublayer_rows"][:TOP_ROW_COUNT]:
        lines.append(
            "{0}  {1}".format(
                fit_table_text(row["name"], name_width),
                format_percent(row["percent"]).rjust(percent_width),
            )
        )

    lines.append("")
    lines.append("The biggest sub layer has been selected and zoomed in Rhino.")
    return "\n".join(lines)


def show_report_message(message):
    rs.MessageBox(message, 0 + 64, "Viewport Layer Usage")


def main():
    doc = get_active_doc()
    view = get_active_view(doc)
    objects = get_objects_in_active_view(doc, view)

    if not objects:
        rs.MessageBox(
            "No active visible geometry was found in the current active viewport.",
            0 + 48,
            "Viewport Layer Usage",
        )
        return

    analysis = analyze_objects(doc, objects)

    top_sublayer = analysis["top_sublayer"]
    if top_sublayer is not None:
        select_and_zoom(doc, top_sublayer["object_ids"], top_sublayer["bbox"])

    message = build_report_message(doc, view, analysis)
    show_report_message(message)


if __name__ == "__main__":
    main()
