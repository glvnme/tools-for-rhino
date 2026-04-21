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
        "inch": Rhino.UnitSystem.Inches, "ft": Rhino.UnitSystem.Feet,
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
    labels = [
        "U Divisions", "V Divisions", "Iterations", "Damping", 
        "Edge Tension", "Ridge/Valley Tension", "Default Link Length"
    ]
    defaults = ["10", "10", "100", "0.5", "0.5", "1.0", "0"]
    results = rs.PropertyListBox(labels, defaults, "Form-Finding Settings")
    if not results: return None
    try:
        u_div = int(results[0])
        v_div = int(results[1])
        iters = int(results[2])
        damp = float(results[3])
        e_tens = float(results[4])
        r_tens = float(results[5])
        link_len = parse_length_to_model_units(results[6])
        if u_div < 1 or v_div < 1: raise ValueError
        return u_div, v_div, iters, damp, e_tens, r_tens, link_len
    except:
        return None

# ==============================================================================
# 3. TOPOLOGY & GRAPH GENERATION
# ==============================================================================
class Node:
    def __init__(self, pt, is_fixed=False, link_anchor=None, link_len=0.0):
        self.pos = pt
        self.is_fixed = is_fixed
        self.link_anchor = link_anchor
        self.link_len = link_len
        self.neighbors = [] 

def get_initial_setup(srf_id, link_ids, ridge_pts, u_div, v_div, def_link_len):
    if not rs.IsSurface(srf_id): return None, None, None

    srf_obj = rs.coercesurface(srf_id)
    dom_u = srf_obj.Domain(0)
    dom_v = srf_obj.Domain(1)
    
    corners = [
        srf_obj.PointAt(dom_u.Min, dom_v.Min),
        srf_obj.PointAt(dom_u.Max, dom_v.Min),
        srf_obj.PointAt(dom_u.Max, dom_v.Max),
        srf_obj.PointAt(dom_u.Min, dom_v.Max)
    ]
    
    manual_lines = [rs.coercecurve(uid) for uid in link_ids] if link_ids else []
    corner_configs = []
    center_pt = srf_obj.PointAt((dom_u.Min+dom_u.Max)/2.0, (dom_v.Min+dom_v.Max)/2.0)
    
    for i, c in enumerate(corners):
        config = {'fixed': True, 'anchor': c, 'len': 0.0, 'pos': c}
        found = False
        for l in manual_lines:
            if not l: continue
            s, e = l.PointAtStart, l.PointAtEnd
            if s.DistanceTo(c) < 0.01: 
                config.update({'fixed': False, 'anchor': e, 'len': l.GetLength(), 'pos': c})
                found=True; break
            elif e.DistanceTo(c) < 0.01:
                config.update({'fixed': False, 'anchor': s, 'len': l.GetLength(), 'pos': c})
                found=True; break
        if not found and def_link_len > 0:
            vec = center_pt - c
            dist = vec.Length
            start_pt = center_pt if dist <= def_link_len else c + (vec/dist * def_link_len)
            config.update({'fixed': False, 'anchor': c, 'len': def_link_len, 'pos': start_pt})
        corner_configs.append(config)

    split_indices = None
    if ridge_pts and len(ridge_pts) == 2:
        idx0, idx1 = -1, -1
        min_d0, min_d1 = 1e9, 1e9
        for i, c in enumerate(corners):
            d = c.DistanceTo(ridge_pts[0])
            if d < min_d0: min_d0 = d; idx0 = i
            d = c.DistanceTo(ridge_pts[1])
            if d < min_d1: min_d1 = d; idx1 = i
        if {idx0, idx1} == {0, 2} or {idx0, idx1} == {1, 3}:
            split_indices = (idx0, idx1)

    nodes = []
    grids = []
    pos_map = {} 

    def add_node(pt, c_idx=-1):
        if c_idx != -1:
            cfg = corner_configs[c_idx]
            pt = cfg['pos']
        key = "{:.4f},{:.4f},{:.4f}".format(pt.X, pt.Y, pt.Z)
        if key in pos_map: return pos_map[key]
        n = Node(pt)
        if c_idx != -1:
            cfg = corner_configs[c_idx]
            n.is_fixed = cfg['fixed']
            n.link_anchor = cfg['anchor']
            n.link_len = cfg['len']
        idx = len(nodes)
        nodes.append(n)
        pos_map[key] = idx
        return idx

    patches = []
    
    if split_indices:
        # Radial Topology (Triangles)
        if {0, 2} == set(split_indices):
            patches.append({'tip': 1, 'b_start': 0, 'b_end': 2})
            patches.append({'tip': 3, 'b_start': 0, 'b_end': 2})
        else:
            patches.append({'tip': 0, 'b_start': 1, 'b_end': 3})
            patches.append({'tip': 2, 'b_start': 1, 'b_end': 3})
            
        for p in patches:
            tip_c, bs_c, be_c = p['tip'], p['b_start'], p['b_end']
            p_tip = corner_configs[tip_c]['pos']
            p_bs = corner_configs[bs_c]['pos']
            p_be = corner_configs[be_c]['pos']
            
            uc, vc = u_div + 1, v_div + 1
            grid_idxs = []
            for v in range(vc):
                row = []
                v_norm = float(v) / float(v_div)
                for u in range(uc):
                    u_norm = float(u) / float(u_div)
                    base_pt = p_bs + (p_be - p_bs) * u_norm
                    final_pt = p_tip + (base_pt - p_tip) * v_norm
                    c_id = -1
                    if v == 0: c_id = tip_c
                    elif v == v_div and u == 0: c_id = bs_c
                    elif v == v_div and u == u_div: c_id = be_c
                    row.append(add_node(final_pt, c_id))
                grid_idxs.append(row)
            grids.append({'u': uc, 'v': vc, 'idxs': grid_idxs, 'type': 'tri'})
    else:
        # Quad Topology
        p0, p1 = corner_configs[0]['pos'], corner_configs[1]['pos']
        p2, p3 = corner_configs[2]['pos'], corner_configs[3]['pos']
        s_temp = rg.NurbsSurface.CreateFromCorners(p0, p1, p2, p3)
        uc, vc = u_div + 1, v_div + 1
        grid_idxs = []
        for u in range(uc):
            col = []
            for v in range(vc):
                u_p = s_temp.Domain(0)[0] + (u/float(u_div))*s_temp.Domain(0).Length
                v_p = s_temp.Domain(1)[0] + (v/float(v_div))*s_temp.Domain(1).Length
                pt = s_temp.PointAt(u_p, v_p)
                c_id = -1
                if u==0 and v==0: c_id=0
                elif u==u_div and v==0: c_id=1
                elif u==u_div and v==v_div: c_id=2
                elif u==0 and v==v_div: c_id=3
                col.append(add_node(pt, c_id))
            grid_idxs.append(col)
        grids.append({'u': uc, 'v': vc, 'idxs': grid_idxs, 'type': 'quad'})

    for g in grids:
        rows = g['idxs']
        is_tri = (g['type'] == 'tri')
        uc, vc = g['u'], g['v']
        
        if is_tri:
            for v in range(vc):
                for u in range(uc):
                    curr = rows[v][u]
                    ns = []
                    if v > 0: ns.append(rows[v-1][u])
                    if v < vc-1: ns.append(rows[v+1][u])
                    if u > 0: ns.append(rows[v][u-1])
                    if u < uc-1: ns.append(rows[v][u+1])
                    for n_idx in ns:
                        w = 1
                        if v == vc-1: w = 2
                        elif u == 0 or u == uc-1: w = 2
                        nodes[curr].neighbors.append((n_idx, w))
        else:
            for u in range(uc):
                for v in range(vc):
                    curr = rows[u][v]
                    ns = []
                    if u > 0: ns.append(rows[u-1][v])
                    if u < uc-1: ns.append(rows[u+1][v])
                    if v > 0: ns.append(rows[u][v-1])
                    if v < vc-1: ns.append(rows[u][v+1])
                    for n_idx in ns:
                        w = 1
                        if u==0 or u==uc-1 or v==0 or v==vc-1: w=2
                        nodes[curr].neighbors.append((n_idx, w))

    return nodes, grids, split_indices is not None

# ==============================================================================
# 4. RELAXATION ENGINE
# ==============================================================================
def solve_physics(nodes, iters, damping, e_tens, r_tens, is_split):
    print("Solving... Nodes: {}".format(len(nodes)))
    
    W_INT = 1.0
    W_EDGE = 1.0 + e_tens
    
    for k in range(iters):
        curr_pos = [n.pos for n in nodes]
        
        for i, n in enumerate(nodes):
            if n.is_fixed and n.link_len <= 0: continue
            
            sum_v = rg.Vector3d.Zero
            tot_w = 0
            
            for (n_idx, w_type) in n.neighbors:
                w = W_INT
                if w_type == 2: 
                    w = W_EDGE
                    if is_split: w += r_tens 
                
                pt = curr_pos[n_idx]
                vec = pt - rg.Point3d.Origin
                sum_v += vec * w
                tot_w += w
            
            if tot_w > 0:
                avg = rg.Point3d.Origin + (sum_v / tot_w)
                move = avg - n.pos
                n.pos += move * damping
                
                if n.link_anchor and n.link_len > 0:
                    l_vec = n.pos - n.link_anchor
                    if l_vec.Length < 0.001: l_vec = rg.Vector3d(0,0,1)
                    l_vec.Unitize()
                    n.pos = n.link_anchor + (l_vec * n.link_len)

        if k % 20 == 0: rs.Prompt("Iter {}/{}".format(k, iters))
    return nodes

# ==============================================================================
# 5. OUTPUT GEOMETRY (JOINED BREP)
# ==============================================================================
def generate_output(nodes, grids, orig_id):
    out_layer = rs.ObjectLayer(orig_id)
    out_col = rs.ObjectColor(orig_id)
    out_mat = rs.ObjectMaterialSource(orig_id)
    
    # List to hold individual Breps for joining
    temp_breps = []
    # Fallback list for Meshes if Nurbs fail
    temp_meshes = []
    
    # 1. Create individual surfaces
    for g in grids:
        uc, vc = g['u'], g['v']
        idxs = g['idxs']
        is_tri = (g['type'] == 'tri')
        
        flat_pts = []
        if is_tri:
            for v in range(vc):
                for u in range(uc):
                    flat_pts.append(nodes[idxs[v][u]].pos)
        else:
            for v in range(vc):
                for u in range(uc):
                    flat_pts.append(nodes[idxs[u][v]].pos)

        # Create Surface
        u_deg = 3 if uc > 3 else 1
        v_deg = 3 if vc > 3 else 1
        
        ns = rg.NurbsSurface.CreateFromPoints(flat_pts, uc, vc, u_deg, v_deg)
        
        if ns:
            temp_breps.append(ns.ToBrep())
        else:
            # Mesh Fallback
            mesh = rg.Mesh()
            for p in flat_pts: mesh.Vertices.Add(p)
            for i in range(len(flat_pts)-uc-1):
               # Simplified mesh face logic (approx)
               pass 
            temp_meshes.append(mesh) # Placeholder for rare failure

    # 2. Join Surfaces into one object
    final_geos = []
    
    if len(temp_breps) > 0:
        if len(temp_breps) > 1:
            # Join multiple surfaces (Split case)
            joined_arr = rg.Brep.JoinBreps(temp_breps, rs.UnitAbsoluteTolerance())
            if joined_arr:
                final_geos.extend(joined_arr)
            else:
                final_geos.extend(temp_breps) # Fallback to separate
        else:
            # Single surface
            final_geos.append(temp_breps[0])

    # 3. Add to Doc
    for geo in final_geos:
        gid = sc.doc.Objects.AddBrep(geo)
        if gid:
            o = sc.doc.Objects.Find(gid)
            o.Attributes.LayerIndex = sc.doc.Layers.Find(out_layer, True)
            o.Attributes.ObjectColor = out_col
            o.Attributes.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
            o.Attributes.MaterialSource = out_mat
            o.CommitChanges()

    # 4. Edges (Magenta)
    e_lay = sc.doc.Layers.Find("Fabric_Edges", True)
    if e_lay == -1: e_lay = sc.doc.Layers.Add("Fabric_Edges", System.Drawing.Color.Magenta)
    
    for g in grids:
        uc, vc, idxs = g['u'], g['v'], g['idxs']
        is_tri = (g['type'] == 'tri')
        
        edge_sets = []
        if is_tri:
            edge_sets.append([nodes[idxs[vc-1][u]].pos for u in range(uc)]) 
            edge_sets.append([nodes[idxs[v][0]].pos for v in range(vc)])    
            edge_sets.append([nodes[idxs[v][uc-1]].pos for v in range(vc)]) 
        else:
            edge_sets.append([nodes[idxs[u][0]].pos for u in range(uc)])
            edge_sets.append([nodes[idxs[u][vc-1]].pos for u in range(uc)])
            edge_sets.append([nodes[idxs[0][v]].pos for v in range(vc)])
            edge_sets.append([nodes[idxs[uc-1][v]].pos for v in range(vc)])

        for pts in edge_sets:
            if len(pts) > 1:
                c = rg.Curve.CreateInterpolatedCurve(pts, 3)
                if not c: c = rg.PolylineCurve(pts)
                at = sc.doc.CreateDefaultAttributes()
                at.LayerIndex = e_lay
                at.ObjectColor = System.Drawing.Color.Magenta
                at.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
                sc.doc.Objects.AddCurve(c, at)
                
    # 5. Links (Red)
    l_lay = sc.doc.Layers.Find("Structural_Links", True)
    if l_lay == -1: l_lay = sc.doc.Layers.Add("Structural_Links", System.Drawing.Color.Red)
    
    for n in nodes:
        if n.link_anchor and n.link_len > 0:
            ln = rg.Line(n.link_anchor, n.pos)
            at = sc.doc.CreateDefaultAttributes()
            at.LayerIndex = l_lay
            at.ObjectColor = System.Drawing.Color.Red
            at.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
            sc.doc.Objects.AddLine(ln, at)

    sc.doc.Views.Redraw()
    print("Geometry generated.")

# ==============================================================================
# 6. MAIN
# ==============================================================================
def main():
    try:
        srf = rs.GetObject("Select Surface", 8, preselect=True)
        if not srf: return
        
        rs.UnselectAllObjects()
        links = rs.GetObjects("Select Link Lines (Optional)", 4)
        
        rs.UnselectAllObjects()
        ridge_pts = []
        p1 = rs.GetPoint("Select Ridge START (Corner)")
        if p1:
            p2 = rs.GetPoint("Select Ridge END (Diagonal Corner)", p1)
            if p2: ridge_pts = [p1, p2]

        sets = get_user_settings()
        if not sets: return
        u, v, it, da, et, rt, ll = sets
        
        rs.EnableRedraw(False)
        rs.HideObject(srf)
        
        nodes, grids, is_split = get_initial_setup(srf, links, ridge_pts, u, v, ll)
        if nodes:
            nodes = solve_physics(nodes, it, da, et, rt, is_split)
            generate_output(nodes, grids, srf)
            
    except Exception as e:
        print("Error: {}".format(e))
    finally:
        rs.EnableRedraw(True)

if __name__ == "__main__":
    main()