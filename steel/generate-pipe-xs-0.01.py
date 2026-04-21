#! python3
import rhinoscriptsyntax as rs
import scriptcontext as sc
import math

def create_structural_pipe():
    # ------------------------------------------------------------------
    # 1. DATA SET: Structural Steel Pipe Sizes (STD & XS)
    #    Expanded to 31 items (1/8" to 10")
    # ------------------------------------------------------------------
    pipe_data = {
        # --- SMALLER XS SIZES ---
        "1/8 Inch XS":   [0.405, 0.095],
        "1/4 Inch XS":   [0.540, 0.119],
        "3/8 Inch XS":   [0.675, 0.126],

        # --- 1/2" to 10" (STD & XS) ---
        "1/2 Inch STD":  [0.840, 0.109],
        "1/2 Inch XS":   [0.840, 0.147],
        
        "3/4 Inch STD":  [1.050, 0.113],
        "3/4 Inch XS":   [1.050, 0.154],
        
        "1 Inch STD":    [1.315, 0.133],
        "1 Inch XS":     [1.315, 0.179],
        
        "1-1/4 Inch STD":[1.660, 0.140],
        "1-1/4 Inch XS": [1.660, 0.191],
        
        "1-1/2 Inch STD":[1.900, 0.145],
        "1-1/2 Inch XS": [1.900, 0.200],
        
        "2 Inch STD":    [2.375, 0.154],
        "2 Inch XS":     [2.375, 0.218],
        
        "2-1/2 Inch STD":[2.875, 0.203],
        "2-1/2 Inch XS": [2.875, 0.276],
        
        "3 Inch STD":    [3.500, 0.216],
        "3 Inch XS":     [3.500, 0.300],
        
        "3-1/2 Inch STD":[4.000, 0.226],
        "3-1/2 Inch XS": [4.000, 0.318],
        
        "4 Inch STD":    [4.500, 0.237],
        "4 Inch XS":     [4.500, 0.337],
        
        "5 Inch STD":    [5.563, 0.258],
        "5 Inch XS":     [5.563, 0.375],
        
        "6 Inch STD":    [6.625, 0.280],
        "6 Inch XS":     [6.625, 0.432],
        
        "8 Inch STD":    [8.625, 0.322],
        "8 Inch XS":     [8.625, 0.500],
        
        "10 Inch STD":   [10.750, 0.365],
        "10 Inch XS":    [10.750, 0.500]
    }

    # ------------------------------------------------------------------
    # 2. USER INPUT
    # ------------------------------------------------------------------
    pt_start = rs.GetPoint("Select Start Point of Pipe Axis")
    if not pt_start: return

    pt_end = rs.GetPoint("Select End Point of Pipe Axis", pt_start)
    if not pt_end: return
    
    if rs.Distance(pt_start, pt_end) < 0.001:
        rs.MessageBox("Start and End points are too close.")
        return

    # Calculate Axis Vector
    vec_axis = rs.VectorCreate(pt_end, pt_start)
    length = rs.VectorLength(vec_axis)

    # ------------------------------------------------------------------
    # 3. UI SELECTION
    # ------------------------------------------------------------------
    options = list(pipe_data.keys())
    # Sort by Outer Diameter (first item in value list)
    options.sort(key=lambda name: (pipe_data[name][0], name))
    
    selected_name = rs.ListBox(options, "Select Pipe Profile Size:", "Pipe Generator")
    if not selected_name: return 

    # Dimensions
    od = pipe_data[selected_name][0]
    wall = pipe_data[selected_name][1]
    id = od - (2 * wall)
    
    # ------------------------------------------------------------------
    # 4. GEOMETRY GENERATION
    # ------------------------------------------------------------------
    # Turn off redraw to hide steps
    rs.EnableRedraw(False)
    
    # A. Create Plane
    plane = rs.PlaneFromNormal(pt_start, vec_axis)
    
    # B. Create Circles
    radius_od = od / 2.0
    radius_id = id / 2.0
    
    crv_od_id = rs.AddCircle(plane, radius_od)
    crv_id_id = rs.AddCircle(plane, radius_id)
    
    # C. Create Planar Surface (Ring)
    temp_srf_ids = rs.AddPlanarSrf([crv_od_id, crv_id_id])
    
    if not temp_srf_ids:
        # Restore redraw if failed
        rs.EnableRedraw(True)
        rs.MessageBox("Failed to create planar surface.")
        return
        
    temp_srf_id = temp_srf_ids[0]
    
    # D. Extrude
    path_line_id = rs.AddLine(pt_start, pt_end)
    pipe_obj_id = rs.ExtrudeSurface(temp_srf_id, path_line_id, cap=True)
    
    # ------------------------------------------------------------------
    # 5. CLEANUP
    # ------------------------------------------------------------------
    rs.DeleteObjects([crv_od_id, crv_id_id, temp_srf_id, path_line_id])

    if not pipe_obj_id:
        rs.EnableRedraw(True)
        rs.MessageBox("Failed to generate pipe geometry.")
        return

    # ------------------------------------------------------------------
    # 6. METADATA
    # ------------------------------------------------------------------
    rs.ObjectName(pipe_obj_id, selected_name)
    
    rs.SetUserText(pipe_obj_id, "PipeName", selected_name)
    rs.SetUserText(pipe_obj_id, "OD", "{:.3f}".format(od))
    rs.SetUserText(pipe_obj_id, "ID", "{:.3f}".format(id))
    rs.SetUserText(pipe_obj_id, "WallThickness", "{:.3f}".format(wall))
    rs.SetUserText(pipe_obj_id, "Length", "{:.3f}".format(length))

    rs.SelectObject(pipe_obj_id)
    
    # Restore Redraw
    rs.EnableRedraw(True)
    print("Created {} | Length: {:.2f}".format(selected_name, length))

if __name__ == "__main__":
    create_structural_pipe()