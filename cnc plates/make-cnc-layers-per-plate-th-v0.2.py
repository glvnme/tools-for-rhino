import rhinoscriptsyntax as rs
import datetime

def create_cnc_layers_multiple():
    """
    This function creates a hierarchical layer structure for CNC steel plate preparation.
    It prompts the user to select multiple plate thicknesses from a checklist and then
    generates the corresponding layers with predefined colors and a fixed order.
    """
    
    # Get the current date and format it as YY-MMDD
    current_date = datetime.datetime.now().strftime("%y-%m%d")
    
    # Pre-defined list of typical steel plate thicknesses in ascending order
    plate_thicknesses = [
        "1/16\"", "1/8\"", "3/16\"", "1/4\"", "5/16\"", "3/8\"", "7/16\"", 
        "1/2\"", "9/16\"", "5/8\"", "11/16\"", "3/4\"", "13/16\"", "7/8\"", 
        "15/16\"", "1\"", "1 1/8\"", "1 1/4\"", "1 3/8\"", "1 1/2\"", 
        "1 3/4\"", "2\""
    ]
    
    # Prompt the user to select multiple plate thicknesses from a checklist
    # The format is [(item1, False), (item2, False), ...]
    items_to_check = [(thickness, False) for thickness in plate_thicknesses]
    selected_items = rs.CheckListBox(items_to_check, "Select Plate Thickness(es)", "CNC Layer Setup")
    
    if selected_items:
        # Filter to get only the thicknesses that were checked (True)
        selected_thicknesses = [item[0] for item in selected_items if item[1]]
        
        if not selected_thicknesses:
            print("No plate thicknesses were selected.")
            return

        # Define the sub-layers and their colors in a specific order
        # Using a list of tuples guarantees the creation order
        sub_layers_ordered = [
            ("CUT", (255, 0, 0)),      # Red
            ("ETCH", (0, 255, 255)),   # Cyan
            ("ANNO", (128, 128, 128)), # Grey
            ("DIMS", (255, 165, 0))    # Orange
        ]

        # Loop through each selected thickness and create the layer structure
        for plate_th in selected_thicknesses:
            # Define the main layer structure
            parent_layer_path = "STEEL PLATES::CNC-EXP-{}::{}".format(current_date, plate_th)
            
            # Create the parent layer. rhinoscriptsyntax handles the nesting.
            rs.AddLayer(parent_layer_path)
            
            # Create and color the sub-layers in the specified order
            for layer_name, color in sub_layers_ordered:
                full_layer_path = "{}::{}".format(parent_layer_path, layer_name)
                # Add the layer and set its color
                rs.AddLayer(full_layer_path, color)
        
        print("Successfully created layer structures for {} plate(s).".format(len(selected_thicknesses)))

# This is the standard way to run the script
if __name__ == "__main__":
    create_cnc_layers_multiple()