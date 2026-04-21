import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino

def iterative_mesh_smooth_by_tolerance():
    """
    Iteratively smooths a mesh until the maximum vertex displacement in one
    iteration is below a specified tolerance.
    """
    # 1. Get user to select a mesh
    mesh_guid = rs.GetObject("Select a mesh to smooth", 32, True, False)
    if not mesh_guid:
        print "No mesh selected."
        return

    # 2. Get the tolerance threshold from the user
    # Determine the current model units to inform the user in the prompt
    # --- THIS LINE HAS BEEN CORRECTED ---
    model_units = rs.UnitSystemName() 
    
    tolerance = rs.GetReal(
        message="Enter the maximum displacement tolerance in current model units ({})".format(model_units),
        number=1.0,  # Default value of 1.0
        minimum=0.0
    )
    if tolerance is None or tolerance <= 0:
        print "Invalid tolerance specified. Operation cancelled."
        return

    # Get the actual mesh geometry from its ID
    mesh = rs.coercemesh(mesh_guid)
    if not mesh:
        print "Failed to get mesh geometry."
        return

    # --- Iteration Loop ---
    iteration_count = 0
    max_iterations = 1000  # Safety limit to prevent infinite loops

    print "Starting iterative smoothing..."
    print "Target tolerance: < {:.4f} {}".format(tolerance, model_units)
    
    while iteration_count < max_iterations:
        iteration_count += 1
        
        # Store the vertex positions before smoothing
        # Using ToPoint3dArray() is an efficient way to get all vertices at once
        pre_smooth_vertices = mesh.Vertices.ToPoint3dArray()

        # Duplicate the mesh to perform the next smoothing operation on it
        smoothed_mesh = mesh.DuplicateMesh()
        
        # Perform a single smoothing pass.
        # The parameters for Smooth are (iterations, smoothX, smoothY, smoothZ, fixBoundaries, coordinateSystem)
        # We use 1 iteration here since we are controlling the looping ourselves.
        smoothed_mesh.Smooth(1, True, True, True, True, Rhino.Geometry.SmoothingCoordinateSystem.World)

        # Get vertex positions after smoothing
        post_smooth_vertices = smoothed_mesh.Vertices.ToPoint3dArray()
        
        # 3. Calculate the maximum displacement for this iteration
        max_displacement = 0.0
        for i in range(len(pre_smooth_vertices)):
            distance = pre_smooth_vertices[i].DistanceTo(post_smooth_vertices[i])
            if distance > max_displacement:
                max_displacement = distance

        # Provide feedback to the user in the command line
        print "Iteration {}: Max vertex displacement = {:.4f}".format(iteration_count, max_displacement)

        # 4. Check if the displacement is within the tolerance
        if max_displacement < tolerance:
            print "\nSuccess: Displacement is within the tolerance threshold."
            # Replace the original mesh with the final smoothed version
            sc.doc.Objects.Replace(mesh_guid, smoothed_mesh)
            break  # Exit the loop

        # If tolerance not met, update the base mesh for the next iteration
        mesh = smoothed_mesh

        # Check if the loop is hitting the safety limit
        if iteration_count == max_iterations:
            print "\nWarning: Maximum number of iterations ({}) reached.".format(max_iterations)
            print "Replacing object with the last smoothed version."
            sc.doc.Objects.Replace(mesh_guid, smoothed_mesh)
            break

    # Redraw views to show the final result
    sc.doc.Views.Redraw()


# --- This is the standard boilerplate to run the function ---
if __name__ == "__main__":
    iterative_mesh_smooth_by_tolerance()