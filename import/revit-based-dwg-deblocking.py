import rhinoscriptsyntax as rs

def process_nested_block_with_layer_sync():
    # 1. Select the Main Block
    main_block_id = rs.GetObject("Select the main block to process", 4096, preselect=True)
    
    if not main_block_id:
        return

    # ==============================================================================
    # STEP 1.5: LAYER SYNC
    # Get the layer of the selected block and make it the Current/Active Layer.
    # This ensures that when Join/Explode happens, Rhino favors this layer.
    # ==============================================================================
    target_layer_name = rs.ObjectLayer(main_block_id)
    rs.CurrentLayer(target_layer_name)

    rs.EnableRedraw(False)

    try:
        # ==============================================================================
        # STEP 2: RECURSIVE EXPLOSION
        # Dig down until no blocks remain, only raw geometry.
        # ==============================================================================
        
        objects_to_check = [main_block_id]
        final_raw_objects = []
        
        iteration = 0
        while True:
            iteration += 1
            has_nested_blocks = False
            next_pass_objects = []
            
            for obj_id in objects_to_check:
                if rs.IsBlockInstance(obj_id):
                    has_nested_blocks = True
                    # Explode
                    exploded_contents = rs.ExplodeBlockInstance(obj_id)
                    
                    if exploded_contents:
                        next_pass_objects.extend(exploded_contents)
                else:
                    # Keep raw geometry (Meshes, curves, etc.)
                    next_pass_objects.append(obj_id)
            
            objects_to_check = next_pass_objects
            
            if not has_nested_blocks:
                final_raw_objects = objects_to_check
                break
            
            if iteration > 50:
                print("Max nested depth reached.")
                final_raw_objects = objects_to_check
                break

        # ==============================================================================
        # STEP 3: FILTER MESHES
        # We only join meshes. We leave curves/points untouched in the scene.
        # ==============================================================================
        
        meshes_to_join = []
        
        for obj in final_raw_objects:
            if rs.IsMesh(obj):
                meshes_to_join.append(obj)

        if not meshes_to_join:
            print("No meshes found inside the blocks.")
            return

        # ==============================================================================
        # STEP 4: JOIN
        # ==============================================================================
        
        joined_mesh_id = None

        if len(meshes_to_join) > 1:
            joined_mesh_id = rs.JoinMeshes(meshes_to_join, delete_input=True)
        elif len(meshes_to_join) == 1:
            joined_mesh_id = meshes_to_join[0]

        if not joined_mesh_id:
            return

        # ==============================================================================
        # STEP 5: SPLIT DISJOINT
        # ==============================================================================
        
        final_parts = rs.SplitDisjointMesh(joined_mesh_id, delete_input=True)

        if not final_parts:
            final_parts = [joined_mesh_id]

        # ==============================================================================
        # STEP 6: LAYER ASSIGNMENT & GROUP
        # Force the final parts to be on the Target Layer (just to be safe)
        # ==============================================================================
        
        if final_parts:
            # Explicitly move geometry to the original block's layer
            rs.ObjectLayer(final_parts, target_layer_name)
            
            # Create Group
            group_name = rs.AddGroup()
            rs.AddObjectsToGroup(final_parts, group_name)
            
            # Select result
            rs.SelectObjects(final_parts)

    except Exception as e:
        rs.MessageBox("Error: {}".format(e), 0, "Error")

    finally:
        rs.EnableRedraw(True)
        print("Congratulations! Done.")

if __name__ == "__main__":
    process_nested_block_with_layer_sync()