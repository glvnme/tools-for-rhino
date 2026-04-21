import re
import rhinoscriptsyntax as rs
import Rhino
import Eto.Forms as forms
import Eto.Drawing as drawing
import scriptcontext as sc

TYPE_KEY = "dot_element_type"
DEFAULT_DISTANCE_INCHES = 2
MISSING_TYPE_TOKEN = ""

DIALOG_WIDTH = 820
DIALOG_HEIGHT = 700
LEFT_PANEL_WIDTH = 285
RIGHT_PANEL_WIDTH = 360


def natural_key(text):
    parts = re.split(r"(\d+)", text)
    key = []
    for p in parts:
        if p.isdigit():
            key.append((0, int(p)))
        else:
            key.append((1, p.lower()))
    return key


def type_label(token):
    return token if token else "(no dot_element_type)"


def is_numeric_name(text):
    return bool(re.match(r"^[+-]?\d+$", (text or "").strip()))


def is_string_name(text):
    return bool(re.match(r"^[A-Za-z]+$", (text or "").strip()))


def name_kind(text):
    if is_numeric_name(text):
        return "Numbers only"
    if is_string_name(text):
        return "Strings only"
    return "Mixed / Other"


def collect_textdots():
    dot_ids = rs.ObjectsByType(rs.filter.textdot, select=False) or []
    by_name = {}
    type_values = set()

    for obj_id in dot_ids:
        txt = rs.TextDotText(obj_id)
        if txt is None:
            continue
        name = txt.strip()
        if not name:
            continue

        t = rs.GetUserText(obj_id, TYPE_KEY)
        token = (t or "").strip() or MISSING_TYPE_TOKEN

        if name not in by_name:
            by_name[name] = []
        by_name[name].append((obj_id, token))
        type_values.add(token)

    names = sorted(by_name.keys(), key=natural_key)
    types_sorted = sorted(list(type_values), key=natural_key)
    if not types_sorted and names:
        types_sorted = [MISSING_TYPE_TOKEN]

    return by_name, names, types_sorted


def choose_duplicate(dot_ids):
    if len(dot_ids) == 1:
        return dot_ids[0]

    rows = []
    for i, obj_id in enumerate(dot_ids, 1):
        pt = rs.TextDotPoint(obj_id)
        layer = rs.ObjectLayer(obj_id) or "-"
        if pt:
            coord = "({0:.3f}, {1:.3f}, {2:.3f})".format(pt.X, pt.Y, pt.Z)
        else:
            coord = "(unknown point)"
        rows.append("{0:03d} | {1} | {2}".format(i, layer, coord))

    picked = rs.ListBox(rows, "More than one dot has this name. Pick one:", "Filter Dots")
    if not picked:
        return None
    return dot_ids[rows.index(picked)]


def inches_to_model_units(inches_value):
    scale = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Inches, sc.doc.ModelUnitSystem)
    return float(inches_value) * scale


def zoom_to_dot(target_id, distance_inches):
    pt = rs.TextDotPoint(target_id)
    if not pt:
        rs.Command("_Zoom _Selected", echo=False)
        return

    dist = inches_to_model_units(distance_inches)
    if dist <= Rhino.RhinoMath.ZeroTolerance:
        dist = inches_to_model_units(DEFAULT_DISTANCE_INCHES)

    view = sc.doc.Views.ActiveView
    if view:
        vp = view.ActiveViewport
        if vp and not vp.IsParallelProjection:
            cam_dir = Rhino.Geometry.Vector3d(vp.CameraDirection)
            if cam_dir.IsTiny():
                cam_dir = Rhino.Geometry.Vector3d(0.0, 0.0, -1.0)
            cam_dir.Unitize()

            new_cam = Rhino.Geometry.Point3d(
                pt.X - cam_dir.X * dist,
                pt.Y - cam_dir.Y * dist,
                pt.Z - cam_dir.Z * dist
            )
            vp.SetCameraLocation(new_cam, True)
            vp.SetCameraTarget(pt, True)
            view.Redraw()
            return

    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                corners.append(
                    Rhino.Geometry.Point3d(
                        pt.X + sx * dist,
                        pt.Y + sy * dist,
                        pt.Z + sz * dist
                    )
                )
    rs.ZoomBoundingBox(corners, view=rs.CurrentView(), all=False)


def zoom_to_dots(target_ids, distance_inches):
    valid_ids = [obj_id for obj_id in (target_ids or []) if rs.IsObject(obj_id)]
    if not valid_ids:
        return

    if len(valid_ids) == 1:
        zoom_to_dot(valid_ids[0], distance_inches)
        return

    pts = []
    for obj_id in valid_ids:
        pt = rs.TextDotPoint(obj_id)
        if pt:
            pts.append(pt)

    if not pts:
        rs.Command("_Zoom _Selected", echo=False)
        return

    dist = inches_to_model_units(distance_inches)
    if dist <= Rhino.RhinoMath.ZeroTolerance:
        dist = inches_to_model_units(DEFAULT_DISTANCE_INCHES)

    corners = []
    for pt in pts:
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    corners.append(
                        Rhino.Geometry.Point3d(
                            pt.X + sx * dist,
                            pt.Y + sy * dist,
                            pt.Z + sz * dist
                        )
                    )

    rs.ZoomBoundingBox(corners, view=rs.CurrentView(), all=False)


class DotPickerDialog(forms.Dialog):
    def __init__(self, by_name, names, type_values):
        forms.Dialog.__init__(self)

        self.Title = "Filter Dots"
        self.ClientSize = drawing.Size(DIALOG_WIDTH, DIALOG_HEIGHT)
        self.Padding = drawing.Padding(10)
        self.Resizable = True

        self.by_name = by_name
        self.all_names = list(names)
        self.type_values = list(type_values)

        self.filtered_names = list(names)
        self.selected_names = []
        self.selected_distance_inches = None
        self.selected_types = set()

        self.search_box = forms.TextBox()
        try:
            self.search_box.PlaceholderText = "Type tag (live filter)"
        except Exception:
            pass
        self.search_box.TextChanged += self.on_text_changed

        self.search_button = forms.Button(Text="Search")
        self.search_button.Click += self.on_search_click

        self.show_all_button = forms.Button(Text="Show All")
        self.show_all_button.Click += self.on_show_all_click

        self.mode_dropdown = forms.DropDown()
        self.mode_dropdown.DataStore = ["Starts with", "Contains"]
        self.mode_dropdown.SelectedIndex = 0
        self.mode_dropdown.SelectedIndexChanged += self.on_mode_changed

        self.distance_box = forms.TextBox(Text=str(DEFAULT_DISTANCE_INCHES))

        self.name_kind_dropdown = forms.DropDown()
        self.name_kind_dropdown.DataStore = ["All names", "Numbers only", "Strings only", "Mixed / Other"]
        self.name_kind_dropdown.SelectedIndex = 0
        self.name_kind_dropdown.SelectedIndexChanged += self.on_name_kind_changed

        self.length_dropdown = forms.DropDown()
        self.length_dropdown.DataStore = ["Any length", "1", "2", "3", "4", "5+"]
        self.length_dropdown.SelectedIndex = 0
        self.length_dropdown.SelectedIndexChanged += self.on_length_changed

        self.sort_dropdown = forms.DropDown()
        self.sort_dropdown.DataStore = [
            "Natural A-Z",
            "Natural Z-A",
            "Text A-Z",
            "Text Z-A",
            "Dot count (low-high)",
            "Dot count (high-low)",
            "Type A-Z",
            "Type Z-A"
        ]
        self.sort_dropdown.SelectedIndex = 0
        self.sort_dropdown.SelectedIndexChanged += self.on_sort_changed

        self.types_all_button = forms.Button(Text="All")
        self.types_all_button.Click += self.on_types_all

        self.types_none_button = forms.Button(Text="None")
        self.types_none_button.Click += self.on_types_none

        self.type_hint = forms.Label(Text="No boxes checked = all types")

        self.type_checkboxes = {}
        type_stack = forms.StackLayout()
        type_stack.Orientation = forms.Orientation.Vertical
        type_stack.Spacing = 2
        type_stack.Padding = drawing.Padding(4)

        for token in self.type_values:
            cb = forms.CheckBox(Text=type_label(token))
            cb.Checked = False
            cb.CheckedChanged += self.on_type_changed
            self.type_checkboxes[token] = cb
            type_stack.Items.Add(cb)

        self.type_scroll = forms.Scrollable()
        self.type_scroll.Border = forms.BorderType.Line
        self.type_scroll.Content = type_stack
        self.type_scroll.Height = 260

        self.status_label = forms.Label(Text="")
        self.list_box = forms.GridView()
        self.list_box.ShowHeader = False
        self.list_box.AllowMultipleSelection = True
        self.list_box.DataStore = []

        name_column = forms.GridColumn()
        name_column.HeaderText = "Tag"
        name_column.Editable = False
        name_column.AutoSize = True
        name_column.DataCell = forms.TextBoxCell(0)
        self.list_box.Columns.Add(name_column)

        self.select_button = forms.Button(Text="Select and Zoom")
        self.select_button.Click += self.on_select_click

        self.cancel_button = forms.Button(Text="Cancel")
        self.cancel_button.Click += self.on_cancel_click
        self.AbortButton = self.cancel_button
        self.DefaultButton = self.search_button

        left_panel = self.build_left_panel()
        right_panel = self.build_right_panel()

        splitter = forms.Splitter()
        splitter.Panel1 = left_panel
        splitter.Panel2 = right_panel
        splitter.Position = LEFT_PANEL_WIDTH
        splitter.FixedPanel = forms.SplitterFixedPanel.Panel1

        root = forms.DynamicLayout()
        root.Spacing = drawing.Size(8, 8)
        root.Add(splitter, yscale=True)
        root.AddSeparateRow(None, self.select_button, self.cancel_button)
        self.Content = root

        self.apply_filter("")

    def two_button_row(self, b1, b2):
        row = forms.TableLayout()
        row.Spacing = drawing.Size(6, 0)
        row.Padding = drawing.Padding(0)
        row.Rows.Add(forms.TableRow(forms.TableCell(b1, True), forms.TableCell(b2, True)))
        return row

    def build_left_panel(self):
        panel = forms.Panel()
        panel.Width = LEFT_PANEL_WIDTH

        lay = forms.DynamicLayout()
        lay.Padding = drawing.Padding(8)
        lay.Spacing = drawing.Size(6, 6)

        lay.AddRow(forms.Label(Text="Search"))
        lay.AddRow(self.search_box)
        lay.AddRow(self.two_button_row(self.search_button, self.show_all_button))

        lay.AddRow(forms.Label(Text="Match mode"))
        lay.AddRow(self.mode_dropdown)

        lay.AddRow(forms.Label(Text="Distance (in)"))
        lay.AddRow(self.distance_box)

        lay.AddRow(forms.Label(Text="Name filter"))
        lay.AddRow(self.name_kind_dropdown)

        lay.AddRow(forms.Label(Text="String length"))
        lay.AddRow(self.length_dropdown)

        lay.AddRow(forms.Label(Text="Sort results"))
        lay.AddRow(self.sort_dropdown)

        lay.AddRow(None)
        lay.AddRow(forms.Label(Text='Filter by\n"{0}"'.format(TYPE_KEY)))
        lay.AddRow(self.two_button_row(self.types_all_button, self.types_none_button))
        lay.AddRow(self.type_hint)
        lay.Add(self.type_scroll, yscale=True)

        panel.Content = lay
        return panel

    def build_right_panel(self):
        panel = forms.Panel()
        panel.Width = RIGHT_PANEL_WIDTH

        lay = forms.DynamicLayout()
        lay.Padding = drawing.Padding(8)
        lay.Spacing = drawing.Size(6, 6)

        lay.AddRow(forms.Label(Text="Available tags"))
        lay.AddRow(self.status_label)
        lay.Add(self.list_box, yscale=True)

        panel.Content = lay
        return panel

    def get_mode(self):
        return "contains" if self.mode_dropdown.SelectedIndex == 1 else "starts_with"

    def get_selected_types(self):
        selected = set()
        for token, cb in self.type_checkboxes.items():
            if cb.Checked is True:
                selected.add(token)
        return selected

    def get_name_kind_filter(self):
        try:
            return self.name_kind_dropdown.SelectedValue or "All names"
        except Exception:
            return "All names"

    def get_sort_mode(self):
        try:
            return self.sort_dropdown.SelectedValue or "Natural A-Z"
        except Exception:
            return "Natural A-Z"

    def get_length_filter(self):
        try:
            return self.length_dropdown.SelectedValue or "Any length"
        except Exception:
            return "Any length"

    def name_matches_type_filter(self, name, selected_types):
        if not selected_types:
            return True
        for _, token in self.by_name.get(name, []):
            if token in selected_types:
                return True
        return False

    def name_matches_kind_filter(self, name, kind_filter):
        if kind_filter == "Numbers only":
            return is_numeric_name(name)
        if kind_filter == "Strings only":
            return is_string_name(name)
        if kind_filter == "Mixed / Other":
            return name_kind(name) == "Mixed / Other"
        return True

    def name_matches_length_filter(self, name, length_filter):
        if length_filter == "Any length":
            return True

        length = len((name or "").strip())

        if length_filter == "5+":
            return length >= 5

        try:
            return length == int(length_filter)
        except Exception:
            return True

    def primary_type_for_name(self, name):
        tokens = sorted({token for _, token in self.by_name.get(name, [])}, key=natural_key)
        if not tokens:
            return ""
        return type_label(tokens[0])

    def sort_names(self, names):
        mode = self.get_sort_mode()

        if mode == "Natural Z-A":
            return sorted(names, key=natural_key, reverse=True)
        if mode == "Text A-Z":
            return sorted(names, key=lambda n: n.lower())
        if mode == "Text Z-A":
            return sorted(names, key=lambda n: n.lower(), reverse=True)
        if mode == "Dot count (low-high)":
            return sorted(names, key=lambda n: (len(self.by_name.get(n, [])), natural_key(n)))
        if mode == "Dot count (high-low)":
            return sorted(names, key=lambda n: (-len(self.by_name.get(n, [])), natural_key(n)))
        if mode == "Type A-Z":
            return sorted(names, key=lambda n: (self.primary_type_for_name(n).lower(), natural_key(n)))
        if mode == "Type Z-A":
            return sorted(names, key=lambda n: (self.primary_type_for_name(n).lower(), natural_key(n)), reverse=True)

        return sorted(names, key=natural_key)

    def apply_filter(self, text):
        q = (text or "").strip().lower()
        mode = self.get_mode()
        selected_types = self.get_selected_types()
        kind_filter = self.get_name_kind_filter()
        length_filter = self.get_length_filter()

        out = []
        for n in self.all_names:
            if not self.name_matches_type_filter(n, selected_types):
                continue
            if not self.name_matches_kind_filter(n, kind_filter):
                continue
            if not self.name_matches_length_filter(n, length_filter):
                continue
            nl = n.lower()
            if q:
                if mode == "contains":
                    if q not in nl:
                        continue
                else:
                    if not nl.startswith(q):
                        continue
            out.append(n)

        out = self.sort_names(out)

        self.filtered_names = out
        self.list_box.DataStore = [[name] for name in self.filtered_names]

        if self.filtered_names:
            self.list_box.SelectRow(0)
            self.status_label.Text = "{0} result(s)".format(len(self.filtered_names))
        else:
            self.status_label.Text = "Search is empty."

    def get_selected_names(self):
        selected = []

        try:
            rows = list(self.list_box.SelectedRows)
        except Exception:
            rows = []

        for row in rows:
            if 0 <= row < len(self.filtered_names):
                selected.append(self.filtered_names[row])

        if selected:
            return selected

        try:
            row = self.list_box.SelectedRow
        except Exception:
            row = -1

        if 0 <= row < len(self.filtered_names):
            return [self.filtered_names[row]]

        return []

    def on_text_changed(self, sender, e):
        self.apply_filter(self.search_box.Text)

    def on_mode_changed(self, sender, e):
        self.apply_filter(self.search_box.Text)

    def on_name_kind_changed(self, sender, e):
        self.apply_filter(self.search_box.Text)

    def on_length_changed(self, sender, e):
        self.apply_filter(self.search_box.Text)

    def on_sort_changed(self, sender, e):
        self.apply_filter(self.search_box.Text)

    def on_search_click(self, sender, e):
        self.apply_filter(self.search_box.Text)

    def on_show_all_click(self, sender, e):
        self.search_box.Text = ""
        self.apply_filter("")

    def on_type_changed(self, sender, e):
        self.apply_filter(self.search_box.Text)

    def on_types_all(self, sender, e):
        for cb in self.type_checkboxes.values():
            cb.Checked = True
        self.apply_filter(self.search_box.Text)

    def on_types_none(self, sender, e):
        for cb in self.type_checkboxes.values():
            cb.Checked = False
        self.apply_filter(self.search_box.Text)

    def on_select_click(self, sender, e):
        if not self.filtered_names:
            rs.MessageBox("Search is empty.", 0, "Filter Dots")
            return

        selected_names = self.get_selected_names()
        if not selected_names:
            rs.MessageBox("Select one or more tags from the list.", 0, "Filter Dots")
            return

        dist_text = (self.distance_box.Text or "").strip().replace(",", ".")
        try:
            dist = float(dist_text)
        except Exception:
            rs.MessageBox("Distance must be a number (in inches).", 0, "Filter Dots")
            return

        if dist <= 0:
            rs.MessageBox("Distance must be greater than 0.", 0, "Filter Dots")
            return

        self.selected_names = selected_names
        self.selected_distance_inches = dist
        self.selected_types = self.get_selected_types()
        self.Close()

    def on_cancel_click(self, sender, e):
        self.selected_names = []
        self.selected_distance_inches = None
        self.selected_types = set()
        self.Close()


def filter_dots():
    by_name, names, type_values = collect_textdots()
    if not names:
        rs.MessageBox("No TextDots with text found in this model.", 0, "Filter Dots")
        return

    dlg = DotPickerDialog(by_name, names, type_values)
    dlg.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)

    if not dlg.selected_names or dlg.selected_distance_inches is None:
        return

    target_ids = []
    for name in dlg.selected_names:
        if dlg.selected_types:
            candidates = [obj_id for obj_id, token in by_name.get(name, []) if token in dlg.selected_types]
        else:
            candidates = [obj_id for obj_id, _ in by_name.get(name, [])]

        if not candidates:
            continue

        if len(dlg.selected_names) == 1:
            target_id = choose_duplicate(candidates)
            if not target_id:
                return
            target_ids = [target_id]
        else:
            target_ids.extend(candidates)

    if not target_ids:
        rs.MessageBox("No dots match the current type filter.", 0, "Filter Dots")
        return

    unique_target_ids = []
    seen = set()
    for obj_id in target_ids:
        key = str(obj_id)
        if key in seen:
            continue
        seen.add(key)
        unique_target_ids.append(obj_id)

    for target_id in unique_target_ids:
        if rs.IsObjectHidden(target_id):
            rs.ShowObject(target_id)
        if rs.IsObjectLocked(target_id):
            rs.UnlockObject(target_id)

    rs.UnselectAllObjects()
    rs.SelectObjects(unique_target_ids)
    zoom_to_dots(unique_target_ids, dlg.selected_distance_inches)
    rs.Redraw()


if __name__ == "__main__":
    filter_dots()
