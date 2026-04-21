import rhinoscriptsyntax as rs
import Rhino
import scriptcontext as sc

def assign_material_from_object_color():
    """
    Assigns a material to selected objects with the color of each object.
    If a material with the same color already exists, it will be reused.
    """
    # Get the objects to process from the user
    object_ids = rs.GetObjects("Select objects to assign material by color", preselect=True)
    if not object_ids:
        print "No objects selected."
        return

    # Keep track of colors and their corresponding material indices
    color_material_map = {}

    for obj_id in object_ids:
        # Get the object's color
        obj_color = rs.ObjectColor(obj_id)

        # Check if a material for this color already exists
        if obj_color.ToArgb() in color_material_map:
            material_index = color_material_map[obj_color.ToArgb()]
        else:
            # Create a new material
            new_material = Rhino.DocObjects.Material()
            new_material.DiffuseColor = obj_color
            new_material.Name = "ObjectColor_{}_{}_{}".format(obj_color.R, obj_color.G, obj_color.B)

            # Add the material to the document
            material_index = sc.doc.Materials.Add(new_material)
            if material_index < 0:
                print "Error adding material for object {}.".format(obj_id)
                continue
            
            # Store the new material index in our map
            color_material_map[obj_color.ToArgb()] = material_index

        # Assign the material to the object
        rhino_object = sc.doc.Objects.Find(obj_id)
        if rhino_object:
            rhino_object.Attributes.MaterialIndex = material_index
            rhino_object.Attributes.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
            rhino_object.CommitChanges()

    # Redraw the viewports to see the changes
    rs.Redraw()
    print "Material assignment complete."

if __name__ == "__main__":
    assign_material_from_object_color()