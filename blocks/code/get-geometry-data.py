"""
Grasshopper Rhino 8 Python 3 script: get data from any Rhino or Grasshopper geometry input.

How to use
1. Drop a Python 3 component onto the Grasshopper canvas in Rhino 8.
2. Create one input and name it `G`.
3. Set input `G` to:
   - Type hint: `No Type Hint`
   - Access: `Item` or `List`
4. Create fifteen outputs with these exact names:
   - `Name`
   - `Keys`
   - `Values`
   - `Geometry`
   - `LayerPath`
   - `GeometryType`
   - `GeometryInfo`
   - `ColorSource`
   - `DisplayColor`
   - `MaterialSource`
   - `MaterialName`
   - `Linetype`
   - `PrintColor`
   - `PrintWidth`
   - `PrintColorSource`
5. Copy the script below into the Python 3 component editor.
6. Plug in any of these types into the same input:
   - Rhino object GUID
   - `ObjRef`
   - Rhino document object
   - Grasshopper or Rhino geometry such as point, line, curve, polyline, arc, circle, mesh, brep, surface, extrusion, box, rectangle

What each output returns
- `Name`: Rhino object name from document attributes when available, otherwise `None`
- `Keys`: user text keys from Rhino document attributes or geometry user strings
- `Values`: user text values matching `Keys`
- `Geometry`: duplicated Rhino geometry, coerced when needed
- `LayerPath`: full layer path when the source is a Rhino document object, otherwise `None`
- `GeometryType`: Rhino geometry class name
- `GeometryInfo`: dictionary of general and type-specific geometry properties
- `ColorSource`: effective Rhino color source, similar to Elefront
- `DisplayColor`: effective display color, similar to Elefront
- `MaterialSource`: effective Rhino material source
- `MaterialName`: resolved Rhino material name when available
- `Linetype`: resolved effective linetype name when available
- `PrintColor`: effective plot/print color when available
- `PrintWidth`: effective plot/print width when available
- `PrintColorSource`: effective plot/print color source

Notes
- This script is universal for mixed geometry input. It does not require a GUID.
- If the input source is native Grasshopper geometry, there is usually no Rhino document GUID, name, or layer path to recover.
- If the input is a list, every output becomes a list with matching order.
"""

import Rhino
import System
import scriptcontext as sc
import rhinoscriptsyntax as rs
from System.Collections import IEnumerable


def get_input_value():
    preferred_names = ["G", "g", "guid", "Guid", "geometry", "Geometry", "x", "a"]
    for name in preferred_names:
        if name in globals():
            value = globals()[name]
            if value is not None:
                return value

    ignored_names = {
        "__name__",
        "__doc__",
        "__package__",
        "__loader__",
        "__spec__",
        "__annotations__",
        "__builtins__",
        "__file__",
        "__cached__",
        "Rhino",
        "System",
        "sc",
        "rs",
        "IEnumerable",
        "get_input_value",
        "get_layer_full_path",
        "point3d_to_tuple",
        "vector3d_to_tuple",
        "interval_to_tuple",
        "bbox_size_tuple",
        "is_iterable_input",
        "ensure_list",
        "duplicate_geometry",
        "unwrap_input",
        "try_get_reference_guid",
        "resolve_guid_reference",
        "coerce_to_geometry",
        "get_enum_name",
        "get_effective_layer",
        "get_indexed_name",
        "resolve_material_name",
        "resolve_linetype_name",
        "resolve_print_color",
        "resolve_print_width",
        "get_attribute_outputs",
        "add_curve_info",
        "add_point_info",
        "add_pointcloud_info",
        "add_brep_info",
        "add_surface_info",
        "add_mesh_info",
        "add_extrusion_info",
        "add_annotation_info",
        "build_geometry_info",
        "get_user_strings_as_lists",
        "try_parse_guid",
        "resolve_single_input",
        "resolve_inputs",
        "collapse_output",
        "Name",
        "Keys",
        "Values",
        "Geometry",
        "LayerPath",
        "GeometryType",
        "GeometryInfo",
        "ColorSource",
        "DisplayColor",
        "MaterialSource",
        "MaterialName",
        "Linetype",
        "PrintColor",
        "PrintWidth",
        "PrintColorSource",
    }

    for name, value in globals().items():
        if name in ignored_names or name.startswith("__"):
            continue
        if callable(value):
            continue
        if value is not None:
            return value

    return None


def get_layer_full_path(doc, layer_index):
    if layer_index < 0:
        return None

    layer = doc.Layers.FindIndex(layer_index)
    if layer is None:
        return None

    return layer.FullPath


def point3d_to_tuple(pt):
    return (pt.X, pt.Y, pt.Z)


def vector3d_to_tuple(vec):
    return (vec.X, vec.Y, vec.Z)


def interval_to_tuple(interval):
    return (interval.T0, interval.T1)


def bbox_size_tuple(bbox):
    diagonal = bbox.Max - bbox.Min
    return (diagonal.X, diagonal.Y, diagonal.Z)


def is_iterable_input(value):
    if value is None:
        return False
    if isinstance(value, (str, bytes)):
        return False
    if isinstance(value, Rhino.Geometry.GeometryBase):
        return False
    if isinstance(value, (Rhino.Geometry.Point3d, Rhino.Geometry.Line, Rhino.Geometry.Arc,
                          Rhino.Geometry.Circle, Rhino.Geometry.Polyline, Rhino.Geometry.Box,
                          Rhino.Geometry.Rectangle3d, Rhino.Geometry.Plane, System.Guid)):
        return False
    return isinstance(value, (list, tuple, IEnumerable))


def ensure_list(value):
    if is_iterable_input(value):
        return list(value)
    return [value]


def duplicate_geometry(geo):
    if geo is None:
        return None
    dup = geo.Duplicate()
    if dup is not None:
        return dup
    return geo


def unwrap_input(value):
    if value is None:
        return None

    if hasattr(value, "ScriptVariable"):
        try:
            unwrapped = value.ScriptVariable()
            if unwrapped is not None:
                return unwrapped
        except Exception:
            pass

    if hasattr(value, "Value"):
        try:
            unwrapped = value.Value
            if unwrapped is not None:
                return unwrapped
        except Exception:
            pass

    return value


def try_get_reference_guid(value):
    for attr_name in ("ReferenceID", "ReferenceId"):
        if hasattr(value, attr_name):
            try:
                ref_id = getattr(value, attr_name)
                if isinstance(ref_id, System.Guid) and ref_id != System.Guid.Empty:
                    return ref_id
            except Exception:
                pass
    return None


def resolve_guid_reference(doc, guid_value):
    if guid_value is None or guid_value == System.Guid.Empty:
        return None, None

    rh_obj = doc.Objects.FindId(guid_value)
    if rh_obj is not None:
        return rh_obj, None

    try:
        obj_ref = Rhino.DocObjects.ObjRef(guid_value)
        if obj_ref is not None:
            rh_obj = obj_ref.Object()
            if rh_obj is not None:
                return rh_obj, None
            geo = obj_ref.Geometry()
            if geo is not None:
                return None, duplicate_geometry(geo)
    except Exception:
        pass

    previous_doc = sc.doc
    try:
        sc.doc = doc
        rh_obj = rs.coercerhinoobject(guid_value, False, False)
        if rh_obj is not None:
            return rh_obj, None
        geo = rs.coercegeometry(guid_value, False)
        if geo is not None:
            return None, duplicate_geometry(geo)
    except Exception:
        pass
    finally:
        sc.doc = previous_doc

    return None, None


def coerce_to_geometry(value):
    value = unwrap_input(value)

    if value is None:
        return None

    if isinstance(value, Rhino.Geometry.GeometryBase):
        return duplicate_geometry(value)

    if isinstance(value, Rhino.Geometry.Point3d):
        return Rhino.Geometry.Point(value)

    if isinstance(value, Rhino.Geometry.Line):
        return Rhino.Geometry.LineCurve(value)

    if isinstance(value, Rhino.Geometry.Arc):
        return Rhino.Geometry.ArcCurve(value)

    if isinstance(value, Rhino.Geometry.Circle):
        return Rhino.Geometry.ArcCurve(value)

    if isinstance(value, Rhino.Geometry.Polyline):
        return Rhino.Geometry.PolylineCurve(value)

    if isinstance(value, Rhino.Geometry.Rectangle3d):
        return value.ToNurbsCurve()

    if isinstance(value, Rhino.Geometry.Box):
        return value.ToBrep()

    if isinstance(value, Rhino.Geometry.Sphere):
        return Rhino.Geometry.Brep.CreateFromSphere(value)

    if isinstance(value, Rhino.Geometry.Cylinder):
        return value.ToBrep(True, True)

    if isinstance(value, Rhino.Geometry.Cone):
        return value.ToBrep(True)

    if isinstance(value, Rhino.Geometry.Plane):
        interval = Rhino.Geometry.Interval(-0.5, 0.5)
        return Rhino.Geometry.PlaneSurface(value, interval, interval)

    return None


def get_enum_name(value):
    if value is None:
        return None

    try:
        return value.ToString()
    except Exception:
        return str(value)


def get_effective_layer(doc, attrs):
    if doc is None or attrs is None:
        return None

    try:
        return doc.Layers.FindIndex(attrs.LayerIndex)
    except Exception:
        return None


def get_indexed_name(table, index):
    if table is None or index is None or index < 0:
        return None

    try:
        item = table.FindIndex(index)
    except Exception:
        item = None

    if item is None:
        try:
            item = table[index]
        except Exception:
            item = None

    if item is None:
        return None

    return getattr(item, "Name", None)


def resolve_material_name(doc, rh_obj, attrs):
    if doc is None or attrs is None:
        return None

    try:
        render_material = rh_obj.GetRenderMaterial(True)
        if render_material is not None and getattr(render_material, "Name", None):
            return render_material.Name
    except Exception:
        pass

    material_index = attrs.MaterialIndex
    if attrs.MaterialSource == Rhino.DocObjects.ObjectMaterialSource.MaterialFromLayer:
        layer = get_effective_layer(doc, attrs)
        if layer is not None:
            material_index = getattr(layer, "RenderMaterialIndex", material_index)

    return get_indexed_name(doc.Materials, material_index)


def resolve_linetype_name(doc, attrs):
    if doc is None or attrs is None:
        return None

    linetype_index = attrs.LinetypeIndex
    if attrs.LinetypeSource == Rhino.DocObjects.ObjectLinetypeSource.LinetypeFromLayer:
        layer = get_effective_layer(doc, attrs)
        if layer is not None:
            linetype_index = getattr(layer, "LinetypeIndex", linetype_index)

    return get_indexed_name(doc.Linetypes, linetype_index)


def resolve_print_color(doc, attrs):
    if doc is None or attrs is None:
        return None

    source = attrs.PlotColorSource
    if source == Rhino.DocObjects.ObjectPlotColorSource.PlotColorFromObject:
        return attrs.PlotColor

    if source == Rhino.DocObjects.ObjectPlotColorSource.PlotColorFromLayer:
        layer = get_effective_layer(doc, attrs)
        if layer is not None:
            return getattr(layer, "PlotColor", None)

    if source == Rhino.DocObjects.ObjectPlotColorSource.PlotColorFromDisplay:
        try:
            return attrs.DrawColor(doc)
        except Exception:
            return None

    if source == Rhino.DocObjects.ObjectPlotColorSource.PlotColorFromParent:
        layer = get_effective_layer(doc, attrs)
        if layer is not None:
            return getattr(layer, "PlotColor", None)

    return attrs.PlotColor


def resolve_print_width(doc, attrs):
    if doc is None or attrs is None:
        return None

    source = attrs.PlotWeightSource
    if source == Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromObject:
        return attrs.PlotWeight

    if source == Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromLayer:
        layer = get_effective_layer(doc, attrs)
        if layer is not None:
            return getattr(layer, "PlotWeight", None)

    if source == Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromParent:
        layer = get_effective_layer(doc, attrs)
        if layer is not None:
            return getattr(layer, "PlotWeight", None)

    return attrs.PlotWeight


def get_attribute_outputs(doc, rh_obj):
    if rh_obj is None:
        return {
            "ColorSource": None,
            "DisplayColor": None,
            "MaterialSource": None,
            "MaterialName": None,
            "Linetype": None,
            "PrintColor": None,
            "PrintWidth": None,
            "PrintColorSource": None,
        }

    attrs = rh_obj.Attributes
    return {
        "ColorSource": get_enum_name(attrs.ColorSource),
        "DisplayColor": attrs.DrawColor(doc),
        "MaterialSource": get_enum_name(attrs.MaterialSource),
        "MaterialName": resolve_material_name(doc, rh_obj, attrs),
        "Linetype": resolve_linetype_name(doc, attrs),
        "PrintColor": resolve_print_color(doc, attrs),
        "PrintWidth": resolve_print_width(doc, attrs),
        "PrintColorSource": get_enum_name(attrs.PlotColorSource),
    }


def add_curve_info(geo, info):
    info["is_curve"] = True
    info["is_closed"] = geo.IsClosed
    info["is_periodic"] = geo.IsPeriodic
    info["degree"] = geo.Degree
    info["domain"] = interval_to_tuple(geo.Domain)
    info["length"] = geo.GetLength()
    info["point_at_start"] = point3d_to_tuple(geo.PointAtStart)
    info["point_at_end"] = point3d_to_tuple(geo.PointAtEnd)

    success, plane = geo.TryGetPlane()
    info["has_plane"] = success
    if success:
        info["plane_origin"] = point3d_to_tuple(plane.Origin)
        info["plane_x_axis"] = vector3d_to_tuple(plane.XAxis)
        info["plane_y_axis"] = vector3d_to_tuple(plane.YAxis)
        info["plane_z_axis"] = vector3d_to_tuple(plane.ZAxis)

    if hasattr(geo, "PointCount"):
        info["point_count"] = geo.PointCount


def add_point_info(geo, info):
    info["is_point"] = True
    info["location"] = point3d_to_tuple(geo.Location)


def add_pointcloud_info(geo, info):
    info["is_pointcloud"] = True
    info["point_count"] = geo.Count
    if geo.Count > 0:
        info["first_point"] = point3d_to_tuple(geo[0].Location)


def add_brep_info(geo, info):
    info["is_brep"] = True
    info["is_solid"] = geo.IsSolid
    info["face_count"] = geo.Faces.Count
    info["edge_count"] = geo.Edges.Count
    info["vertex_count"] = geo.Vertices.Count

    area_props = Rhino.Geometry.AreaMassProperties.Compute(geo)
    if area_props:
        info["area"] = area_props.Area
        info["area_centroid"] = point3d_to_tuple(area_props.Centroid)

    volume_props = Rhino.Geometry.VolumeMassProperties.Compute(geo)
    if volume_props:
        info["volume"] = volume_props.Volume
        info["volume_centroid"] = point3d_to_tuple(volume_props.Centroid)


def add_surface_info(geo, info):
    info["is_surface"] = True
    info["u_domain"] = interval_to_tuple(geo.Domain(0))
    info["v_domain"] = interval_to_tuple(geo.Domain(1))
    info["is_closed_u"] = geo.IsClosed(0)
    info["is_closed_v"] = geo.IsClosed(1)

    area_props = Rhino.Geometry.AreaMassProperties.Compute(geo)
    if area_props:
        info["area"] = area_props.Area
        info["area_centroid"] = point3d_to_tuple(area_props.Centroid)


def add_mesh_info(geo, info):
    info["is_mesh"] = True
    info["vertex_count"] = geo.Vertices.Count
    info["face_count"] = geo.Faces.Count
    info["is_closed"] = geo.IsClosed
    info["is_manifold"] = geo.IsManifold(True)

    area_props = Rhino.Geometry.AreaMassProperties.Compute(geo)
    if area_props:
        info["area"] = area_props.Area
        info["area_centroid"] = point3d_to_tuple(area_props.Centroid)

    volume_props = Rhino.Geometry.VolumeMassProperties.Compute(geo)
    if volume_props:
        info["volume"] = volume_props.Volume
        info["volume_centroid"] = point3d_to_tuple(volume_props.Centroid)


def add_extrusion_info(geo, info):
    info["is_extrusion"] = True
    info["is_solid"] = geo.IsSolid
    info["path_start"] = point3d_to_tuple(geo.PathStart)
    info["path_end"] = point3d_to_tuple(geo.PathEnd)

    area_props = Rhino.Geometry.AreaMassProperties.Compute(geo)
    if area_props:
        info["area"] = area_props.Area

    volume_props = Rhino.Geometry.VolumeMassProperties.Compute(geo)
    if volume_props:
        info["volume"] = volume_props.Volume


def add_annotation_info(geo, info):
    info["is_annotation"] = True
    plain_text = None
    if hasattr(geo, "PlainText"):
        plain_text = geo.PlainText
    elif hasattr(geo, "Text"):
        plain_text = geo.Text
    info["text"] = plain_text


def build_geometry_info(geo):
    bbox = geo.GetBoundingBox(True)

    info = {}
    info["geometry_type"] = geo.GetType().Name
    info["is_valid"] = geo.IsValid
    info["bounding_box_min"] = point3d_to_tuple(bbox.Min)
    info["bounding_box_max"] = point3d_to_tuple(bbox.Max)
    info["bounding_box_size"] = bbox_size_tuple(bbox)
    info["bounding_box_center"] = point3d_to_tuple(bbox.Center)

    if isinstance(geo, Rhino.Geometry.Point):
        add_point_info(geo, info)
    elif isinstance(geo, Rhino.Geometry.PointCloud):
        add_pointcloud_info(geo, info)
    elif isinstance(geo, Rhino.Geometry.Brep):
        add_brep_info(geo, info)
    elif isinstance(geo, Rhino.Geometry.Surface):
        add_surface_info(geo, info)
    elif isinstance(geo, Rhino.Geometry.Mesh):
        add_mesh_info(geo, info)
    elif isinstance(geo, Rhino.Geometry.Extrusion):
        add_extrusion_info(geo, info)
    elif isinstance(geo, Rhino.Geometry.AnnotationBase):
        add_annotation_info(geo, info)
    elif isinstance(geo, Rhino.Geometry.Curve):
        add_curve_info(geo, info)

    return info, bbox


def get_user_strings_as_lists(string_holder):
    keys = []
    values = []

    if string_holder is None or not hasattr(string_holder, "GetUserStrings"):
        return keys, values

    user_strings = string_holder.GetUserStrings()
    if user_strings:
        for key in user_strings.AllKeys:
            keys.append(key)
            values.append(user_strings[key])

    return keys, values


def try_parse_guid(value):
    if isinstance(value, System.Guid):
        return value

    if isinstance(value, str):
        try:
            return System.Guid.Parse(value)
        except Exception:
            return None

    return None


def resolve_single_input(doc, value):
    raw_value = value
    value = unwrap_input(value)

    rh_obj = None
    geo = None
    name = None
    layer_path = None
    keys = []
    values = []

    reference_guid = try_get_reference_guid(raw_value)
    if reference_guid is not None:
        rh_obj, geo = resolve_guid_reference(doc, reference_guid)

    guid_value = try_parse_guid(value)
    if guid_value is not None and guid_value != System.Guid.Empty:
        found_obj, found_geo = resolve_guid_reference(doc, guid_value)
        if found_obj is not None:
            rh_obj = found_obj
        elif geo is None:
            geo = found_geo

    if rh_obj is None and isinstance(value, Rhino.DocObjects.ObjRef):
        rh_obj = value.Object()
        if rh_obj is None:
            geo = value.Geometry()

    elif rh_obj is None and isinstance(value, Rhino.DocObjects.RhinoObject):
        rh_obj = value

    if rh_obj is None and geo is None:
        geo = coerce_to_geometry(value)

    if rh_obj is not None:
        geo = duplicate_geometry(rh_obj.Geometry)
        name = rh_obj.Attributes.Name
        layer_path = get_layer_full_path(doc, rh_obj.Attributes.LayerIndex)
        keys, values = get_user_strings_as_lists(rh_obj.Attributes)
    elif geo is not None:
        keys, values = get_user_strings_as_lists(geo)

    if geo is None:
        value_type = type(value).__name__
        if guid_value is not None:
            raise Exception(
                "Input is a Guid, but it does not resolve to Rhino document geometry. "
                "Use 'No Type Hint' on the Grasshopper input, or pass a Rhino-referenced object instead."
            )
        raise Exception("Unsupported input type: {0}".format(value_type))

    geometry_info, _ = build_geometry_info(geo)
    attribute_outputs = get_attribute_outputs(doc, rh_obj)

    return {
        "Name": name,
        "Keys": keys,
        "Values": values,
        "Geometry": geo,
        "LayerPath": layer_path,
        "GeometryType": geo.GetType().Name,
        "GeometryInfo": geometry_info,
        "ColorSource": attribute_outputs["ColorSource"],
        "DisplayColor": attribute_outputs["DisplayColor"],
        "MaterialSource": attribute_outputs["MaterialSource"],
        "MaterialName": attribute_outputs["MaterialName"],
        "Linetype": attribute_outputs["Linetype"],
        "PrintColor": attribute_outputs["PrintColor"],
        "PrintWidth": attribute_outputs["PrintWidth"],
        "PrintColorSource": attribute_outputs["PrintColorSource"],
    }


def resolve_inputs(doc, value):
    results = []
    for item in ensure_list(value):
        results.append(resolve_single_input(doc, item))
    return results


def collapse_output(results, key):
    values = [item[key] for item in results]
    if len(values) == 1:
        return values[0]
    return values


Name = None
Keys = []
Values = []
Geometry = None
LayerPath = None
GeometryType = None
GeometryInfo = {}
ColorSource = None
DisplayColor = None
MaterialSource = None
MaterialName = None
Linetype = None
PrintColor = None
PrintWidth = None
PrintColorSource = None

input_value = get_input_value()

if input_value is None:
    raise Exception("No input found. Connect one input containing GUIDs, Rhino objects, or geometry.")

doc = Rhino.RhinoDoc.ActiveDoc
if doc is None:
    raise Exception("No active Rhino document.")

results = resolve_inputs(doc, input_value)

Name = collapse_output(results, "Name")
Keys = collapse_output(results, "Keys")
Values = collapse_output(results, "Values")
Geometry = collapse_output(results, "Geometry")
LayerPath = collapse_output(results, "LayerPath")
GeometryType = collapse_output(results, "GeometryType")
GeometryInfo = collapse_output(results, "GeometryInfo")
ColorSource = collapse_output(results, "ColorSource")
DisplayColor = collapse_output(results, "DisplayColor")
MaterialSource = collapse_output(results, "MaterialSource")
MaterialName = collapse_output(results, "MaterialName")
Linetype = collapse_output(results, "Linetype")
PrintColor = collapse_output(results, "PrintColor")
PrintWidth = collapse_output(results, "PrintWidth")
PrintColorSource = collapse_output(results, "PrintColorSource")
