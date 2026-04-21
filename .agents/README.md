# Rhino Agent Pack

This `.agents` folder stores reusable guidance for working with Rhino 8, Grasshopper, Rhino Python 3.9.10, and legacy IronPython-based workflows.

## Included Guides

- `rhino-8-python/SKILL.md`: default practices for Rhino 8 CPython scripting.
- `grasshopper-component-patterns/SKILL.md`: patterns for stable Grasshopper Python components.
- `ironpython-interop/SKILL.md`: rules for keeping code compatible across Rhino 8 CPython and legacy IronPython contexts.

## How To Use

- Start with the guide that matches the runtime you are in.
- Read the paired `reference.md` file when you need more detail.
- Prefer RhinoCommon-first solutions when code needs to survive across Rhino, Grasshopper, CPython, and IronPython.

## Runtime Map

- Rhino 8 `EditPythonScript` and Rhino 8 Python components: CPython 3.9.10.
- Legacy `GhPython` components: usually IronPython-based.
- Grasshopper scripts may run against the Grasshopper document while Rhino object access happens through the active Rhino document.

## Default Rule

When in doubt, write small pure helper functions, validate all external inputs early, avoid mutating source geometry in place, and keep document access isolated from computation.
