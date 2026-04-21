---
name: ironpython-interop
description: Keep Rhino and Grasshopper scripts compatible across Rhino 8 CPython 3.9.10 and legacy IronPython workflows by avoiding unsupported language features, favoring RhinoCommon, and isolating runtime-specific code. Use when porting scripts, sharing code between runtimes, or reviewing compatibility risks.
---

# IronPython Interop

## Quick Start

Use this guide when code must survive in both Rhino 8 CPython and older IronPython-based Grasshopper environments.

## Core Rules

1. Treat CPython and IronPython as different runtimes with overlapping RhinoCommon access.
2. Put shared logic in runtime-neutral helper functions.
3. Isolate runtime-specific imports and features near the edges.
4. Prefer RhinoCommon over libraries that exist in only one runtime.
5. Avoid modern Python syntax if the same code must run in IronPython 2.7.

## Compatibility Defaults

- Write syntax that IronPython can parse when true cross-runtime compatibility is required.
- Avoid f-strings in shared code; use `.format()`.
- Avoid Python 3-only standard library assumptions in shared modules.
- Keep external dependency use out of compatibility-critical code.
- Prefer simple lists, tuples, dicts, and RhinoCommon types for handoff values.

## Porting Workflow

1. Identify the true target runtime for each script.
2. Split shared geometry logic from runtime bootstrapping.
3. Replace Python 3-only syntax in shared code if IronPython must support it.
4. Validate object and geometry behavior in both environments.
5. Keep one documented compatibility boundary instead of many small conditionals.

## Review Checklist

- Runtime assumptions are written down.
- Shared code avoids unsupported syntax.
- RhinoCommon is the main API surface.
- Runtime-specific branches are minimal and obvious.
- Error messages mention the expected runtime when relevant.

## Additional Resources

- For detailed compatibility notes, see [reference.md](reference.md).
