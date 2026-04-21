import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import Rhino
import copy
import re
import math

# ==============================================================================
# 1. HELPER: UNIT CONVERSION
# ==============================================================================

def parse_length_to_model_units(input_str):
    """
    Parses a string like "1 inch", "200 mm", "0.5 ft" and converts it 
    to the current Rhino document's model units.
    If no unit is specified (e.g. "5"), assumes Model Units.
    Returns 0.0 if input is 0 or invalid.
    """
    if not input_str: return 0.0
    
    # Normalize input: lowercase and strip spaces
    s = input_str.lower().strip()
    
    # If it's just "0", return 0
    if s == "0": return 0.0

    # Regex to separate number and text
    match = re.match(r"([0-9.]+)\s*([a-z]*)", s)
    if not match:
        return 0.0
        
    value = float(match.group(1))
    unit_str = match.group(2)
    
    if not unit_str:
        return value # No unit provided, assume model units

    # Map string to Rhino UnitSystem
    unit_map = {
        "mm": Rhino.UnitSystem.Millimeters,
        "cm": Rhino.UnitSystem.Centimeters,
        "m": Rhino.UnitSystem.Meters,
        "in": Rhino.UnitSystem.Inches,
        "inch": Rhino.UnitSystem.Inches,
        "inches": Rhino.UnitSystem.Inches,
        "ft": Rhino.UnitSystem.Feet,
        "feet": Rhino.UnitSystem.Feet,
        "yd": Rhino.UnitSystem.Yards
    }
    
    source_unit = unit_map.get(unit_str)
    
    if source_unit is None:
        print("Warning: Unit '{}' not recognized. Assuming Model Units.".format(unit_str))
        return value
        
    # Get current model units
    target_unit = rs.UnitSystem()
    
    # Calculate scale factor
    scale = Rhino.RhinoMath.UnitScale(source_unit, target_unit)
    converted_value = value * scale
    
    print("Input '{}' converted to {:.4f} Model Units".format(input_str, converted_value))
    return converted_value

# ==============================================================================
# 2. USER INTERFACE FUNCTION
# ==============================================================================

def get_user_settings():
    """
    Displays a pop-up window for simulation parameters, including Link Length.
    """
    setting_labels = [
        "U Divisions", 
        "V Divisions", 
        "Iterations", 
        "Damping", 
        "Edge Tension",
        "Link Length (e.g. '1 inch', '0' for none)"
    ]
    setting_defaults = ["10", "10", "50", "0.5", "0.5", "0"]
    
    results = rs.PropertyListBox(setting_labels, setting_defaults, "Form-Finding Settings")

    if not results: return None

    try:
        u_div = int(results[0])
        v_div = int(results[1])
        iterations = int(results[2])
        damping = float(results[3])
        edge_tension = float(results[4])
        link_length_str = results[5]
        
        # Parse the link length string to a float in model units
        link_length = parse_length_to_model_units(link_length_str)
        
        if u_div < 1 or v_div < 1 or iterations < 1 or not (0.0 < damping <= 1.0) or not (0.0 <= edge_tension):
            raise ValueError("One or more settings are out of the valid range.")
            
        return u_div, v_div, iterations, damping, edge_tension, link_length
        
    except (ValueError, TypeError) as e:
        print("Error: Invalid input. Details: {}".format(e))
        return None

# ==============================================================================
# 3. GEOMETRY GENERATION (WITH LINKS LOGIC)
# ==============================================================================

def get_initial_setup(surface_id, u_div, v_div, link_length):
    """
    Generates the point grid. 
    If link_length > 0, it offsets the corners inwards and generates the grid 
    between the NEW locations, while returning the OLD corners as anchors.
    """
    if not rs.IsSurface(surface_id): return None, None

    srf_obj = rs.coercesurface(surface_id)
    
    # Get the 4 corners of the original surface (Anchors)
    dom_u = srf_obj.Domain(0)
    dom_v = srf_obj.Domain(1)
    
    corners = [
        srf_obj.PointAt(dom_u.Min, dom_v.Min), # 0,0
        srf_obj.PointAt(dom_u.Max, dom_v.Min), # 1,0
        srf_obj.PointAt(dom_u.Max, dom_v.Max), # 1,1
        srf_obj.PointAt(dom_u.Min, dom_v.Max)  # 0,1
    ]
    
    anchors = corners # These are the fixed points on the frame

    # Determine the surface to generate grid from
    grid_surface = srf_obj # Default to original

    if link_length > 0:
        print("Link length detected. Offsetting surface corners inwards...")
        
        # Calculate center of surface roughly
        center = srf_obj.PointAt((dom_u.Min+dom_u.Max)/2.0, (dom_v.Min+dom_v.Max)/2.0)
        
        new_corners = []
        for corner in corners:
            vec = center - corner
            dist = vec.Length
            
            if dist <= link_length:
                print("Warning: Link length is larger than surface radius! Using center point.")
                new_corners.append(center)
            else:
                vec.Unitize()
                move_vec = vec * link_length
                new_pt = corner + move_vec
                new_corners.append(new_pt)
        
        # Create a temporary surface from the new inset corners to generate the grid
        # Using 4 points to make a surface
        grid_surface = rg.NurbsSurface.CreateFromCorners(
            new_corners[0], new_corners[1], new_corners[2], new_corners[3]
        )
    
    # Generate the grid
    print("Generating a {}x{} division grid...".format(u_div, v_div))
    u_domain = grid_surface.Domain(0)
    v_domain = grid_surface.Domain(1)
    
    point_grid = []
    u_count = u_div + 1
    v_count = v_div + 1

    for i in range(u_count):
        row = []
        u_norm = float(i) / u_div
        u_param = u_domain[0] + u_norm * (u_domain[1] - u_domain[0])
        for j in range(v_count):
            v_norm = float(j) / v_div
            v_param = v_domain[0] + v_norm * (v_domain[1] - v_domain[0])
            point = grid_surface.PointAt(u_param, v_param)
            row.append(point)
        point_grid.append(row)

    # Map anchors to grid positions for easy lookup
    # grid[0][0], grid[-1][0], grid[-1][-1], grid[0][-1]
    anchor_map = {
        (0, 0): anchors[0],
        (u_count-1, 0): anchors[1],
        (u_count-1, v_count-1): anchors[2],
        (0, v_count-1): anchors[3]
    }
        
    return point_grid, anchor_map

# ==============================================================================
# 4. RELAXATION SIMULATION
# ==============================================================================

def run_form_finding_relaxation(point_grid, anchor_map, iterations, damping, edge_tension, link_length):
    """
    Runs the relaxation.
    - If link_length > 0, corners are treated as constrained moving particles.
    - If link_length == 0, corners are fixed.
    """
    if not point_grid: return None
        
    u_count = len(point_grid)
    v_count = len(point_grid[0])
    
    weight_edge = 1.0 + edge_tension
    weight_internal = 1.0
    
    for i in range(iterations):
        new_point_grid = copy.deepcopy(point_grid)

        for u in range(u_count):
            for v in range(v_count):
                
                current_pt = point_grid[u][v]
                is_corner = (u == 0 or u == u_count - 1) and (v == 0 or v == v_count - 1)
                
                # --- CASE A: FIXED CORNERS (No Links) ---
                if is_corner and link_length <= 0:
                    continue

                avg_pt = None
                
                # 1. CALCULATE PULL FROM NEIGHBORS (Smoothed Position)
                
                # Corner Point (Only processes if Links > 0)
                if is_corner:
                    # Get the two neighbors connected to the corner
                    neighbors = []
                    if u == 0: neighbors.append(point_grid[u+1][v])
                    else: neighbors.append(point_grid[u-1][v])
                    
                    if v == 0: neighbors.append(point_grid[u][v+1])
                    else: neighbors.append(point_grid[u][v-1])
                    
                    # Average pull from fabric
                    sx, sy, sz = 0,0,0
                    for n in neighbors:
                        sx += n.X; sy += n.Y; sz += n.Z
                    avg_pt = rg.Point3d(sx/2, sy/2, sz/2)

                # Edge Point (Left/Right)
                elif u == 0 or u == u_count - 1:
                    p_up = point_grid[u][v + 1]
                    p_down = point_grid[u][v - 1]
                    p_side = point_grid[u + 1 if u == 0 else u - 1][v]
                    total_weight = 2 * weight_edge + weight_internal
                    avg_x = (weight_edge * (p_up.X + p_down.X) + weight_internal * p_side.X) / total_weight
                    avg_y = (weight_edge * (p_up.Y + p_down.Y) + weight_internal * p_side.Y) / total_weight
                    avg_z = (weight_edge * (p_up.Z + p_down.Z) + weight_internal * p_side.Z) / total_weight
                    avg_pt = rg.Point3d(avg_x, avg_y, avg_z)

                # Edge Point (Top/Bottom)
                elif v == 0 or v == v_count - 1:
                    p_left = point_grid[u - 1][v]
                    p_right = point_grid[u + 1][v]
                    p_side = point_grid[u][v + 1 if v == 0 else v - 1]
                    total_weight = 2 * weight_edge + weight_internal
                    avg_x = (weight_edge * (p_left.X + p_right.X) + weight_internal * p_side.X) / total_weight
                    avg_y = (weight_edge * (p_left.Y + p_right.Y) + weight_internal * p_side.Y) / total_weight
                    avg_z = (weight_edge * (p_left.Z + p_right.Z) + weight_internal * p_side.Z) / total_weight
                    avg_pt = rg.Point3d(avg_x, avg_y, avg_z)

                # Internal Point
                else:
                    neighbors = [
                        point_grid[u - 1][v], point_grid[u + 1][v],
                        point_grid[u][v - 1], point_grid[u][v + 1]
                    ]
                    sum_x, sum_y, sum_z = 0.0, 0.0, 0.0
                    for pt in neighbors:
                        sum_x += pt.X; sum_y += pt.Y; sum_z += pt.Z
                    num_neighbors = len(neighbors)
                    avg_pt = rg.Point3d(sum_x/num_neighbors, sum_y/num_neighbors, sum_z/num_neighbors)
                
                # 2. APPLY MOVEMENT & DAMPING
                if avg_pt:
                    move_vector = rs.VectorCreate(avg_pt, current_pt)
                    damped_vector = rs.VectorScale(move_vector, damping)
                    candidate_pos = rs.PointAdd(current_pt, damped_vector)
                    
                    # 3. CONSTRAINT: LINK LENGTH (Only for corners if links exist)
                    if is_corner and link_length > 0:
                        fixed_anchor = anchor_map[(u, v)]
                        
                        # Create vector from Anchor -> Candidate Position
                        link_vec = rs.VectorCreate(candidate_pos, fixed_anchor)
                        
                        # Force vector length to be exactly link_length (Rigid Link)
                        # Note: To simulate a cable that can go slack, check if length > link_length.
                        # But for form finding, we usually assume tension.
                        link_vec.Unitize()
                        corrected_vec = rs.VectorScale(link_vec, link_length)
                        
                        # Final position is Anchor + Rigid Vector
                        final_pos = rs.PointAdd(fixed_anchor, corrected_vec)
                        new_point_grid[u][v] = final_pos
                    else:
                        new_point_grid[u][v] = candidate_pos

        point_grid = new_point_grid
        if (i + 1) % 10 == 0:
            print("Completed iteration {} of {}...".format(i + 1, iterations))

    print("Form-finding simulation complete.")
    return point_grid

def create_geometry_from_grid(final_grid, anchor_map, link_length):
    """
    Generates the surface, edge curves, and optionally the link lines.
    """
    if not final_grid: return

    flat_points = [point for row in final_grid for point in row]
    u_count = len(final_grid)
    v_count = len(final_grid[0])
    degree = 3
    
    new_surface = rs.AddSrfPtGrid((u_count, v_count), flat_points, (degree, degree), (False, False))
    
    if new_surface:
        rs.ObjectName(new_surface, "Form-Found_Surface")
        print("Successfully generated the final NURBS surface.")
    
    # Draw Edges
    edge_points_bottom = final_grid[0]
    edge_points_top = final_grid[-1]
    edge_points_left = [row[0] for row in final_grid]
    edge_points_right = [row[-1] for row in final_grid]

    rs.ObjectName(rs.AddPolyline(edge_points_bottom), "Edge_Curve_Bottom")
    rs.ObjectName(rs.AddPolyline(edge_points_top), "Edge_Curve_Top")
    rs.ObjectName(rs.AddPolyline(edge_points_left), "Edge_Curve_Left")
    rs.ObjectName(rs.AddPolyline(edge_points_right), "Edge_Curve_Right")
    
    # Draw Links if they exist
    if link_length > 0:
        link_layer = rs.AddLayer("Structural_Links", (255, 0, 0))
        
        # Corners of the grid
        corners_indices = [(0,0), (u_count-1, 0), (u_count-1, v_count-1), (0, v_count-1)]
        
        for (u, v) in corners_indices:
            mesh_pt = final_grid[u][v]
            anchor_pt = anchor_map[(u, v)]
            line = rs.AddLine(anchor_pt, mesh_pt)
            rs.ObjectLayer(line, link_layer)
            
        print("Generated structural links connecting fabric to original anchors.")

# ==============================================================================
# 5. MAIN EXECUTION
# ==============================================================================

def main():
    print("--- Starting Surface Form-Finding Script with Links ---")
    
    settings = get_user_settings()
    if not settings:
        print("Operation cancelled by user.")
        return
        
    u_div, v_div, iterations, damping, edge_tension, link_length = settings

    input_surface_id = rs.GetObject("Select an initial NURBS surface", 8, preselect=True)
    if not input_surface_id:
        print("No surface selected. Operation cancelled.")
        return

    rs.HideObject(input_surface_id)
    
    # Generate Grid (Handles Offset if Links > 0)
    initial_grid, anchor_map = get_initial_setup(input_surface_id, u_div, v_div, link_length)
    
    if initial_grid:
        # Run Physics (Handles Link Constraints)
        final_grid = run_form_finding_relaxation(initial_grid, anchor_map, iterations, damping, edge_tension, link_length)
        
        if final_grid:
            create_geometry_from_grid(final_grid, anchor_map, link_length)

    print("--- Script finished. ---")

if __name__ == "__main__":
    main()