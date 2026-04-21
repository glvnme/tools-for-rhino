#! python3
import Rhino
import scriptcontext as sc
import System.Drawing
import os
import datetime
import math

# --- 1. ROBUST DATE CONVERSION ---
def julian_to_dt(jd):
    """
    Converts Rhino's Julian Day (sun slider position) into a Python datetime.
    This bypasses potential missing .Year attributes.
    """
    if jd is None: return None
    try:
        J = float(jd) + 0.5
        j = J + 32044
        g = j // 146097
        dg = j % 146097
        c = (dg // 36524 + 1) * 3 // 4
        dc = dg - c * 36524
        b = dc // 1461
        db = dc % 1461
        a = (db // 365 + 1) * 3 // 4
        da = db - a * 365
        y = g * 400 + c * 100 + b * 4 + a - 4800 + (1 if 0 <= 2 else 0)
        m = (da * 5 + 308) // 153 - 2
        d = da - (m + 4) * 153 // 5 + 122
        return datetime.datetime(int(y + (m + 2) // 12), int((m + 2) % 12 + 1), int(d + 1))
    except:
        return None

def safe_get_val(obj, attr_list, default):
    """Helper to safely grab a value from a list of possible attribute names."""
    for name in attr_list:
        if hasattr(obj, name):
            val = getattr(obj, name)
            if not callable(val): return val
    return default

def capture_sun_study_image():
    # --- 2. SETUP & VALIDATION ---
    doc = sc.doc
    if not doc.Path:
        print("Error: Please save the Rhino file first.")
        return

    # Target the UI Panel settings specifically
    sun = doc.RenderSettings.Sun
    earth = doc.EarthAnchorPoint

    # --- 3. GET DATE (STRICTLY FROM PANEL) ---
    sim_date = None

    # Priority A: Julian Day (Most reliable for Rhino 8)
    if hasattr(sun, "JulianDay"):
        sim_date = julian_to_dt(sun.JulianDay)

    # Priority B: Explicit Properties
    if sim_date is None:
        try:
            y = int(sun.Year)
            m = int(sun.Month)
            d = int(sun.Day)
            if m == 0: m = 1
            sim_date = datetime.datetime(y, m, d)
        except:
            pass

    # Safety: If all else fails, do NOT use today. Error out or use placeholder.
    if sim_date is None:
        print("CRITICAL: Could not read Sun Panel Date. Using placeholder 2000-01-01.")
        sim_date = datetime.datetime(2000, 1, 1)

    # --- 4. GET TIME (STRICTLY FROM PANEL) ---
    sim_time_str = "12-00-PM"
    try:
        raw_hours = safe_get_val(sun, ["Hours"], 12.0)
        h_int = int(raw_hours)
        m_int = int((raw_hours - h_int) * 60)
        
        # Merge time into date object
        sim_dt_full = sim_date.replace(hour=h_int, minute=m_int)
        sim_time_str = sim_dt_full.strftime("%I-%M-%p") # 10-38-AM
    except:
        pass

    # --- 5. GET LOCATION (ROBUST FALLBACKS) ---
    # Try Sun -> Earth -> Default
    p_long = safe_get_val(sun, ["Longitude"], None)
    if p_long is None:
        p_long = safe_get_val(earth, ["Longitude", "EarthLocationLongitude"], 0.0)

    p_north = safe_get_val(sun, ["North"], None)
    if p_north is None:
        p_north = safe_get_val(earth, ["ModelNorth", "ModelNorthAngle"], 0.0)
        
    p_alt = safe_get_val(sun, ["Altitude"], 0.0)

    # --- 6. FORMATTING ---
    # Date Parts: MARCH_16
    month_name = sim_date.strftime("%B").upper()
    day_str = str(sim_date.day)
    fname_date = "{}_{}".format(month_name, day_str)
    
    # Folder Date: 03-16
    folder_date = sim_date.strftime("%m-%d")

    # Physics
    alt_str = "{:.1f}".format(p_alt)
    long_str = "{:.1f}".format(p_long)
    north_str = "{:.1f}".format(p_north)

    # Viewport
    view = doc.Views.ActiveView
    vp_name = view.ActiveViewport.Name if view else "View"
    vp_name = "".join(x for x in vp_name if x.isalnum() or x in "_-")

    # --- 7. FILE PATHS ---
    # Filename: MARCH_16_10-38-AM_Alt44.9_Long-120.0_North90.0_Perspective.jpg
    filename = "{}_{}_Alt{}_Long{}_North{}_{}.jpg".format(
        fname_date, sim_time_str, alt_str, long_str, north_str, vp_name
    )

    project_path = os.path.dirname(doc.Path)
    folder_path = os.path.join(project_path, "sun_study", folder_date)
    
    if not os.path.exists(folder_path):
        try:
            os.makedirs(folder_path)
        except OSError as e:
            print("Error creating folder: " + str(e))
            return

    full_path = os.path.abspath(os.path.join(folder_path, filename))

    # --- 8. CAPTURE ---
    capture = Rhino.Display.ViewCapture()
    if view:
        w = view.ActiveViewport.Bounds.Width
        h = view.ActiveViewport.Bounds.Height
        capture.Width = int(w * 3)
        capture.Height = int(h * 3)
    else:
        capture.Width = 1920
        capture.Height = 1080

    capture.ScaleScreenItems = True
    capture.DrawAxes = True
    capture.DrawGrid = True
    capture.TransparentBackground = False

    try:
        bitmap = capture.CaptureToBitmap(view)
        if bitmap:
            bitmap.Save(full_path, System.Drawing.Imaging.ImageFormat.Jpeg)
            print("\n" + "="*50)
            print("SUN STUDY CAPTURED")
            print("Date: " + fname_date)
            print("Path: " + full_path)
            print("="*50 + "\n")
        else:
            print("Error: Capture failed.")
    except Exception as e:
        print("Error saving image: " + str(e))

if __name__ == "__main__":
    capture_sun_study_image()