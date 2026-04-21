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
        self.selected_name = None
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
        self.list_box = forms.ListBox()

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

    def name_matches_type_filter(self, name, selected_types):
        if not selected_types:
            return True
        for _, token in self.by_name.get(name, []):
            if token in selected_types:
                return True
        return False

    def apply_filter(self, text):
        q = (text or "").strip().lower()
        mode = self.get_mode()
        selected_types = self.get_selected_types()

        out = []
        for n in self.all_names:
            if not self.name_matches_type_filter(n, selected_types):
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

        self.filtered_names = out
        self.list_box.DataStore = self.filtered_names

        if self.filtered_names:
            self.list_box.SelectedIndex = 0
            self.status_label.Text = "{0} result(s)".format(len(self.filtered_names))
        else:
            self.status_label.Text = "Search is empty."

    def on_text_changed(self, sender, e):
        self.apply_filter(self.search_box.Text)

    def on_mode_changed(self, sender, e):
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

        idx = self.list_box.SelectedIndex
        if idx < 0 or idx >= len(self.filtered_names):
            rs.MessageBox("Select a tag from the list.", 0, "Filter Dots")
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

        self.selected_name = self.filtered_names[idx]
        self.selected_distance_inches = dist
        self.selected_types = self.get_selected_types()
        self.Close()

    def on_cancel_click(self, sender, e):
        self.selected_name = None
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

    if not dlg.selected_name or dlg.selected_distance_inches is None:
        return

    if dlg.selected_types:
        candidates = [obj_id for obj_id, token in by_name.get(dlg.selected_name, []) if token in dlg.selected_types]
    else:
        candidates = [obj_id for obj_id, _ in by_name.get(dlg.selected_name, [])]

    if not candidates:
        rs.MessageBox("No dot matches current type filter.", 0, "Filter Dots")
        return

    target_id = choose_duplicate(candidates)
    if not target_id:
        return

    if rs.IsObjectHidden(target_id):
        rs.ShowObject(target_id)
    if rs.IsObjectLocked(target_id):
        rs.UnlockObject(target_id)

    rs.UnselectAllObjects()
    rs.SelectObject(target_id)
    zoom_to_dot(target_id, dlg.selected_distance_inches)
    rs.Redraw()


if __name__ == "__main__":
    filter_dots()
