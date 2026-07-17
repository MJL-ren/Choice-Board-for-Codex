# Authoring benchmark results

The benchmark compared direct canonical schema authoring with the internal
Minimal Draft compiler on locked 5-, 10-, and 15-question fixtures.

## Result

- Twelve fresh target runs completed on their first accepted submission.
- Every paired run produced byte-identical normalized canonical JSON.
- Every paired run produced byte-identical rendered output.
- Minimal Draft used roughly 15% fewer semantic input bytes across the three
  fixture sizes.
- The observed post-start authoring medians were modestly lower with Minimal
  Draft, but pair-to-pair noise was large enough that the project makes no speed
  guarantee.

The 15-question benchmark used a historical deterministic render-bundle step.
That harness detail does not define the current runtime question limit.

## Adoption decision

Minimal Draft is used only as an internal authoring adapter for fresh fixed
guided boards. It must compile into the public canonical schema before the
normal validator and renderer run. Compact, restored, completion, custom-copy,
and branching inputs continue to use canonical authoring directly.

Raw task identities, machine timings, and run directories are intentionally not
part of the public repository. The locked fixtures, compiler, golden canonical
output, and regression tests remain available for reproduction.
