import rhinoscriptsyntax as rs
import math

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_block_diagonal(block_id):
    """Calculates diagonal size for sorting blocks."""
    try:
        bbox = rs.BoundingBox(block_id)
        if not bbox: return 0
        return rs.Distance(bbox[0], bbox[6])
    except:
        return 0

def convert_inches_to_model_units(inches_value):
    """Converts a value in Inches to the current document units."""
    units = rs.UnitSystem()
    if units == 2: return inches_value * 25.4   # mm
    elif units == 3: return inches_value * 2.54 # cm
    elif units == 4: return inches_value * 0.0254 # m
    elif units == 9: return inches_value / 12.0 # feet
    else: return inches_value # inches or other

# ==============================================================================
# PHASE 0: PREPARATION (UNHIDE EVERYTHING)
# ==============================================================================

def run_preparation_phase():
    """
    Ensures all data is visible before processing.
    1. Turns on all Layers.
    2. runs 'Show' to unhide hidden objects.
    """
    rs.EnableRedraw(False)
    
    # 1. Unhide all Layers
    all_layers = rs.LayerNames()
    if all_layers:
        for layer in all_layers:
            # Force visibility to True
            rs.LayerVisible(layer, True)
            # Optional: Unlock layers too, so we can actually edit the geometry?
            # rs.LayerLocked(layer, False) 

    # 2. Show all Hidden Geometry
    # We use the command because it's the most robust way to catch everything
    rs.Command("_-Show _Enter", echo=False)
    
    rs.EnableRedraw(True)
    # No pop-up needed here, just do it silently so we can start work.

# ==============================================================================
# PHASE 1: BLOCK LOGIC
# ==============================================================================

def process_single_block_logic(block_id):
    """Deep clean a single block (Explode -> Join -> Split -> Group)."""
    if not rs.IsObject(block_id): return

    # 1. Layer Sync
    target_layer = rs.ObjectLayer(block_id)
    rs.CurrentLayer(target_layer)

    # 2. Recursive Explode
    objects_to_check = [block_id]
    final_raw_objects = []
    iteration = 0
    
    while True:
        iteration += 1
        has_nested_blocks = False
        next_pass = []
        for obj in objects_to_check:
            if rs.IsBlockInstance(obj):
                has_nested_blocks = True
                parts = rs.ExplodeBlockInstance(obj)
                if parts: next_pass.extend(parts)
            else:
                next_pass.append(obj)
        objects_to_check = next_pass
        if not has_nested_blocks or iteration > 50:
            final_raw_objects = objects_to_check
            break

    # 3. Join & Split
    meshes = [obj for obj in final_raw_objects if rs.IsMesh(obj)]
    if not meshes: return

    joined_mesh_id = None
    if len(meshes) > 1:
        joined_mesh_id = rs.JoinMeshes(meshes, delete_input=True)
    elif len(meshes) == 1:
        joined_mesh_id = meshes[0]

    if not joined_mesh_id: return

    final_parts = rs.SplitDisjointMesh(joined_mesh_id, delete_input=True)
    if not final_parts: final_parts = [joined_mesh_id]

    # 4. Group
    if final_parts:
        rs.ObjectLayer(final_parts, target_layer)
        group_name = rs.AddGroup()
        rs.AddObjectsToGroup(final_parts, group_name)

# ==============================================================================
# PHASE 2: GLOBAL MESH CONSOLIDATION (CLEAN SOLIDS)
# ==============================================================================

def run_phase_2_consolidation():
    msg = "Phase 1 (Blocks) complete.\n\nProceed with Phase 2?\n(Join meshes by Color -> Split into clean solids)"
    if rs.MessageBox(msg, 4 | 32, "Phase 2") != 6: return

    rs.EnableRedraw(False)
    all_meshes = rs.ObjectsByType(32, select=False)
    if not all_meshes: return

    # Sort
    color_map = {}
    rs.StatusBarProgressMeterShow("Sorting Colors", 0, len(all_meshes))
    for i, mesh_id in enumerate(all_meshes):
        if i % 500 == 0: rs.StatusBarProgressMeterUpdate(i, True)
        color = rs.ObjectColor(mesh_id)
        key = (color.R, color.G, color.B)
        if key not in color_map: color_map[key] = []
        color_map[key].append(mesh_id)
    rs.StatusBarProgressMeterHide()

    # Process
    total = len(color_map)
    rs.StatusBarProgressMeterShow("Merging Colors", 0, total)
    
    try:
        for i, key in enumerate(color_map):
            rs.StatusBarProgressMeterUpdate(i, True)
            meshes_in_color = color_map[key]
            if not meshes_in_color: continue

            # Layer Sync
            first_mesh = meshes_in_color[0]
            target_layer = rs.ObjectLayer(first_mesh)
            try: rs.CurrentLayer(target_layer)
            except: pass 

            # Join
            joined_mesh = None
            if len(meshes_in_color) > 1:
                joined_mesh = rs.JoinMeshes(meshes_in_color, delete_input=True)
            elif len(meshes_in_color) == 1:
                joined_mesh = meshes_in_color[0]
            if not joined_mesh: continue

            # Split Disjoint (Keeps them as separate objects)
            final_parts = rs.SplitDisjointMesh(joined_mesh, delete_input=True)
            if final_parts: rs.ObjectLayer(final_parts, target_layer)

    except Exception as e:
         rs.MessageBox("Error in Phase 2: {}".format(e))

    rs.StatusBarProgressMeterHide()
    rs.EnableRedraw(True)

# ==============================================================================
# PHASE 3: CLEANUP & OPTIMIZATION
# ==============================================================================

def run_phase_3_cleanup():
    msg = "Phase 2 complete.\n\nProceed with Phase 3 (Cleanup)?\n1. Delete Duplicates\n2. Align Vertices\n3. Full Purge"
    if rs.MessageBox(msg, 4 | 32, "Phase 3") != 6: return

    rs.EnableRedraw(False)

    # 1. Duplicates
    rs.Prompt("Searching for duplicates...")
    rs.Command("_-SelDup", echo=False)
    duplicates = rs.SelectedObjects()
    if duplicates: rs.DeleteObjects(duplicates)
    rs.UnselectAllObjects()

    # 2. Align Vertices
    tol_inches = rs.GetReal("Enter AlignVertices tolerance in INCHES (will auto-convert):", 1.0, 0.000001)
    if tol_inches:
        tol_model = convert_inches_to_model_units(tol_inches)
        all_meshes = rs.ObjectsByType(32, select=True)
        if all_meshes:
            rs.Prompt("Aligning vertices...")
            cmd = "_-AlignVertices _Distance={} _Enter".format(tol_model)
            rs.Command(cmd, echo=False)
            rs.UnselectAllObjects()

    # 3. Purge
    rs.Prompt("Purging project...")
    rs.Command("_-Purge _All=_Yes _Enter", echo=False)
    rs.EnableRedraw(True)

# ==============================================================================
# PHASE 4: SUPER MERGE (FILE SIZE OPTIMIZATION)
# ==============================================================================

def run_phase_4_super_merge():
    """Joins all meshes of same color into ONE object. No Split."""
    msg = (
        "Phase 3 complete.\n\n"
        "Do you want to JOIN all meshes of the same color into a single object?\n\n"
        "WHY: Storing 1 large mesh uses significantly less data than 100s of small objects. "
        "This reduces file size.\n\n"
        "Proceed?"
    )
    if rs.MessageBox(msg, 4 | 32, "Phase 4 - Super Merge") != 6: return

    rs.EnableRedraw(False)
    all_meshes = rs.ObjectsByType(32, select=False)
    if not all_meshes: return

    # Sort
    color_map = {}
    rs.StatusBarProgressMeterShow("Sorting Colors for Merge", 0, len(all_meshes))
    for i, mesh_id in enumerate(all_meshes):
        if i % 500 == 0: rs.StatusBarProgressMeterUpdate(i, True)
        color = rs.ObjectColor(mesh_id)
        key = (color.R, color.G, color.B)
        if key not in color_map: color_map[key] = []
        color_map[key].append(mesh_id)
    rs.StatusBarProgressMeterHide()

    # Join Only
    total = len(color_map)
    rs.StatusBarProgressMeterShow("Super Merging...", 0, total)

    try:
        for i, key in enumerate(color_map):
            rs.StatusBarProgressMeterUpdate(i, True)
            meshes_in_color = color_map[key]
            
            if not meshes_in_color or len(meshes_in_color) < 2: 
                continue

            first_mesh = meshes_in_color[0]
            target_layer = rs.ObjectLayer(first_mesh)
            try: rs.CurrentLayer(target_layer)
            except: pass

            joined_mesh = rs.JoinMeshes(meshes_in_color, delete_input=True)
            if joined_mesh:
                rs.ObjectLayer(joined_mesh, target_layer)

    except Exception as e:
        rs.MessageBox("Error in Phase 4: {}".format(e))

    rs.StatusBarProgressMeterHide()
    rs.EnableRedraw(True)
    rs.MessageBox("Optimization Complete.", 0, "Success")

# ==============================================================================
# PHASE 5: SAVE PROMPT & FINAL DISCLAIMER
# ==============================================================================

def final_save_and_disclaimer():
    # 1. SAVE PROMPT
    msg = "Workflow successfully finished.\n\nDo you want to SAVE the model now?"
    result = rs.MessageBox(msg, 4 | 32, "Save Model")
    
    if result == 6:
        rs.Prompt("Saving model...")
        rs.Command("_-Save _Enter", echo=False)
        rs.MessageBox("Model saved successfully.", 0, "Saved")

    # 2. FINAL DISCLAIMER
    disclaimer_text = (
        "IMPORTANT - PLEASE READ:\n\n\n"
        "This script is not a universal 'silver bullet' solution. "
        "You must verify and correct the file manually.\n\n\n"
        "CRITICAL CHECKLIST:\n\n"
        "- UNITS & SCALE:\n"
        "Even if file units match, verify geometry sizes against "
        "reference drawings or PDFs. Scale uniformly if necessary.\n\n"
        "- GLOBAL ORIGIN:\n"
        "Move all geometry close to the origin {0,0,0}.\n"
        "This is critical for NDN workflows and managing data transfer.\n\n"
        "- WORKSESSIONS:\n"
        "If this is a reference model, store it with the original export.\n"
        "Use Rhino 'Worksessions' to overlay it into your main working environment."
    )
    rs.MessageBox(disclaimer_text, 0 | 64, "Final Checklist")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main_workflow():
    
    # --- PHASE 0: PREPARATION ---
    # Unhide Layers and Geometry before starting
    run_preparation_phase()

    # --- PHASE 1: BLOCKS ---
    all_blocks = rs.ObjectsByType(4096, select=False)
    if all_blocks:
        count = len(all_blocks)
        if rs.MessageBox("Found {} blocks.\n\nProceed with Phase 1 (Blocks to Groups)?".format(count), 4 | 32, "Phase 1") == 6:
            rs.Prompt("Sorting blocks by size...")
            sorted_blocks = sorted(all_blocks, key=get_block_diagonal, reverse=True)
            rs.EnableRedraw(False)
            rs.StatusBarProgressMeterShow("Processing Blocks", 0, count)
            try:
                for i, block_id in enumerate(sorted_blocks):
                    rs.StatusBarProgressMeterUpdate(i, True)
                    process_single_block_logic(block_id)
            except Exception as e: rs.MessageBox("Error: {}".format(e))
            finally:
                rs.EnableRedraw(True)
                rs.StatusBarProgressMeterHide()
                rs.Command("_-Purge _BlockDefinitions _Yes _Enter", echo=False)

    # --- PHASE 2: CONSOLIDATION ---
    run_phase_2_consolidation()
    
    # --- PHASE 3: CLEANUP ---
    run_phase_3_cleanup()

    # --- PHASE 4: SUPER MERGE ---
    run_phase_4_super_merge()

    # --- PHASE 5: SAVE & DISCLAIMER ---
    final_save_and_disclaimer()

if __name__ == "__main__":
    main_workflow()