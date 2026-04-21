import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino

def _gcd(a, b):
    a = int(abs(a)); b = int(abs(b))
    while b:
        a, b = b, a % b
    return a or 1

def inches_to_ft_in_16(inches):
    # Convert to integer sixteenths to avoid floating error and enforce 1/16" tolerance
    total_16 = int(round(inches * 16.0))  # nearest 1/16"
    feet = total_16 // (12 * 16)          # 192 sixteenths per foot
    rem_16 = total_16 - feet * 12 * 16

    whole_in = rem_16 // 16
    frac_16 = rem_16 - whole_in * 16

    # Reduce fraction
    if frac_16:
        g = _gcd(frac_16, 16)
        num = frac_16 // g
        den = 16 // g
    else:
        num = 0; den = 1

    # Assemble inch part
    if num == 0:
        inch_part = str(whole_in) + '"'
    else:
        inch_part = (str(whole_in) + '-' if whole_in else '') + str(num) + '/' + str(den) + '"'

    return str(feet) + "' " + inch_part

def main():
    # Get model unit system and scale to inches
    unit_from = sc.doc.ModelUnitSystem
    to_inches = Rhino.RhinoMath.UnitScale(unit_from, Rhino.UnitSystem.Inches)

    # Pick two points like Rhino's Distance command
    p1 = rs.GetPoint("First point")
    if not p1: return
    p2 = rs.GetPoint("Second point")
    if not p2: return

    # Distance in model units -> decimal inches
    d_model = rs.Distance(p1, p2)
    d_in = d_model * to_inches

    # Format as feet-inches @ 1/16"
    out = inches_to_ft_in_16(d_in)
    print(out)  # command history only

if __name__ == "__main__":
    main()
