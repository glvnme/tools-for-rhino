#! python3
import Rhino
import scriptcontext as sc
import Eto.Forms as forms
import Eto.Drawing as drawing
import datetime

# ==============================================================================
# 1. DATA CONFIGURATION
# ==============================================================================

CABLE_SIZES = [
    "1/16\"", "3/32\"", "1/8\"", "5/32\"", "3/16\"", "7/32\"", "1/4\"", 
    "5/16\"", "3/8\"", "7/16\"", "1/2\"", "9/16\"", "5/8\"", "3/4\"", 
    "7/8\"", "1\"", "1-1/8\"", "1-1/4\"", "1-1/2\"", "1-3/4\"", "2\""
]

TUBE_SPECS = {
    "3/8\" XS":  {"OD": "0.675\"", "Wall": "0.126\""},
    "1/2\" XS":  {"OD": "0.840\"", "Wall": "0.147\""},
    "3/4\" XS":  {"OD": "1.050\"", "Wall": "0.154\""},
    "1\" XS":    {"OD": "1.315\"", "Wall": "0.179\""},
    "1-1/4\" XS":{"OD": "1.680\"", "Wall": "0.191\""},
    "1-1/2\" XS":{"OD": "1.900\"", "Wall": "0.200\""},
    "2\" XS":    {"OD": "2.375\"", "Wall": "0.218\""},
    "2-1/2\" XS":{"OD": "2.875\"", "Wall": "0.276\""},
    "3\" XS":    {"OD": "3.500\"", "Wall": "0.300\""},
    "3-1/2\" XS":{"OD": "4.000\"", "Wall": "0.318\""},
    "4\" XS":    {"OD": "4.500\"", "Wall": "0.337\""},
    "5\" XS":    {"OD": "5.563\"", "Wall": "0.375\""}
}

SECTION_START = ">>> POCKETS_DATA_START >>>"
SECTION_END   = "<<< POCKETS_DATA_END <<<"

# ==============================================================================
# 2. UI CLASS (ETO FORMS)
# ==============================================================================

class PocketsDialog(forms.Dialog[bool]):
    def __init__(self):
        self.Title = "Pockets & Seams Data Recorder"
        self.Padding = drawing.Padding(10)
        self.Resizable = False
        self.Width = 350

        # --- Inputs ---
        
        # 1. Edge Cable Dia
        self.dd_cable = forms.DropDown()
        self.dd_cable.DataStore = CABLE_SIZES
        self.dd_cable.SelectedIndex = 6 # Default to 1/4"

        # 2. Cuff Seam W
        self.txt_cuff = forms.TextBox(Text="2\"")

        # 3. Offset X
        self.txt_offset = forms.TextBox(Text="1\"")

        # 4. Cable Stud Length
        self.txt_stud_len = forms.TextBox(Text="3\"")

        # 5. Cable Stud Diameter (NEW)
        self.txt_stud_dia = forms.TextBox(Text="1/2\"")

        # 6. Cable Stud Thread
        self.txt_stud_thd = forms.TextBox(Text="1/2-13")

        # 7. Cable Tube Name
        sorted_keys = sorted(list(TUBE_SPECS.keys()))
        self.dd_tube = forms.DropDown()
        self.dd_tube.DataStore = sorted_keys
        
        # Attempt to set default to 1" XS if it exists
        try:
            self.dd_tube.SelectedIndex = sorted_keys.index("1\" XS")
        except:
            self.dd_tube.SelectedIndex = 0
            
        self.dd_tube.SelectedIndexChanged += self.on_tube_changed

        # 8 & 9. Tube OD and Wall (Read Only)
        self.lbl_tube_od = forms.Label(Text="-")
        self.lbl_tube_wall = forms.Label(Text="-")
        
        # Trigger initial update for OD/Wall
        self.on_tube_changed(None, None)

        # --- Buttons ---
        self.btn_save = forms.Button(Text="Save to Notes")
        self.btn_save.Click += self.on_save_click

        self.btn_cancel = forms.Button(Text="Cancel")
        self.btn_cancel.Click += self.on_cancel_click

        # --- Layout ---
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(5, 5)

        layout.AddRow(forms.Label(Text="Edge Cable Diameter:"), self.dd_cable)
        layout.AddRow(forms.Label(Text="Cuff Seam W:"), self.txt_cuff)
        layout.AddRow(forms.Label(Text="Offset from Cable X:"), self.txt_offset)
        
        layout.AddRow(None) # Spacer
        layout.AddRow(forms.Label(Text="--- Stud Specs ---"))
        layout.AddRow(forms.Label(Text="Cable Stud Length:"), self.txt_stud_len)
        layout.AddRow(forms.Label(Text="Cable Stud Diameter:"), self.txt_stud_dia) # Added here
        layout.AddRow(forms.Label(Text="Cable Stud Thread:"), self.txt_stud_thd)
        
        layout.AddRow(None) # Spacer
        layout.AddRow(forms.Label(Text="--- Hardware Specs ---"))
        
        layout.AddRow(forms.Label(Text="Cable Tube Name:"), self.dd_tube)
        layout.AddRow(forms.Label(Text="Tube OD:"), self.lbl_tube_od)
        layout.AddRow(forms.Label(Text="Tube Wall:"), self.lbl_tube_wall)

        layout.AddRow(None) # Spacer
        layout.AddRow(self.btn_save, self.btn_cancel)

        self.Content = layout

    # --- Event Handlers ---

    def on_tube_changed(self, sender, e):
        """Updates OD and Wall based on selected Tube Name"""
        selected_key = self.dd_tube.SelectedValue
        if selected_key in TUBE_SPECS:
            data = TUBE_SPECS[selected_key]
            self.lbl_tube_od.Text = data["OD"]
            self.lbl_tube_wall.Text = data["Wall"]

    def on_save_click(self, sender, e):
        """Collects data and closes dialog"""
        self.collected_data = {
            "Edge Cable Dia": self.dd_cable.SelectedValue,
            "Cuff Seam W": self.txt_cuff.Text,
            "Offset X": self.txt_offset.Text,
            "Stud Length": self.txt_stud_len.Text,
            "Stud Diameter": self.txt_stud_dia.Text, # Capture new field
            "Stud Thread": self.txt_stud_thd.Text,
            "Tube Name": self.dd_tube.SelectedValue,
            "Tube OD": self.lbl_tube_od.Text,
            "Tube Wall": self.lbl_tube_wall.Text,
            "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.Close(True)

    def on_cancel_click(self, sender, e):
        self.Close(False)

# ==============================================================================
# 3. NOTES STORAGE LOGIC
# ==============================================================================

def format_for_notes(data_dict):
    """Formats the data into a clean block string."""
    lines = []
    lines.append(SECTION_START)
    lines.append("Recorded: {}".format(data_dict['Timestamp']))
    lines.append("-" * 20)
    lines.append("Cable Dia   : {}".format(data_dict['Edge Cable Dia']))
    lines.append("Cuff Seam   : {}".format(data_dict['Cuff Seam W']))
    lines.append("Offset X    : {}".format(data_dict['Offset X']))
    lines.append("Stud Len    : {}".format(data_dict['Stud Length']))
    lines.append("Stud Dia    : {}".format(data_dict['Stud Diameter'])) # Added to notes
    lines.append("Stud Thread : {}".format(data_dict['Stud Thread']))
    lines.append("Tube Spec   : {}".format(data_dict['Tube Name']))
    lines.append("  > OD      : {}".format(data_dict['Tube OD']))
    lines.append("  > Wall    : {}".format(data_dict['Tube Wall']))
    lines.append(SECTION_END)
    lines.append("") # Empty line for spacing
    return "\n".join(lines)

def update_rhino_notes():
    # 1. Show Dialog
    dialog = PocketsDialog()
    result = dialog.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)

    if result:
        # 2. Get Data
        new_entry = format_for_notes(dialog.collected_data)
        
        # 3. Read Existing Notes
        current_notes = sc.doc.Notes
        if current_notes is None:
            current_notes = ""

        # 4. Append New Data
        updated_notes = current_notes + "\n" + new_entry
        sc.doc.Notes = updated_notes
        
        print("Success: Pocket data saved to Rhino Notes.")
    else:
        print("Cancelled.")

# ==============================================================================
# 4. EXECUTION
# ==============================================================================

if __name__ == "__main__":
    update_rhino_notes()