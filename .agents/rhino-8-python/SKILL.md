---
name: rhino-8-python
description: Write Rhino 8 Python scripts using CPython 3.9.10 and RhinoCommon with safe document access, input validation, and geometry handling. Use when creating or reviewing Rhino 8 scripts, Rhino Python 3 components, or RhinoCommon-based automation.
---

# Rhino 8 Python

## Quick Start

Use this guide for Rhino 8 CPython scripts and Rhino 8 Python 3 Grasshopper components.

## Core Rules

1. Treat Rhino 8 Python as CPython 3.9.10, not IronPython.
2. Prefer RhinoCommon APIs over ad hoc command macros.
3. Validate every external input early and fail with a clear message.
4. Separate document access from geometry processing.
5. Duplicate geometry before transforming or mutating it.
6. Read model tolerance and units from the active document instead of hard-coding values.
7. Return structured results instead of printing-only workflows.

## Default Workflow

1. Resolve the correct document context.
2. Validate IDs, object types, and null cases.
3. Convert Rhino document objects into duplicated geometry or plain data.
4. Run pure helper functions on that data.
5. Return results in the format expected by Rhino or Grasshopper.

## Preferred Patterns

### Input validation

- Accept `Guid`, Rhino objects, or strings only when explicitly converted.
- Check for `None`, empty GUIDs, missing objects, and wrong object types.
- Raise short, precise exceptions for script failures.

### Document access

- Use `Rhino.RhinoDoc.ActiveDoc` for Rhino document objects.
- Keep document lookups near the top of the script.
- Avoid scattering document reads across business logic.

### Geometry safety

- Use `Duplicate()` or the type-specific duplicate method before transforms.
- Apply transforms to copies, not source geometry from the document.
- Preserve source metadata separately if downstream code needs it.

### Data design

- Keep related outputs aligned by index.
- Return names that match Grasshopper outputs exactly.
- Prefer dictionaries or parallel lists over ambiguous free-form text blobs.

## Review Checklist

- Runtime is correctly assumed to be CPython 3.9.10.
- RhinoCommon imports are at the top of the file.
- Inputs are validated before document access.
- Geometry is duplicated before mutation.
- Tolerance-sensitive operations use document tolerance.
- Exceptions are clear and actionable.

## Additional Resources

- For detailed practices, see [reference.md](reference.md).
