# IronPython Interop Reference

## Runtime Differences That Matter

- Rhino 8 Python scripts run on CPython 3.9.10.
- Legacy GhPython workflows often run on IronPython 2.7.
- Both runtimes can use RhinoCommon, which is the safest shared layer.
- Pure Python dependencies that rely on CPython wheels usually will not work in IronPython.

## Shared-Code Guidelines

- Keep shared helpers focused on geometry, transforms, validation, and data shaping.
- Pass in RhinoCommon objects or plain values instead of runtime-specific wrappers.
- Keep file IO, package imports, and UI prompts out of shared compatibility layers.

## Syntax To Avoid In Shared Code

- f-strings
- assignment expressions
- Python 3-only exception or iterator assumptions
- type-hint syntax that IronPython cannot parse

## Safe Defaults

```python
def format_name(name, count):
    return "{} ({})".format(name, count)
```

```python
def require_value(value, message):
    if value is None:
        raise Exception(message)
    return value
```

## Porting Strategy

### From IronPython to Rhino 8 CPython

- Keep RhinoCommon logic.
- Modernize syntax only after compatibility is no longer needed.
- Re-evaluate any old workarounds that existed only for IronPython limitations.

### From CPython to IronPython

- Remove Python 3-only syntax first.
- Strip external dependencies unless a pure .NET or IronPython-safe substitute exists.
- Test imports and string formatting early before debugging geometry logic.

## Common Pitfalls

- Assuming a package import available in Rhino 8 will work in GhPython.
- Copying CPython-only syntax into a legacy component.
- Mixing compatibility fixes throughout the whole script instead of isolating them.
- Forgetting that some online Rhino examples target a different runtime than yours.

## Decision Rule

If code does not need to run in IronPython, optimize for Rhino 8 CPython clarity.
If code must run in both, optimize for RhinoCommon portability and conservative syntax.
