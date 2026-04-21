---
name: grasshopper-component-patterns
description: Build reliable Grasshopper Python components for Rhino 8 with predictable inputs, aligned outputs, document-safe geometry access, and minimal side effects. Use when creating or reviewing Grasshopper Python scripts, data-tree handling, or Rhino-backed component logic.
---

# Grasshopper Component Patterns

## Quick Start

Use this guide for Python components on the Grasshopper canvas, especially when the component reads Rhino document objects or returns transformed geometry.

## Core Rules

1. Make input names, type hints, and access settings explicit.
2. Keep component outputs deterministic for the same inputs.
3. Separate Rhino document lookups from computation.
4. Avoid side effects unless the component is explicitly for baking or document edits.
5. Keep output lists aligned and documented.
6. Support the component's declared input names only, unless backward compatibility is intentional.

## Preferred Workflow

1. Document expected inputs at the top of the script.
2. Read inputs and normalize them once.
3. Validate object existence and type.
4. Extract or duplicate Rhino geometry.
5. Compute results in helper functions.
6. Assign outputs once near the end.

## Output Design

- Use exact, stable output names.
- Keep related lists in matching order.
- Return empty lists instead of partial mixed states when computation cannot proceed.
- Use one output per concept instead of packing everything into text.

## Grasshopper-Specific Guidance

### Inputs

- Set the correct type hint whenever possible.
- Prefer `Item` access unless list semantics are required.
- If supporting multiple historical input names, handle that in one normalization block.

### Data handling

- Convert external Rhino object references into geometry or metadata early.
- Preserve mapping between geometry and metadata by appending to parallel lists in one place.
- Use trees only when downstream structure matters; otherwise keep outputs simple.

### Side effects

- Do not add or delete Rhino document objects during normal evaluation.
- If baking is required, isolate it behind an explicit boolean trigger.
- Avoid `print`-driven debugging as the main output contract.

## Review Checklist

- Input names and type hints are documented.
- The component does not mutate source geometry.
- Metadata ordering matches geometry ordering.
- The script handles missing or invalid Rhino objects cleanly.
- Output assignment is easy to trace.

## Additional Resources

- For detailed patterns, see [reference.md](reference.md).
