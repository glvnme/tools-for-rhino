import Rhino
import Eto.Forms as forms
import Eto.Drawing as drawing
import scriptcontext as sc
import os
import json
import datetime
import io
import System
import random
from collections import OrderedDict

# Unique keys
STICKY_TIMER = "RhinoWorkLog_Timer_v6"
STICKY_LOADED = "RhinoWorkLog_IsLoaded_v6"

# ==============================================================================
# 1. DATA MANAGER
# ==============================================================================
class LogManager:
    def __init__(self):
        self.doc = Rhino.RhinoDoc.ActiveDoc
        self.doc_path = self.doc.Path
        self.valid = False
        
        if not self.doc_path:
            self.valid = False
            return
            
        self.valid = True
        self.folder = os.path.dirname(self.doc_path)
        self.filename = os.path.basename(self.doc_path)
        base_name = os.path.splitext(self.filename)[0]
        self.json_path = os.path.join(self.folder, "{0}_worklog.json".format(base_name))

    def ensure_valid(self):
        if not self.valid:
            raise Exception("File is not saved.")

    def _read_full_file(self):
        if not self.valid or not os.path.exists(self.json_path):
            return {"settings": {}, "logs": []}
        try:
            with io.open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list): return {"settings": {}, "logs": data}
                if isinstance(data, dict): return data
                return {"settings": {}, "logs": []}
        except:
            return {"settings": {}, "logs": []}

    def _write_full_file(self, settings_data, logs_data):
        output = OrderedDict()
        output["settings"] = settings_data
        output["logs"] = logs_data
        with io.open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=4, ensure_ascii=False)

    def load_settings(self):
        full_data = self._read_full_file()
        defaults = {"custom_username": "", "mode": "Manual", "interval_minutes": 30}
        defaults.update(full_data.get("settings", {}))
        return defaults

    def save_settings(self, new_settings):
        self.ensure_valid()
        full_data = self._read_full_file()
        self._write_full_file(new_settings, full_data.get("logs", []))
        if STICKY_TIMER in sc.sticky:
            sc.sticky[STICKY_TIMER].refresh_settings()

    def load_logs(self):
        return self._read_full_file().get("logs", [])

    def save_log(self, user_inputs):
        self.ensure_valid()
        full_data = self._read_full_file()
        current_logs = full_data.get("logs", [])
        
        entry = self.get_file_info()
        entry.update(user_inputs)
        current_logs.append(entry)
        
        self._write_full_file(full_data.get("settings", {}), current_logs)
        return self.json_path

    def update_logs(self, updated_logs):
        self.ensure_valid()
        full_data = self._read_full_file()
        self._write_full_file(full_data.get("settings", {}), updated_logs)

    def get_user_name(self):
        settings = self.load_settings()
        custom = settings.get("custom_username", "").strip()
        if custom: return custom
        return System.Environment.UserName

    def get_file_info(self):
        self.ensure_valid()
        size_bytes = os.path.getsize(self.doc_path)
        size_mb = round(size_bytes / (1024.0 * 1024.0), 2)
        return {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rhino_file_name": self.filename,
            "file_size": "{0} MB".format(size_mb),
            "file_path": self.doc_path,
            "user": self.get_user_name()
        }

# ==============================================================================
# 2. BACKGROUND MONITOR
# ==============================================================================
class AutoPrompter:
    def __init__(self):
        self.enabled = False
        self.next_trigger = datetime.datetime.max
        self.is_dialog_open = False
        self.last_check_time = datetime.datetime.now()
        self.check_interval_seconds = 5
        self.current_file_path = None
        self.refresh_settings()
        Rhino.RhinoApp.Idle += self.on_idle

    def refresh_settings(self):
        mgr = LogManager()
        self.current_file_path = mgr.doc_path
        if not mgr.valid:
            self.enabled = False
            return
        settings = mgr.load_settings()
        mode = settings.get("mode", "Manual")
        interval = float(settings.get("interval_minutes", 30))
        if mode == "Manual":
            self.enabled = False
        else:
            self.enabled = True
            self.set_next_trigger(mode, interval)

    def set_next_trigger(self, mode, interval):
        now = datetime.datetime.now()
        minutes_to_add = interval
        if mode == "Random":
            minutes_to_add = random.uniform(interval * 0.5, interval * 1.5)
        self.next_trigger = now + datetime.timedelta(minutes=minutes_to_add)

    def on_idle(self, sender, e):
        now = datetime.datetime.now()
        if (now - self.last_check_time).total_seconds() > self.check_interval_seconds:
            self.last_check_time = now
            active_doc = Rhino.RhinoDoc.ActiveDoc
            current_path = active_doc.Path if active_doc else None
            if current_path != self.current_file_path:
                self.refresh_settings()

        if not self.enabled or self.is_dialog_open:
            return

        if now > self.next_trigger:
            self.is_dialog_open = True
            self.show_prompt()

    def show_prompt(self):
        def ui_runner():
            try:
                mgr = LogManager()
                if mgr.valid:
                    System.Media.SystemSounds.Exclamation.Play()
                    dlg = WorkLogDialog()
                    dlg.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)
            finally:
                self.is_dialog_open = False
                self.refresh_settings()
        Rhino.UI.RhinoEtoApp.MainWindow.Invoke(forms.UITask(ui_runner))

    def dispose(self):
        try: Rhino.RhinoApp.Idle -= self.on_idle
        except: pass

def init_background_monitor(silent=True):
    if STICKY_TIMER in sc.sticky:
        old = sc.sticky[STICKY_TIMER]
        if old: old.dispose()
    prompter = AutoPrompter()
    sc.sticky[STICKY_TIMER] = prompter
    if not silent:
        print("Work Logger: Background monitor active.")

# ==============================================================================
# 3. UI COMPONENTS
# ==============================================================================
class SettingsDialog(forms.Dialog[bool]):
    def __init__(self, manager):
        self.Title = "Logger Settings"
        self.Padding = drawing.Padding(10)
        self.Width = 350
        self.manager = manager
        self.settings = self.manager.load_settings()

        self.txt_user = forms.TextBox()
        self.txt_user.Text = self.settings.get("custom_username", "")
        
        self.rb_manual = forms.RadioButton()
        self.rb_manual.Text = "Manual Only"
        self.rb_interval = forms.RadioButton(self.rb_manual)
        self.rb_interval.Text = "Exact Interval"
        self.rb_random = forms.RadioButton(self.rb_manual)
        self.rb_random.Text = "Random (Approximate)"
        
        mode = self.settings.get("mode", "Manual")
        if mode == "Interval": self.rb_interval.Checked = True
        elif mode == "Random": self.rb_random.Checked = True
        else: self.rb_manual.Checked = True

        self.num_interval = forms.NumericStepper()
        self.num_interval.Value = float(self.settings.get("interval_minutes", 30))
        self.num_interval.MinValue = 0.5
        self.num_interval.MaxValue = 240.0
        self.num_interval.DecimalPlaces = 1

        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(5, 5)
        layout.AddRow(forms.Label(Text="Custom Username:"), self.txt_user)
        layout.AddRow(None)
        layout.AddRow(forms.Label(Text="Auto-Popup Mode:"), self.rb_manual)
        layout.AddRow(None, self.rb_interval)
        layout.AddRow(None, self.rb_random)
        layout.AddRow(None)
        layout.AddRow(forms.Label(Text="Interval (Minutes):"), self.num_interval)
        layout.AddRow(None)
        
        btn_save = forms.Button(Text="Save Settings")
        btn_save.Click += self.on_save
        layout.AddRow(btn_save)
        self.Content = layout

    def on_save(self, sender, e):
        mode = "Manual"
        if self.rb_interval.Checked: mode = "Interval"
        if self.rb_random.Checked: mode = "Random"
        new_settings = {"custom_username": self.txt_user.Text, "mode": mode, "interval_minutes": self.num_interval.Value}
        self.manager.save_settings(new_settings)
        self.Close(True)

class LogViewerDialog(forms.Dialog[bool]):
    def __init__(self, log_manager):
        self.Title = "Log History"
        self.Padding = drawing.Padding(10)
        self.Size = drawing.Size(900, 500)
        self.manager = log_manager
        self.logs = self.manager.load_logs()
        
        self.grid = forms.GridView()
        self.grid.ShowHeader = True
        self.grid.GridLines = forms.GridLines.Both
        self.grid.DataStore = self.logs

        self.create_column("Timestamp", "timestamp", False, 140)
        self.create_column("User", "user", False, 80)
        self.create_column("Working On", "working_on", True, 200)
        self.create_column("Complications", "complications", True, 150)
        self.create_column("Issues", "issues", True, 150)
        self.create_column("Bottlenecks", "bottlenecks", True, 150)

        self.btn_save = forms.Button(Text="Save Changes")
        self.btn_save.Click += lambda s,e: [self.manager.update_logs(self.logs), self.Close(True)]
        
        layout = forms.DynamicLayout()
        layout.Add(self.grid, yscale=True)
        layout.AddSeparateRow(None, self.btn_save)
        self.Content = layout

    def create_column(self, header, key, editable, width):
        col = forms.GridColumn()
        col.HeaderText = header
        col.Width = width
        col.Editable = editable
        col.DataCell = forms.TextBoxCell()
        col.DataCell.Binding = forms.Binding.Delegate[object, System.String](
            lambda item: str(item.get(key, "")), 
            lambda item, val: item.__setitem__(key, val)
        )
        self.grid.Columns.Add(col)

class WorkLogDialog(forms.Dialog[bool]):
    def __init__(self):
        self.Title = "Project Work Logger"
        self.Padding = drawing.Padding(15)
        self.Resizable = False
        self.Width = 500
        
        try:
            self.manager = LogManager()
            self.manager.ensure_valid()
        except Exception as e:
            Rhino.UI.Dialogs.ShowMessage(str(e), "Notice")
            self.Close(False)
            return

        self.lbl_title = forms.Label(Text="Log Progress", Font=drawing.Font("Segoe UI", 12, drawing.FontStyle.Bold))
        self.lbl_status = forms.Label(Text="File: {0}".format(self.manager.filename), Font=drawing.Font("Segoe UI", 8))
        self.lbl_status.TextColor = drawing.Colors.Gray

        self.input_working = self.create_area("What are you working on?")
        self.input_complications = self.create_area("Complications")
        self.input_issues = self.create_area("Issues")
        self.input_bottlenecks = self.create_area("Bottlenecks")

        self.btn_record = forms.Button(Text="RECORD LOG")
        self.btn_record.Height = 40
        self.btn_record.BackgroundColor = drawing.Colors.Black
        self.btn_record.TextColor = drawing.Colors.White
        self.btn_record.Click += self.on_record
        
        self.btn_view = forms.Button(Text="History")
        self.btn_view.Click += lambda s,e: LogViewerDialog(self.manager).ShowModal(self)
        self.btn_settings = forms.Button(Text="Settings")
        self.btn_settings.Click += lambda s,e: SettingsDialog(self.manager).ShowModal(self)

        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(5, 8)
        
        layout.AddRow(self.lbl_title)
        layout.AddRow(self.lbl_status)
        layout.AddRow(None)
        layout.AddRow(self.create_group("Current Task", self.input_working))
        layout.AddRow(self.create_group("Complications", self.input_complications))
        layout.AddRow(self.create_group("Issues", self.input_issues))
        layout.AddRow(self.create_group("Bottlenecks", self.input_bottlenecks))
        layout.AddRow(None)
        
        btn_layout = forms.TableLayout()
        btn_layout.Rows.Add(forms.TableRow(self.btn_settings, self.btn_view, self.btn_record))
        layout.AddRow(btn_layout)
        self.Content = layout

    def create_area(self, tooltip):
        ta = forms.TextArea()
        ta.Height = 45
        ta.ToolTip = tooltip
        return ta

    def create_group(self, title, control):
        gb = forms.GroupBox()
        gb.Text = title
        gb.Content = control
        return gb

    def on_record(self, sender, e):
        inputs = {
            "working_on": self.input_working.Text,
            "complications": self.input_complications.Text,
            "issues": self.input_issues.Text,
            "bottlenecks": self.input_bottlenecks.Text
        }
        try:
            self.manager.save_log(inputs)
            self.Close(True)
        except Exception as ex:
            Rhino.UI.Dialogs.ShowMessage(str(ex), "Error")

# ==============================================================================
# 4. EXECUTION
# ==============================================================================
def main():
    if Rhino.RhinoDoc.ActiveDoc is None:
        return

    # 1. Always start the background timer logic (Silent)
    init_background_monitor(silent=True)
    
    # 2. Check if this is a first load for this Rhino session
    is_first_load = False
    if STICKY_LOADED not in sc.sticky:
        sc.sticky[STICKY_LOADED] = True
        is_first_load = True

    # 3. Check if file is saved
    mgr = LogManager()
    
    # --- LOGIC FIX: NEVER POPUP ON UNSAVED FILES ---
    if not mgr.valid:
        # If user runs the command manually but file is unsaved,
        # we PRINT to console instead of blocking the screen with a popup.
        if not is_first_load:
            print("Work Logger: Please save your Rhino file to begin logging.")
        return

    # 4. If Saved + First Load: Stay Silent
    if is_first_load:
        if STICKY_TIMER in sc.sticky:
            print("Work Logger: Auto-Monitor Started (Silent).")
        return

    # 5. If Saved + Manual Run (Not First Load): Show Panel
    dlg = WorkLogDialog()
    dlg.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)

if __name__ == "__main__":
    main()