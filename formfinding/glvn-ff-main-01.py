#! python3
import Rhino
import Rhino.Geometry as rg
import Rhino.Input.Custom as ric
import Rhino.DocObjects as rdo
import scriptcontext as sc
import rhinoscriptsyntax as rs
import System.Drawing
import Eto.Forms as forms
import Eto.Drawing as drawing
import math

"""
Rhino Tensile Form Finder (Final Polish)
----------------------------------------
- Fixed 'CommandLineOption' error.
- Fixed 'Point3f' type mismatch.
- ADDED: Aggressive Mesh Normal Rebuild (Weld + Rebuild) for smooth final result.
"""

# ==========================================
# 1. SETTINGS UI
# ==========================================
class TensileSettingsDialog(forms.Dialog[bool]):
    def __init__(self):
        self.Title = "Tensile Form Settings"
        self.Padding = drawing.Padding(10)
        self.Resizable = False
        self.Width = 340

        # Inputs
        self.warp_box = forms.TextBox(Text="1.0")
        self.fill_box = forms.TextBox(Text="1.0")
        self.cable_box = forms.TextBox(Text="20.0")
        
        # Visuals
        self.show_reactions_chk = forms.CheckBox(Text="Show Reaction Lines", Checked=True)
        self.rxn_scale_box = forms.TextBox(Text="1.0")

        # Layout
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(5, 5)
        
        layout.AddRow(forms.Label(Text="-- Stiffness / Tension --"))
        layout.AddRow(forms.Label(Text="Fabric Warp:"), self.warp_box)
        layout.AddRow(forms.Label(Text="Fabric Fill:"), self.fill_box)
        layout.AddRow(forms.Label(Text="Cable Tension:"), self.cable_box)
        
        layout.AddRow(None)
        
        layout.AddRow(forms.Label(Text="-- Visuals --"))
        layout.AddRow(self.show_reactions_chk)
        layout.AddRow(forms.Label(Text="Reaction Scale (ft):"), self.rxn_scale_box)
        
        layout.AddRow(None)

        self.run_button = forms.Button(Text="RUN SOLVER")
        self.run_button.Click += self.on_run_click
        
        self.cancel_button = forms.Button(Text="Cancel")
        self.cancel_button.Click += self.on_cancel_click

        layout.AddRow(self.run_button, self.cancel_button)
        self.Content = layout
        self.values = None

    def on_run_click(self, sender, e):
        try:
            w = float(self.warp_box.Text)
            f = float(self.fill_box.Text)
            c = float(self.cable_box.Text)
            r_scale = float(self.rxn_scale_box.Text)
            r_show = self.show_reactions_chk.Checked
            
            self.values = {
                'warp': w, 'fill': f, 'cable': c,
                'rxn_scale': r_scale, 'rxn_show': r_show
            }
            self.Close(True)
        except ValueError:
            Rhino.UI.Dialogs.ShowMessage("Please enter valid numbers.", "Input Error")

    def on_cancel_click(self, sender, e):
        self.Close(False)

# ==========================================
# 2. PHYSICS ENGINE
# ==========================================
class TensileSolver:
    def __init__(self, mesh_id, fixed_indices, settings):
        self.mesh_id = mesh_id
        rh_obj = sc.doc.Objects.FindId(mesh_id)
        self.geometry = rh_obj.Geometry.Duplicate()
        self.mesh = self.geometry
        
        # Initial cleanup
        self.mesh.Faces.ConvertQuadsToTriangles()
        self.mesh.Normals.ComputeNormals()
        self.mesh.Compact()

        # Physics Parameters
        self.drag = 0.5
        self.dt = 0.1
        self.iterations = 800 
        
        self.k_fabric = (settings['warp'] + settings['fill']) / 2.0
        self.cable_tension = settings['cable']
        self.rxn_scale = settings['rxn_scale']
        self.show_rxn = settings['rxn_show']
        
        self.total_v = self.mesh.Vertices.Count
        self.positions = [rg.Point3d(self.mesh.Vertices[i]) for i in range(self.total_v)]
        self.velocities = [rg.Vector3d(0,0,0) for _ in range(self.total_v)]
        self.forces = [rg.Vector3d(0,0,0) for _ in range(self.total_v)]
        
        self.fixed = [False] * self.total_v
        for idx in fixed_indices:
            if idx < self.total_v:
                self.fixed[idx] = True
        
        self.fabric_edges = []
        self.cable_edges = [] 
        self.cable_chains = []
        
        self.setup_constraints()

    def setup_constraints(self):
        edge_counter = {}
        
        for i in range(self.mesh.Faces.Count):
            face = self.mesh.Faces[i]
            indices = [face.A, face.B, face.C]
            if face.IsQuad: indices.append(face.D)
            
            for j in range(len(indices)):
                idx_a = indices[j]
                idx_b = indices[(j+1) % len(indices)]
                key = tuple(sorted((idx_a, idx_b)))
                edge_counter[key] = edge_counter.get(key, 0) + 1

        naked_adj = {} 
        
        for key, count in edge_counter.items():
            idx_a, idx_b = key
            if count < 2:
                self.cable_edges.append({'a': idx_a, 'b': idx_b})
                if idx_a not in naked_adj: naked_adj[idx_a] = []
                if idx_b not in naked_adj: naked_adj[idx_b] = []
                naked_adj[idx_a].append(idx_b)
                naked_adj[idx_b].append(idx_a)
            else:
                self.fabric_edges.append({'a': idx_a, 'b': idx_b})

        # Chain finding
        visited = set()
        start_nodes = [i for i in range(self.total_v) if self.fixed[i] and i in naked_adj]
        
        for start in start_nodes:
            for neighbor in naked_adj[start]:
                edge_key = tuple(sorted((start, neighbor)))
                if edge_key in visited: continue
                
                chain = [start, neighbor]
                visited.add(edge_key)
                curr = neighbor
                prev = start
                
                while not self.fixed[curr]:
                    if curr not in naked_adj: break
                    next_node = -1
                    for n in naked_adj[curr]:
                        if n != prev:
                            next_node = n
                            break
                    if next_node == -1: break
                    
                    v_key = tuple(sorted((curr, next_node)))
                    visited.add(v_key)
                    chain.append(next_node)
                    prev = curr
                    curr = next_node
                
                if self.fixed[chain[-1]]:
                    self.cable_chains.append(chain)

    def step(self):
        self.forces = [rg.Vector3d(0,0,0) for _ in range(self.total_v)]
        
        # Fabric
        for e in self.fabric_edges:
            pA = self.positions[e['a']]
            pB = self.positions[e['b']]
            vec = pB - pA
            dist = vec.Length
            if dist == 0: continue
            force = vec * (self.k_fabric) 
            self.forces[e['a']] += force
            self.forces[e['b']] -= force

        # Cable
        for e in self.cable_edges:
            pA = self.positions[e['a']]
            pB = self.positions[e['b']]
            vec = pB - pA
            dist = vec.Length
            if dist < 0.001: continue
            force = (vec / dist) * self.cable_tension
            self.forces[e['a']] += force
            self.forces[e['b']] -= force

        # Equalization
        for chain in self.cable_chains:
            total_len = sum([(self.positions[chain[k+1]] - self.positions[chain[k]]).Length for k in range(len(chain)-1)])
            if total_len == 0: continue
            target_len = total_len / (len(chain) - 1)
            eq_stiffness = self.cable_tension * 2.0 
            
            for k in range(1, len(chain)-1):
                idx = chain[k]
                prev = chain[k-1]
                next_node = chain[k+1]
                
                vec_p = self.positions[prev] - self.positions[idx]
                dist_p = vec_p.Length
                if dist_p > 0:
                    self.forces[idx] += (vec_p / dist_p) * (dist_p - target_len) * eq_stiffness
                
                vec_n = self.positions[next_node] - self.positions[idx]
                dist_n = vec_n.Length
                if dist_n > 0:
                    self.forces[idx] += (vec_n / dist_n) * (dist_n - target_len) * eq_stiffness

        # Integration
        reaction_lines = []
        
        for i in range(self.total_v):
            if self.fixed[i]:
                if self.show_rxn:
                    rxn_vec = self.forces[i] * -1.0
                    if rxn_vec.Length > 0.001:
                        direction = rxn_vec / rxn_vec.Length
                        display_vec = direction * self.rxn_scale
                        pt = self.positions[i]
                        reaction_lines.append(rg.Line(pt, pt + display_vec))
                continue
            
            self.velocities[i] += self.forces[i] * self.dt
            self.velocities[i] *= self.drag
            self.positions[i] += self.velocities[i] * self.dt
            self.mesh.Vertices.SetVertex(i, self.positions[i].X, self.positions[i].Y, self.positions[i].Z)
            
        return reaction_lines

    def update_view(self):
        self.mesh.Normals.ComputeNormals()
        sc.doc.Objects.Replace(self.mesh_id, self.mesh)
        sc.doc.Views.Redraw()
    
    def finalize_mesh(self):
        """
        Complete Rebuild of Mesh Normals for smooth tensile appearance.
        """
        # 1. Weld vertices to ensure smoothness (180 deg / Pi radians)
        self.mesh.Weld(math.pi)
        
        # 2. Clear and Recompute Normals
        self.mesh.Normals.Clear()
        self.mesh.FaceNormals.ComputeFaceNormals()
        self.mesh.Normals.ComputeNormals()
        
        # 3. Compact and Replace
        self.mesh.Compact()
        sc.doc.Objects.Replace(self.mesh_id, self.mesh)

# ==========================================
# 3. HELPERS
# ==========================================
def get_anchors_smart(mesh_id):
    target_guid = rs.coerceguid(mesh_id)
    rh_obj = sc.doc.Objects.FindId(target_guid)
    mesh_geo = rh_obj.Geometry
    
    sc.doc.Objects.UnselectAll()
    
    go = ric.GetObject()
    go.SetCommandPrompt("Select Anchors (Right-Click for Auto-Detect)")
    go.GeometryFilter = rdo.ObjectType.MeshVertex
    go.SubObjectSelect = True
    go.EnablePreSelect(False, True)
    go.DeselectAllBeforePostSelect = False
    go.AcceptNothing(True)
    
    # OPTION: Use Wrapper to fix 'CommandLineOption' error
    opt_angle_val = ric.OptionDouble(45.0)
    go.AddOptionDouble("CornerAngle", opt_angle_val)
    
    indices = set()
    corner_angle = 45.0
    
    while True:
        res = go.GetMultiple(1, 0)
        
        if res == Rhino.Input.GetResult.Option:
            # FIX: Read value from wrapper
            corner_angle = opt_angle_val.CurrentValue
            continue
            
        elif res == Rhino.Input.GetResult.Object:
            for obj_ref in go.Objects():
                if str(obj_ref.ObjectId) != str(target_guid): continue
                comp_ind = obj_ref.GeometryComponentIndex
                if comp_ind.ComponentIndexType == rg.ComponentIndexType.MeshVertex:
                    indices.add(comp_ind.Index)
                else:
                    # Fallback
                    sel_pt = obj_ref.SelectionPoint()
                    if sel_pt == rg.Point3d.Unset: continue
                    closest = mesh_geo.ClosestMeshPoint(sel_pt, 5.0)
                    if closest:
                        f = mesh_geo.Faces[closest.FaceIndex]
                        candidates = [f.A, f.B, f.C, f.D] if f.IsQuad else [f.A, f.B, f.C]
                        best_i = -1
                        best_d = 999.0
                        for c in candidates:
                            # FIX: Explicit Cast to Point3d
                            v_pt3d = rg.Point3d(mesh_geo.Vertices[c])
                            d = v_pt3d.DistanceTo(sel_pt)
                            if d < best_d:
                                best_d = d
                                best_i = c
                        if best_i != -1: indices.add(best_i)
            break
            
        elif res == Rhino.Input.GetResult.Nothing:
            print("Auto-detecting corners > {} degrees...".format(corner_angle))
            detected = auto_detect_corners_logic(mesh_geo, corner_angle)
            for idx in detected: indices.add(idx)
            if not indices:
                print("No sharp corners found. Please select manually.")
                continue
            break
            
        else:
            return None
            
    return list(indices)

def auto_detect_corners_logic(mesh, angle_deg):
    indices = set()
    rad_thresh = math.radians(angle_deg)
    polys = mesh.GetNakedEdges()
    if not polys: return []
    
    # Cast all vertices to Point3d once for distance checks
    mesh_verts_3d = [rg.Point3d(v) for v in mesh.Vertices]
    
    for poly in polys:
        pts = [poly[i] for i in range(poly.Count)]
        is_closed = poly.IsClosed
        n = len(pts)
        limit = n - 1 if is_closed else n
        
        for i in range(limit):
            curr = i
            if is_closed:
                prev = (i - 1) % (n - 1)
                nxt = (i + 1) % (n - 1)
            else:
                prev = i - 1
                nxt = i + 1
                if prev < 0 or nxt >= n: continue
            
            v1 = pts[curr] - pts[prev]
            v2 = pts[nxt] - pts[curr]
            
            if v1.IsTiny() or v2.IsTiny(): continue
            v1.Unitize()
            v2.Unitize()
            
            angle = rg.Vector3d.VectorAngle(v1, v2)
            
            if angle > rad_thresh:
                p_loc = pts[curr]
                best_i = -1
                best_d = 0.1
                
                for m_i, m_v in enumerate(mesh_verts_3d):
                    d = m_v.DistanceTo(p_loc)
                    if d < best_d:
                        best_d = d
                        best_i = m_i
                
                if best_i != -1:
                    indices.add(best_i)
                    
    return list(indices)

def generate_catenary_cables_split(mesh_id, anchor_indices):
    rh_obj = sc.doc.Objects.FindId(mesh_id)
    mesh = rh_obj.Geometry
    polylines = mesh.GetNakedEdges()
    if not polylines: return
    
    boundary_crvs = rg.Curve.JoinCurves([p.ToPolylineCurve() for p in polylines])
    anchor_pts = [rg.Point3d(mesh.Vertices[i]) for i in anchor_indices]
    final_cables = []
    
    for crv in boundary_crvs:
        split_params = []
        for pt in anchor_pts:
            rc, t = crv.ClosestPoint(pt, 0.1) 
            if rc:
                dist = crv.PointAt(t).DistanceTo(pt)
                if dist < 0.1:
                    dom = crv.Domain
                    if abs(t - dom.Min) > 0.01 and abs(t - dom.Max) > 0.01:
                        split_params.append(t)
        
        if split_params:
            split_params.sort()
            segments = crv.Split(split_params)
            if segments:
                final_cables.extend(segments)
            else:
                final_cables.append(crv)
        else:
            final_cables.append(crv)
            
    created_ids = []
    attr = sc.doc.CreateDefaultAttributes()
    attr.ObjectColor = System.Drawing.Color.Blue
    attr.ColorSource = rdo.ObjectColorSource.ColorFromObject
    
    for c in final_cables:
        guid = sc.doc.Objects.AddCurve(c, attr)
        created_ids.append(guid)
    return created_ids

# ==========================================
# 4. MAIN
# ==========================================
def main():
    mesh_id = rs.GetObject("Select Mesh", rs.filter.mesh)
    if not mesh_id: return
    
    anchor_indices = get_anchors_smart(mesh_id)
    if not anchor_indices: 
        print("No anchors set.")
        return
    
    mesh_geo = rs.coercemesh(mesh_id)
    temp_dots = [sc.doc.Objects.AddPoint(rg.Point3d(mesh_geo.Vertices[i])) for i in anchor_indices]
    sc.doc.Views.Redraw()

    dlg = TensileSettingsDialog()
    rc = dlg.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)
    
    for d in temp_dots: sc.doc.Objects.Delete(d, True)
    
    if not rc: return
    settings = dlg.values

    try:
        solver = TensileSolver(mesh_id, anchor_indices, settings)
        
        rs.EnableRedraw(False)
        reaction_ids = []
        
        for i in range(solver.iterations):
            if sc.escape_test(False): break
            
            rxn_lines = solver.step()
            
            if i % 5 == 0:
                solver.update_view()
                
                for guid in reaction_ids: sc.doc.Objects.Delete(guid, True)
                reaction_ids = []
                if rxn_lines:
                    attr = sc.doc.CreateDefaultAttributes()
                    attr.ObjectColor = System.Drawing.Color.Red
                    attr.ColorSource = rdo.ObjectColorSource.ColorFromObject
                    for line in rxn_lines:
                        reaction_ids.append(sc.doc.Objects.AddLine(line, attr))
                
                rs.EnableRedraw(True)
                rs.EnableRedraw(False)
                Rhino.RhinoApp.Wait()
        
        if not settings['rxn_show']:
            for guid in reaction_ids: sc.doc.Objects.Delete(guid, True)
        else:
            rs.SelectObjects(reaction_ids)
        
        print("Finalizing Mesh Normals (Weld + Rebuild)...")
        solver.finalize_mesh()
        
        # Explicit call to the RhinoScript command for safety
        rs.RebuildMeshNormals(mesh_id)
        
        print("Generating Boundary Cables...")
        cable_ids = generate_catenary_cables_split(mesh_id, anchor_indices)
        if cable_ids:
            rs.SelectObjects(cable_ids)
            
    except Exception as e:
        print("Error: {}".format(e))
    finally:
        rs.EnableRedraw(True)

if __name__ == "__main__":
    main()