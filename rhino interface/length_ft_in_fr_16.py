# Rhino 8 (CPython) — two-point distance, formatted as feet-inch fraction (1/16" resolution)
import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
from math import gcd

def inches_to_ft_in_16(inches: float) -> str:
    # feet + inches rounded to nearest 1/16"
    feet = int(inches // 12)
    rem_in = inches - feet * 12.0
    rem_in = round(rem_in * 16) / 16.0  # snap to 1/16"

    # carry if rounding hits 12"
    if rem_in >= 12.0:
        feet += 1
        rem_in = 0.0

    whole = int(rem_in // 1)
    frac = rem_in - whole
    num = int(round(frac * 16))  # 0..15 at this point
    den = 16

    # reduce fraction
    if num:
        g = gcd(num, den)
        num //= g
        den //= g

    # build inch part with hyphen style like: 1-1/16"
    if num == 0:
        inch_part = f'{whole}"'
    else:
        inch_part = f'{whole}-{num}/{den}"' if whole else f'{num}/{den}"'

    return f"{feet}' {inch_part}"

def main():
    doc = sc.doc
    unit_from = doc.ModelUnitSystem  # current model units
    to_inches = Rhino.RhinoMath.UnitScale(unit_from, Rhino.UnitSystem.Inches)

    p1 = rs.GetPoint("First point")
    if not p1: return
    p2 = rs.GetPoint("Second point")
    if not p2: return

    length_model = rs.Distance(p1, p2)          # as Rhino measures
    length_inches = length_model * to_inches     # to decimal inches
    out = inches_to_ft_in_16(length_inches)      # feet-inch fract

    print(out)
    rs.StatusBarText(out)
    rs.MessageBox(out, 0, "Distance")

if __name__ == "__main__":
    main()
