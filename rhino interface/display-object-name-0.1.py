import rhinoscriptsyntax as rs

def show_selected_object_names():
    # Get all selected objects
    objects = rs.SelectedObjects()
    
    # If no objects are selected, prompt user to select them
    if not objects:
        print("No objects selected. Please select objects now...")
        objects = rs.GetObjects("Select objects", filter=0)  # 0 = all objects
        
        # Check if user cancelled selection
        if not objects:
            print("No objects selected")
            return
    
    # Print each object's name
    for i, obj in enumerate(objects):
        name = rs.ObjectName(obj)
        if name:
            print("Object {0}: {1}".format(i+1, name))
        else:
            print("Object {0}: (unnamed)".format(i+1))

# Run the function
show_selected_object_names()
