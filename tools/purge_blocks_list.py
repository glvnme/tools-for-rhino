import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs

def remove_all_blocks_and_purge():
    """
    Deletes all block instances and their definitions from the Rhino project
    and purges the Block Manager.
    """
    # Get the active document
    doc = sc.doc
    
    # Access the InstanceDefinitionTable (the Block Manager)
    idef_table = doc.InstanceDefinitions
    
    # Get a list of all current definition indices
    idef_indices = [idef.Index for idef in idef_table]
    
    if not idef_indices:
        print("No block definitions found in the project.")
        return

    # UPDATED: Use .format() instead of f-strings for Python 2 compatibility
    print("Found {} block definitions. Removing...".format(len(idef_indices)))

    count = 0
    # Iterate through the indices and delete them
    for i in idef_indices:
        # Find the definition again by index to ensure it still exists
        # (Using the ID is safer during iteration)
        original_def = idef_table[i]
        if original_def:
            idef = idef_table.FindId(original_def.Id)
            
            if idef:
                # Delete the definition. 
                # true = delete references (instances) in the model
                # true = quiet mode (suppress warning dialogs)
                success = idef_table.Delete(idef.Index, True, True)
                if success:
                    count += 1

    # UPDATED: Use .format()
    print("Successfully deleted {} block definitions and their instances.".format(count))

    # FINAL PURGE
    # We run the native Purge command to ensure the Block Manager is completely clean.
    print("Running deep purge to clean Block Manager...")
    rs.Command("-_Purge _BlockDefinitions=_Yes _Materials=_No _Layers=_No _Linetypes=_No _AnnotationStyles=_No _Groups=_No _HatchPatterns=_No _Textures=_No _Environments=_No _Bitmaps=_No _Enter", False)
    
    # Refresh the Block Manager UI panel
    doc.Views.Redraw()
    print("Block Manager fully purged.")

if __name__ == "__main__":
    remove_all_blocks_and_purge()