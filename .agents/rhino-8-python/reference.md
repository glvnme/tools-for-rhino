# Rhino 8 Python Reference

## Runtime Notes

- Rhino 8 Python uses CPython 3.9.10.
- Many older Rhino and Grasshopper examples online still target IronPython 2.7. Do not copy them blindly.
- CPython-only packages may work in Rhino 8 scripts but will not automatically work in legacy GhPython.

## Recommended Structure

```python
import Rhino
import System


def validate_input(value):
    if value is None:
        raise ValueError("Expected an input value.")
    return value


def compute(data):
    # Keep this pure when possible.
    return data


doc = Rhino.RhinoDoc.ActiveDoc
if doc is None:
    raise RuntimeError("No active Rhino document.")

result = compute(validate_input(...))
```

## Best Practices

- Keep imports at the top.
- Use helper functions for reusable conversions.
- Prefer small functions over one long top-level script body.
- Read object attributes before duplicating if you need metadata.
- Avoid command-string automation when RhinoCommon exposes the same operation.
- Use `doc.ModelAbsoluteTolerance` and `doc.ModelUnitSystem` when geometric operations depend on precision or units.
- Guard against `None` returns from RhinoCommon methods.

## Common Pitfalls

- Assuming Grasshopper inputs arrive as plain Python types.
- Transforming document-owned geometry without duplication.
- Using stringly typed outputs when structured outputs are possible.
- Relying on global mutable state for repeatable computations.
- Mixing UI prompts, document edits, and computation in the same helper.

## Performance Guidance

- Cache expensive lookups only when inputs are stable.
- Avoid repeated object table queries inside tight loops.
- Collect document objects once, then process in memory.
- Return only the geometry or metadata actually needed downstream.

## Good Defaults For Shared Code

- Use RhinoCommon as the common denominator.
- Keep serialization simple: GUIDs, strings, numbers, planes, points, curves, breps, meshes.
- If code may be reused in Grasshopper, isolate Rhino document writes behind one function.
