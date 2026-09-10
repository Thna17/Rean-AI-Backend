# Visual Tutor STEM renderer scope

The public teaching-plan contract accepts only bounded declarative STEM actions.
Flutter calculates final placement from semantic layout zones; the model never
supplies a widget, canvas command, SVG, HTML, JavaScript, or executable code.

Supported now:

- Math: progressive text/equation transformations, number lines, axes, graphs,
  function plots, points, arrows, lines, circles, and rectangles.
- Physics: free-body diagrams, labelled vectors/arrows, motion graphs through
  the graph primitive, and transverse-wave diagrams.
- Chemistry: molecule structures, Bohr-style atom models, solid/liquid/gas
  particle diagrams, simple series circuits, and reaction-balancing layouts.

Deferred intentionally:

- ray diagrams with reflection/refraction geometry;
- parallel/branching circuits, meters, and circuit simulation;
- 3D molecular geometry, electron-cloud/orbital diagrams, and reaction
  mechanism arrows;
- an interactive periodic-table relationship explorer;
- arbitrary geometric construction scripts.

Each deferred item needs a separate bounded data schema, accessibility wording,
renderer implementation, and tests before its action type is added. Do not
fall back to raw SVG, HTML, JavaScript, Canvas paths, or Flutter widget code.
