import rhinoscriptsyntax as rs

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_block_diagonal(block_id):
    """Calculates diagonal size for sorting."""
    try:
        bbox = rs.BoundingBox(block_id)
        if not bbox: return 0
        return rs.Distance(bbox[0], bbox[6])
    except:
        return 0

def process_single_block_logic(block_id):
    """Deep clean a single block."""
    if not rs.IsObject(block_id): return

    # 1. Layer Sync (Phase 1)
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
# PHASE 2: GLOBAL MESH CONSOLIDATION
# ==============================================================================

def run_mesh_color_consolidation():
    """
    1. Collect all meshes.
    2. Sort by Color.
    3. Switch Active Layer to match the first mesh of that color.
    4. Join by Color -> Split Disjoint.
    """
    # 1. Ask User
    msg = "Phase 1 (Blocks) is complete.\n\nDo you want to proceed with Global Mesh Consolidation?\n(Join all meshes of same color -> Split Disjoint)"
    result = rs.MessageBox(msg, 4 | 32, "Phase 2") # 4=Yes/No
    if result != 6: 
        rs.MessageBox("Congratulations! Phase 1 Done. Phase 2 Skipped.", 0, "Done")
        return

    rs.EnableRedraw(False)
    
    # 2. Collect Meshes
    all_meshes = rs.ObjectsByType(32, select=False)
    if not all_meshes:
        rs.MessageBox("No meshes found.", 0, "Info")
        return

    # 3. Sort into Color Bins
    # Dictionary: Key=(R,G,B) -> Value=[MeshIDs]
    color_map = {}
    
    rs.StatusBarProgressMeterShow("Sorting Colors", 0, len(all_meshes))
    
    for i, mesh_id in enumerate(all_meshes):
        if i % 500 == 0: rs.StatusBarProgressMeterUpdate(i, True)
        
        color = rs.ObjectColor(mesh_id)
        key = (color.R, color.G, color.B)
        
        if key not in color_map:
            color_map[key] = []
        color_map[key].append(mesh_id)
        
    rs.StatusBarProgressMeterHide()

    # 4. Process Bins
    total_colors = len(color_map)
    rs.StatusBarProgressMeterShow("Merging Colors", 0, total_colors)
    
    try:
        for i, key in enumerate(color_map):
            rs.StatusBarProgressMeterUpdate(i, True)
            
            meshes_in_color = color_map[key]
            if not meshes_in_color: continue

            # --- NEW LAYER LOGIC ---
            # Grab the layer from the first mesh in this list
            # and set it as active. This ensures the result stays on the correct layer.
            first_mesh = meshes_in_color[0]
            target_layer = rs.ObjectLayer(first_mesh)
            
            # Switch active layer (ignoring errors if layer is somehow locked/invalid)
            try:
                rs.CurrentLayer(target_layer)
            except:
                pass 

            # JOIN
            joined_mesh = None
            if len(meshes_in_color) > 1:
                joined_mesh = rs.JoinMeshes(meshes_in_color, delete_input=True)
            elif len(meshes_in_color) == 1:
                joined_mesh = meshes_in_color[0]
                
            if not joined_mesh: continue

            # SPLIT DISJOINT
            final_parts = rs.SplitDisjointMesh(joined_mesh, delete_input=True)
            
            # Just to be absolutely sure, force layer assignment on the final parts
            if final_parts:
                rs.ObjectLayer(final_parts, target_layer)

    except Exception as e:
         rs.MessageBox("Error in Phase 2: {}".format(e))

    rs.StatusBarProgressMeterHide()
    rs.EnableRedraw(True)
    rs.MessageBox("Congratulations! It's over.", 0, "Success")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main_workflow():
    # --- PHASE 1: BLOCKS ---
    all_blocks = rs.ObjectsByType(4096, select=False)
    
    if all_blocks:
        count = len(all_blocks)
        msg = "Found {} blocks.\n\nProceed with Block-to-Group conversion?".format(count)
        if rs.MessageBox(msg, 4 | 32, "Phase 1") == 6:
            
            rs.Prompt("Sorting blocks by size...")
            # Sort by size to handle nested geometry efficiently
            sorted_blocks = sorted(all_blocks, key=get_block_diagonal, reverse=True)

            rs.EnableRedraw(False)
            rs.StatusBarProgressMeterShow("Processing Blocks", 0, count)

            try:
                for i, block_id in enumerate(sorted_blocks):
                    rs.StatusBarProgressMeterUpdate(i, True)
                    process_single_block_logic(block_id)
            except Exception as e:
                rs.MessageBox("Error in Phase 1: {}".format(e))
            finally:
                rs.EnableRedraw(True)
                rs.StatusBarProgressMeterHide()
                # Quiet purge to clean up definitions
                rs.Command("_-Purge _BlockDefinitions _Yes _Enter", echo=False)

    # --- PHASE 2: COLORS ---
    run_mesh_color_consolidation()

if __name__ == "__main__":
    main_workflow()