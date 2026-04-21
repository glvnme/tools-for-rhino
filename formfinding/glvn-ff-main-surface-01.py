    # -*- coding: utf-8 -*-
    #
    # Title: Surface-Based Mesh-Free Form-Finding (v7)
    # Author: [Your Name/Company Name]
    # Date: 2024-10-27
    # Description: A script to perform a relaxation simulation on a point grid
    #              derived from a NURBS surface. This version corrects the
    #              nonexistent 'PointMean' function call.
    
    import rhinoscriptsyntax as rs
    import Rhino.Geometry as rg
    import copy
    
    # ==============================================================================
    # 1. USER INTERFACE FUNCTION
    # ==============================================================================
    
    def get_user_settings():
        """
        Displays a single, unified pop-up window to get all simulation parameters.
        
        Returns:
            tuple: A tuple containing (u_div, v_div, iterations, damping, edge_tension)
                   or None if the user cancels the dialog.
        """
        setting_labels = ["U Divisions", "V Divisions", "Iterations", "Damping", "Edge Tension"]
        setting_defaults = [10, 10, 50, 0.5, 0.5]
        results = rs.PropertyListBox(setting_labels, setting_defaults, "Form-Finding Settings")
    
        if not results: return None
    
        try:
            u_div = int(results[0])
            v_div = int(results[1])
            iterations = int(results[2])
            damping = float(results[3])
            edge_tension = float(results[4])
            
            if u_div < 1 or v_div < 1 or iterations < 1 or not (0.0 < damping <= 1.0) or not (0.0 <= edge_tension):
                raise ValueError("One or more settings are out of the valid range.")
                
            return u_div, v_div, iterations, damping, edge_tension
            
        except (ValueError, TypeError) as e:
            print("Error: Invalid input. Please enter valid numbers. Details: {}".format(e))
            return None
    
    # ==============================================================================
    # 2. CORE GEOMETRY AND SIMULATION FUNCTIONS
    # ==============================================================================
    
    def get_point_grid_from_surface(surface_id, u_div, v_div):
        """
        Evaluates points on a NURBS surface to create an initial grid for simulation.
        """
        if not rs.IsSurface(surface_id): return None
        print("Generating a {}x{} division grid...".format(u_div, v_div))
    
        u_domain = rs.SurfaceDomain(surface_id, 0)
        v_domain = rs.SurfaceDomain(surface_id, 1)
        
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
                point = rs.EvaluateSurface(surface_id, u_param, v_param)
                row.append(point)
            point_grid.append(row)
            
        print("Successfully generated a {}x{} point grid.".format(u_count, v_count))
        return point_grid
    
    
    def run_form_finding_relaxation(point_grid, iterations, damping, edge_tension):
        """
        Runs an iterative relaxation process with weighted edge tension.
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
                    
                    is_corner = (u == 0 or u == u_count - 1) and (v == 0 or v == v_count - 1)
                    if is_corner:
                        continue
    
                    current_pt = point_grid[u][v]
                    avg_pt = None
                    
                    # Condition: Point is on a vertical edge (left or right)
                    if u == 0 or u == u_count - 1:
                        p_up = point_grid[u][v + 1]
                        p_down = point_grid[u][v - 1]
                        p_side = point_grid[u + 1 if u == 0 else u - 1][v]
                        total_weight = 2 * weight_edge + weight_internal
                        avg_x = (weight_edge * (p_up.X + p_down.X) + weight_internal * p_side.X) / total_weight
                        avg_y = (weight_edge * (p_up.Y + p_down.Y) + weight_internal * p_side.Y) / total_weight
                        avg_z = (weight_edge * (p_up.Z + p_down.Z) + weight_internal * p_side.Z) / total_weight
                        avg_pt = rg.Point3d(avg_x, avg_y, avg_z)
    
                    # Condition: Point is on a horizontal edge (top or bottom)
                    elif v == 0 or v == v_count - 1:
                        p_left = point_grid[u - 1][v]
                        p_right = point_grid[u + 1][v]
                        p_side = point_grid[u][v + 1 if v == 0 else v - 1]
                        total_weight = 2 * weight_edge + weight_internal
                        avg_x = (weight_edge * (p_left.X + p_right.X) + weight_internal * p_side.X) / total_weight
                        avg_y = (weight_edge * (p_left.Y + p_right.Y) + weight_internal * p_side.Y) / total_weight
                        avg_z = (weight_edge * (p_left.Z + p_right.Z) + weight_internal * p_side.Z) / total_weight
                        avg_pt = rg.Point3d(avg_x, avg_y, avg_z)
    
                    # Condition: Point is an internal point
                    else:
                        neighbors = [
                            point_grid[u - 1][v], point_grid[u + 1][v],
                            point_grid[u][v - 1], point_grid[u][v + 1]
                        ]
                        # --- FIX: Manually calculate the average point ---
                        sum_x, sum_y, sum_z = 0.0, 0.0, 0.0
                        for pt in neighbors:
                            sum_x += pt.X
                            sum_y += pt.Y
                            sum_z += pt.Z
                        num_neighbors = len(neighbors)
                        avg_pt = rg.Point3d(sum_x/num_neighbors, sum_y/num_neighbors, sum_z/num_neighbors)
                        # -----------------------------------------------
                    
                    if avg_pt:
                        move_vector = rs.VectorCreate(avg_pt, current_pt)
                        damped_vector = rs.VectorScale(move_vector, damping)
                        new_position = rs.PointAdd(current_pt, damped_vector)
                        new_point_grid[u][v] = new_position
    
            point_grid = new_point_grid
            if (i + 1) % 10 == 0:
                print("Completed iteration {} of {}...".format(i + 1, iterations))
    
        print("Form-finding simulation complete.")
        return point_grid
    
    
    def create_geometry_from_grid(final_grid):
        """
        Generates the final geometry (NURBS surface and edge curves) from the relaxed grid.
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
        else:
            print("Error: Failed to generate the final surface.")
    
        edge_points_bottom = final_grid[0]
        edge_points_top = final_grid[-1]
        edge_points_left = [row[0] for row in final_grid]
        edge_points_right = [row[-1] for row in final_grid]
    
        rs.ObjectName(rs.AddPolyline(edge_points_bottom), "Edge_Curve_Bottom")
        rs.ObjectName(rs.AddPolyline(edge_points_top), "Edge_Curve_Top")
        rs.ObjectName(rs.AddPolyline(edge_points_left), "Edge_Curve_Left")
        rs.ObjectName(rs.AddPolyline(edge_points_right), "Edge_Curve_Right")
        print("Generated 4 boundary edge curves.")
    
    # ==============================================================================
    # 3. MAIN EXECUTION BLOCK
    # ==============================================================================
    
    def main():
        """
        Main function to run the entire form-finding process.
        """
        print("--- Starting Surface Form-Finding Script ---")
        
        settings = get_user_settings()
        if not settings:
            print("Operation cancelled by user.")
            return
        u_div, v_div, iterations, damping, edge_tension = settings
    
        input_surface_id = rs.GetObject("Select an initial NURBS surface", 8, preselect=True)
        if not input_surface_id:
            print("No surface selected. Operation cancelled.")
            return
    
        rs.HideObject(input_surface_id)
        
        initial_grid = get_point_grid_from_surface(input_surface_id, u_div, v_div)
        
        if initial_grid:
            final_grid = run_form_finding_relaxation(initial_grid, iterations, damping, edge_tension)
            
            if final_grid:
                create_geometry_from_grid(final_grid)
    
        print("--- Script finished. ---")
    
    # ==============================================================================
    # Run the main function when the script is executed
    # ==============================================================================
    if __name__ == "__main__":
        main()