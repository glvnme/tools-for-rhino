import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
import System


def _collect_existing_ids(doc):
    ids = set()
    settings = Rhino.DocObjects.ObjectEnumeratorSettings()

    # RhinoCommon version compatibility
    if hasattr(settings, "IncludeDeletedObjects"):
        settings.IncludeDeletedObjects = False
    elif hasattr(settings, "DeletedObjects"):
        settings.DeletedObjects = False

    if hasattr(settings, "IncludeGrips"):
        settings.IncludeGrips = False
    elif hasattr(settings, "GripObjects"):
        settings.GripObjects = False

    try:
        objs = doc.Objects.GetObjectList(settings)
        for obj in objs:
            if obj is None:
                continue
            try:
                if obj.IsDeleted:
                    continue
            except:
                pass
            ids.add(obj.Id)
        return ids
    except:
        # Fallback for API differences
        all_ids = rs.AllObjects(False, True, False, True)
        return set(all_ids) if all_ids else set()


def _build_layer_map(doc, file3dm):
    layer_map = {}
    layer_count = file3dm.Layers.Count

    for i in xrange(layer_count):
        src_layer = file3dm.Layers.FindIndex(i)
        if src_layer is None:
            continue

        target_index = -1

        # Try nested full path first
        if hasattr(src_layer, "FullPath"):
            try:
                target_index = doc.Layers.FindByFullPath(src_layer.FullPath, -1)
            except:
                pass

        # Fallback by name
        if target_index < 0:
            try:
                target_index = doc.Layers.Find(src_layer.Name, True)
            except:
                target_index = -1

        # Create if missing
        if target_index < 0:
            new_layer = Rhino.DocObjects.Layer()
            new_layer.Name = src_layer.Name
            if hasattr(src_layer, "Color"):
                new_layer.Color = src_layer.Color
            if hasattr(src_layer, "IsVisible"):
                new_layer.IsVisible = src_layer.IsVisible
            if hasattr(src_layer, "IsLocked"):
                new_layer.IsLocked = src_layer.IsLocked
            target_index = doc.Layers.Add(new_layer)

        if target_index >= 0:
            layer_map[i] = target_index

    return layer_map


def _post_import_action(imported_ids):
    if not imported_ids:
        return

    action = rs.GetString(
        "Imported new geometry. Action?",
        "Select",
        ["None", "Select", "Isolate"]
    )
    if not action or action == "None":
        return

    rs.UnselectAllObjects()
    rs.SelectObjects(imported_ids)

    if action == "Select":
        return

    # Isolate mode:
    # 1) new objects selected
    # 2) invert selection
    # 3) lock all others
    # 4) reselect new objects
    rs.InvertSelectedObjects()
    others = rs.SelectedObjects() or []
    if others:
        rs.LockObjects(others)

    rs.UnselectAllObjects()
    rs.SelectObjects(imported_ids)


def import_only_new_by_guid():
    path = rs.OpenFileName(
        "Select source .3dm to merge (new GUIDs only)",
        "Rhino 3D Model (*.3dm)|*.3dm||"
    )
    if not path:
        return

    source = Rhino.FileIO.File3dm.Read(path)
    if source is None:
        print("Could not read file: {0}".format(path))
        return

    existing_ids = _collect_existing_ids(sc.doc)
    layer_map = _build_layer_map(sc.doc, source)

    imported = 0
    skipped = 0
    failed = 0
    imported_ids = []

    for src_obj in source.Objects:
        if src_obj is None or src_obj.Geometry is None:
            failed += 1
            continue

        attrs = src_obj.Attributes.Duplicate()
        src_id = attrs.ObjectId

        if src_id != System.Guid.Empty and src_id in existing_ids:
            skipped += 1
            continue

        if attrs.LayerIndex in layer_map:
            attrs.LayerIndex = layer_map[attrs.LayerIndex]

        new_id = sc.doc.Objects.Add(src_obj.Geometry, attrs)
        if new_id == System.Guid.Empty:
            failed += 1
            continue

        imported += 1
        imported_ids.append(new_id)
        existing_ids.add(new_id)

    sc.doc.Views.Redraw()

    msg = "Imported: {0}\nSkipped: {1}\nFailed: {2}".format(imported, skipped, failed)
    print(msg)
    rs.MessageBox(msg, 0, "Import New")

    _post_import_action(imported_ids)
    sc.doc.Views.Redraw()


if __name__ == "__main__":
    import_only_new_by_guid()
