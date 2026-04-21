import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import Rhino
import scriptcontext as sc
import copy
import re
import System.Drawing

# ==============================================================================
# 1. HELPER: UNIT CONVERSION
# ==============================================================================
def parse_length_to_model_units(input_str):
    if not input_str: return 0.0
    s = input_str.lower().strip()
    if s == "0": return 0.0
    match = re.match(r"([0-9.]+)\s*([a-z]*)", s)
    if not match: return 0.0
    value = float(match.group(1))
    unit_str = match.group(2)
    if not unit_str: return value 
    unit_map = {
        "mm": Rhino.UnitSystem.Millimeters, "cm": Rhino.UnitSystem.Centimeters,
        "m": Rhino.UnitSystem.Meters, "in": Rhino.UnitSystem.Inches,
        "inch": Rhino.UnitSystem.Inches, "inches": Rhino.UnitSystem.Inches,
        "ft": Rhino.UnitSystem.Feet, "feet": Rhino.UnitSystem.Feet,
        "yd": Rhino.UnitSystem.Yards
    }
    source_unit = unit_map.get(unit_str)
    if source_unit is None: return value
    target_unit = rs.UnitSystem()
    scale = Rhino.RhinoMath.UnitScale(source_unit, target_unit)
    return value * scale

# ==============================================================================
# 2. USER INTERFACE
# ==============================================================================
def get_user_settings():
    setting_labels = ["U Divisions", "V Divisions", "Iterations", "Damping", "Edge Tension", "Default Link Length"]
    setting_defaults = ["10", "10", "50", "0.5", "0.5", "0"]
    results = rs.PropertyListBox(setting_labels, setting_defaults, "Form-Finding Settings")
    if not results: return None
    try:
        u_div = int(results[0])
        v_div = int(results[1])
        iterations = int(results[2])
        damping = float(results[3])
        edge_tension = float(results[4])
        link_length = parse_length_to_model_units(results[5])
        if u_div < 1 or v_div < 1: raise ValueError
        return u_div, v_div, iterations, damping, edge_tension, link_length
    except:
        return None

# ==============================================================================
# 3. GEOMETRY SETUP
# ==============================================================================
def get_initial_setup(surface_id, manual_link_ids, u_div, v_div, default_link_length):
    if not rs.IsSurface(surface_id): return None, None
    srf_obj = rs.coercesurface(surface_id)
    dom_u = srf_obj.Domain(0)
    dom_v = srf_obj.Domain(1)
    
    corners = [
        srf_obj.PointAt(dom_u.Min, dom_v.Min),
        srf_obj.PointAt(dom_u.Max, dom_v.Min),
        srf_obj.PointAt(dom_u.Max, dom_v.Max),
        srf_obj.PointAt(dom_u.Min, dom_v.Max)
    ]
    
    manual_lines = []
    if manual_link_ids:
        manual_lines = [rs.coercecurve(uid) for uid in manual_link_ids]

    fabric_start_corners = []
    corner_constraints = [] 
    center_pt = srf_obj.PointAt((dom_u.Min+dom_u.Max)/2.0, (dom_v.Min+dom_v.Max)/2.0)
    tolerance = rs.UnitAbsoluteTolerance() * 10

    for i, corner in enumerate(corners):
        found_manual = False
        for crv in manual_lines:
            if not crv: continue
            start = crv.PointAtStart
            end = crv.PointAtEnd
            length = crv.GetLength()
            external_anchor = None
            
            # Manual Link: Node on surface, Anchor away
            if start.DistanceTo(corner) < tolerance:
                external_anchor = end
            elif end.DistanceTo(corner) < tolerance:
                external_anchor = start
            
            if external_anchor:
                fabric_start_corners.append(corner) 
                corner_constraints.append({'anchor': external_anchor, 'length': length})
                found_manual = True
                break
        
        if not found_manual:
            if default_link_length > 0:
                vec = center_pt - corner
                dist = vec.Length
                start_pt = center_pt if dist <= default_link_length else corner + (vec/dist * default_link_length)
                fabric_start_corners.append(start_pt)
                corner_constraints.append({'anchor': corner, 'length': default_link_length})
            else:
                fabric_start_corners.append(corner)
                corner_constraints.append({'anchor': corner, 'length': 0.0})

    grid_surface = rg.NurbsSurface.CreateFromCorners(
        fabric_start_corners[0], fabric_start_corners[1], 
        fabric_start_corners[2], fabric_start_corners[3]
    )
    
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
            row.append(grid_surface.PointAt(u_param, v_param))
        point_grid.append(row)

    anchor_map = {
        (0, 0): corner_constraints[0], (u_count-1, 0): corner_constraints[1],
        (u_count-1, v_count-1): corner_constraints[2], (0, v_count-1): corner_constraints[3]
    }
    return point_grid, anchor_map

# ==============================================================================
# 4. RELAXATION ENGINE
# ==============================================================================
def run_form_finding_relaxation(point_grid, anchor_map, iterations, damping, edge_tension):
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
                constraint = anchor_map.get((u,v))
                
                if is_corner and constraint and constraint['length'] <= 0: continue

                avg_pt = None
                if is_corner:
                    neighbors = []
                    if u == 0: neighbors.append(point_grid[u+1][v])
                    else: neighbors.append(point_grid[u-1][v])
                    if v == 0: neighbors.append(point_grid[u][v+1])
                    else: neighbors.append(point_grid[u][v-1])
                    sx, sy, sz = 0,0,0
                    for n in neighbors: sx+=n.X; sy+=n.Y; sz+=n.Z
                    if neighbors: avg_pt = rg.Point3d(sx/len(neighbors), sy/len(neighbors), sz/len(neighbors))
                elif u == 0 or u == u_count - 1:
                    p_up = point_grid[u][v+1]; p_down = point_grid[u][v-1]
                    p_side = point_grid[u+1 if u==0 else u-1][v]
                    total = 2*weight_edge + weight_internal
                    avg_pt = (p_up*weight_edge + p_down*weight_edge + p_side*weight_internal) / total
                elif v == 0 or v == v_count - 1:
                    p_left = point_grid[u-1][v]; p_right = point_grid[u+1][v]
                    p_side = point_grid[u][v+1 if v==0 else v-1]
                    total = 2*weight_edge + weight_internal
                    avg_pt = (p_left*weight_edge + p_right*weight_edge + p_side*weight_internal) / total
                else:
                    n = [point_grid[u-1][v], point_grid[u+1][v], point_grid[u][v-1], point_grid[u][v+1]]
                    sx, sy, sz = 0,0,0
                    for p in n: sx+=p.X; sy+=p.Y; sz+=p.Z
                    avg_pt = rg.Point3d(sx/4, sy/4, sz/4)
                
                if avg_pt:
                    move = avg_pt - current_pt
                    damped = move * damping
                    candidate = current_pt + damped
                    if is_corner and constraint and constraint['length'] > 0:
                        anchor = constraint['anchor']
                        target_len = constraint['length']
                        link_vec = candidate - anchor
                        if link_vec.Length < 0.001: link_vec = rg.Vector3d(0,0,1)
                        link_vec.Unitize()
                        new_point_grid[u][v] = anchor + (link_vec * target_len)
                    else:
                        new_point_grid[u][v] = candidate
        point_grid = new_point_grid
        if (i+1) % 10 == 0: rs.Prompt("Iteration {}/{}".format(i+1, iterations))
    return point_grid

# ==============================================================================
# 5. ROBUST GEOMETRY OUTPUT
# ==============================================================================
def create_geometry_from_grid(final_grid, anchor_map, original_srf_id):
    if not final_grid: return

    u_count = len(final_grid)
    v_count = len(final_grid[0])
    
    # 1. Flatten Points (V varies slowly, U varies quickly)
    flat_points = []
    for v in range(v_count):
        for u in range(u_count):
            flat_points.append(final_grid[u][v])
            
    # 2. Calculate Degree
    u_degree = 3 if u_count > 3 else 1
    v_degree = 3 if v_count > 3 else 1
    
    # 3. Create Surface
    new_surface = rs.AddSrfPtGrid((u_count, v_count), flat_points, (u_degree, v_degree))
    
    # 4. Apply Attributes (CRITICAL FIX: Copy manually, do not match entire block)
    if new_surface and original_srf_id:
        rs.ObjectName(new_surface, "Form-Found_Surface")
        
        # Manually copy essential attributes to avoid copying "Hidden=True"
        orig_layer = rs.ObjectLayer(original_srf_id)
        orig_color = rs.ObjectColor(original_srf_id)
        orig_mat_source = rs.ObjectMaterialSource(original_srf_id)
        
        rs.ObjectLayer(new_surface, orig_layer)
        rs.ObjectColor(new_surface, orig_color)
        rs.ObjectMaterialSource(new_surface, orig_mat_source)
        
        # Force visible just in case
        rs.ShowObject(new_surface)

    # 5. Fallback: If surface failed, make a Mesh so user sees *something*
    if not new_surface:
        print("Surface failed to resolve. Creating Mesh fallback.")
        mesh = rg.Mesh()
        for pt in flat_points: mesh.Vertices.Add(pt)
        for v in range(v_count - 1):
            for u in range(u_count - 1):
                i = v * u_count + u
                mesh.Faces.AddFace(i, i + 1, i + u_count + 1, i + u_count)
        mesh_id = sc.doc.Objects.AddMesh(mesh)
        if mesh_id and original_srf_id:
            rs.ObjectLayer(mesh_id, rs.ObjectLayer(original_srf_id))
            rs.ObjectColor(mesh_id, rs.ObjectColor(original_srf_id))

    # 6. Edges (Magenta)
    edge_layer = rs.AddLayer("Fabric_Edges", (255, 0, 255))
    edge_pts_sets = [
        [final_grid[u][0] for u in range(u_count)],
        [final_grid[u][-1] for u in range(u_count)],
        [final_grid[0][v] for v in range(v_count)],
        [final_grid[-1][v] for v in range(v_count)]
    ]
    for pts in edge_pts_sets:
        if len(pts) > 1:
            crv = rs.AddInterpCurve(pts, degree=3) if len(pts) > 2 else rs.AddPolyline(pts)
            if crv: rs.ObjectLayer(crv, edge_layer)

    # 7. Links (Red)
    link_layer = rs.AddLayer("Structural_Links", (255, 0, 0))
    for key, data in anchor_map.items():
        if data['length'] > 0:
            u, v = key
            line = rs.AddLine(data['anchor'], final_grid[u][v])
            if line: rs.ObjectLayer(line, link_layer)
            
    print("Geometry generated.")

# ==============================================================================
# 6. MAIN EXECUTION
# ==============================================================================
def main():
    try:
        settings = get_user_settings()
        if not settings: return
        u_div, v_div, iterations, damping, edge_tension, def_link_len = settings

        srf_id = rs.GetObject("Select base NURBS surface", 8, preselect=True)
        if not srf_id: return
        
        rs.UnselectAllObjects()
        line_ids = rs.GetObjects("Select LINK LINES (Optional)", 4)
        
        rs.EnableRedraw(False)
        rs.HideObject(srf_id)
        
        initial_grid, anchor_map = get_initial_setup(srf_id, line_ids, u_div, v_div, def_link_len)
        
        if initial_grid:
            final_grid = run_form_finding_relaxation(initial_grid, anchor_map, iterations, damping, edge_tension)
            create_geometry_from_grid(final_grid, anchor_map, srf_id)
            
    except Exception as e:
        print("Error: {}".format(e))
    finally:
        rs.EnableRedraw(True)

if __name__ == "__main__":
    main()