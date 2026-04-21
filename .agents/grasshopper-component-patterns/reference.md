# Grasshopper Component Patterns Reference

## Recommended Script Shape

```python
import Rhino


def normalize_input(value):
    if value is None:
        raise ValueError("Missing input.")
    return value


def collect_data(doc, value):
    return value


def solve(data):
    return data


A = None

doc = Rhino.RhinoDoc.ActiveDoc
if doc is None:
    raise RuntimeError("No active Rhino document.")

value = normalize_input(x)
data = collect_data(doc, value)
A = solve(data)
```

## Best Practices

- Keep the top-level script short and readable.
- Use helper functions for recursion, filtering, and object conversion.
- Initialize outputs to safe defaults before work begins.
- Fail early on invalid inputs instead of returning corrupted partial results.
- Match the output order to the component UI.
- If reading block or nested instance geometry, accumulate transforms carefully and recursively.

## Rhino And Grasshopper Document Context

- Grasshopper is orchestrating evaluation, but Rhino document objects usually live in `Rhino.RhinoDoc.ActiveDoc`.
- Be explicit about which document owns the data you are reading or writing.
- If your script starts baking or editing objects, isolate those operations and make the trigger explicit.

## When To Use Parallel Lists

Use parallel lists when:

- each geometry item needs matching metadata
- output ports are already separated by concept
- downstream components benefit from simple list outputs

Prefer a tree when:

- branch structure has meaning
- you are preserving nested grouping
- flattening would destroy relationships

## Common Pitfalls

- Silent acceptance of the wrong object type.
- Returning geometry without the matching metadata order.
- Hiding input name fallbacks deep inside the logic.
- Mixing recursion, output assignment, and document queries in one loop.
- Writing to the Rhino document on every recompute.

## Testing Checklist

- Test with a valid object.
- Test with `None`.
- Test with a wrong object type.
- Test nested blocks or nested data if applicable.
- Test empty metadata cases.
- Confirm output ordering stays stable after refactors.
