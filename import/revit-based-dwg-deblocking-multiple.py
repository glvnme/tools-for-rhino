import rhinoscriptsyntax as rs
import math

def get_block_diagonal(block_id):
    """Calculates the diagonal length of a block's bounding box."""
    try:
        # Get bounding box (corners)
        bbox = rs.BoundingBox(block_id)
        if not bbox: return 0
        # Calculate distance between min (0) and max (6) corners
        return rs.Distance(bbox[0], bbox[6])
    except:
        return 0

def process_single_block_logic(block_id):
    """
    The Core Workflow:
    1. Get Layer.
    2. Recursive Explode.
    3. Join Meshes.
    4. Split Disjoint.
    5. Group.
    """
    
    # Check if object still exists (it might have been inside a previous block)
    if not rs.IsObject(block_id):
        return

    # 1. Layer Sync
    target_layer = rs.ObjectLayer(block_id)
    rs.CurrentLayer(target_layer)

    # 2. Recursive Explode (The "Deep Clean")
    objects_to_check = [block_id]
    final_raw_objects = []
    
    # Safety counter to prevent infinite loops
    iteration = 0
    
    while True:
        iteration += 1
        has_nested_blocks = False
        next_pass = []
        
        for obj in objects_to_check:
            if rs.IsBlockInstance(obj):
                has_nested_blocks = True
                parts = rs.ExplodeBlockInstance(obj)
                if parts:
                    next_pass.extend(parts)
            else:
                next_pass.append(obj)
        
        objects_to_check = next_pass
        
        if not has_nested_blocks or iteration > 50:
            final_raw_objects = objects_to_check
            break

    # 3. Filter Meshes (Leave Curves/Points alone)
    meshes_to_join = [obj for obj in final_raw_objects if rs.IsMesh(obj)]
    
    if not meshes_to_join:
        return

    # 4. Join
    joined_mesh_id = None
    if len(meshes_to_join) > 1:
        joined_mesh_id = rs.JoinMeshes(meshes_to_join, delete_input=True)
    elif len(meshes_to_join) == 1:
        joined_mesh_id = meshes_to_join[0]

    if not joined_mesh_id:
        return

    # 5. Split Disjoint
    final_parts = rs.SplitDisjointMesh(joined_mesh_id, delete_input=True)
    
    # Failsafe: if not disjoint, keep original
    if not final_parts:
        final_parts = [joined_mesh_id]

    # 6. Group & Restore Layer
    if final_parts:
        rs.ObjectLayer(final_parts, target_layer)
        group_name = rs.AddGroup()
        rs.AddObjectsToGroup(final_parts, group_name)

def automate_full_model():
    # 1. Find all Blocks
    print("Scanning model for blocks...")
    all_blocks = rs.ObjectsByType(4096, select=False)
    
    if not all_blocks:
        rs.MessageBox("No blocks found in the model.", 0, "Info")
        return

    count = len(all_blocks)

    # 2. Pop-up Question
    msg = "Found {} blocks in the model.\n\nDo you want to proceed with the Block-to-Group conversion?".format(count)
    result = rs.MessageBox(msg, 4 | 32, "Cinebryno Workflow") # 4=Yes/No, 32=Question Icon
    
    if result != 6: # 6 is 'Yes'
        return

    # 3. Sort Blocks by Size (Largest First)
    # This optimizes the workflow. Exploding the House first handles the windows inside it automatically.
    rs.Prompt("Sorting blocks by size... please wait.")
    # We create a list of tuples: (ID, Size) and sort by Size descending
    sorted_blocks = sorted(all_blocks, key=get_block_diagonal, reverse=True)

    # 4. Processing Loop
    rs.EnableRedraw(False)
    rs.StatusBarProgressMeterShow("Processing Blocks", 0, count)

    try:
        for i, block_id in enumerate(sorted_blocks):
            # Update Progress Bar (Float value 0.0 - 1.0 handled by Rhino internally via range)
            rs.StatusBarProgressMeterUpdate(i, True)
            
            # Run the workflow
            process_single_block_logic(block_id)
            
            # Optional: Force Rhino to keep UI responsive (slight slowdown, but stops 'Not Responding')
            if i % 10 == 0:
                rs.Prompt("Processed {} / {} blocks...".format(i, count))

    except Exception as e:
        rs.MessageBox("An error occurred: {}".format(e), 0, "Error")

    finally:
        # 5. Cleanup
        rs.EnableRedraw(True)
        rs.StatusBarProgressMeterHide()
        rs.Command("_-Purge _BlockDefinitions _Yes _Enter", echo=False) # Optional cleanup of definitions
        rs.MessageBox("Congratulations! It's over.", 0, "Success")

if __name__ == "__main__":
    automate_full_model()