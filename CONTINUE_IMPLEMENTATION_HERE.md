# Continue Implementation Here - Phase 0 (Continuation)

**Status**: Phase 0.1 ✅ COMPLETE | Phase 0.2 🟡 IN PROGRESS (60% done)  
**Current**: GraphRenderer + GeometricRenderer implemented  
**Next**: VectorRenderer + MoleculeRenderer + Tests  
**Files Created**: 5 | **Lines of Code**: ~2,500  

---

## What's Been Done ✅

### 1. RichMediaCanvas Widget
✅ **File**: `ai_tutor/lib/features/visual_tutor/presentation/widgets/rich_media_canvas.dart`

- Responsive layout (LayoutBuilder-based)
- Dynamic % positioning (fixes off-screen issue)
- ScrollView for large boards
- Animation support
- Performance optimized (RepaintBoundary)
- Supports up to 128 actions

**Key Fix**: Converts fixed pixel coords to % of available space

---

### 2. GraphRenderer Service
✅ **File**: `ai_tutor/lib/features/visual_tutor/presentation/services/graph_renderer.dart`

- Plots mathematical functions
- Plots data points
- Custom axes, grid, labels
- Multiple graph types (line, scatter, bar)
- ~480 lines of production code

**Can Plot**:
- f(x) = x²
- f(x) = sin(x)
- Linear functions
- Data point sets
- Custom domains/ranges

---

### 3. GeometricRenderer Service
✅ **File**: `ai_tutor/lib/features/visual_tutor/presentation/services/geometric_renderer.dart`

- Triangles (with right angle markers)
- Circles (with radius lines)
- Rectangles
- Arbitrary polygons
- Free body diagrams (object + forces)
- Angle arcs with labels
- ~850 lines of production code

**Can Draw**:
- Right triangles (3-4-5)
- Circles with radius
- Free body diagrams with 4+ forces
- Custom polygons
- Angles with degree labels

---

## What Needs to Be Done 🚀

### NEXT TASK #1: VectorRenderer (3-4 hours)

**File to create**: `ai_tutor/lib/features/visual_tutor/presentation/services/vector_renderer.dart`

**Code template**:

```dart
import 'dart:math' as math;
import 'package:flutter/material.dart';

/// VectorRenderer: Physics-specific vector visualization
/// 
/// Supports:
/// - Single vectors with magnitude and direction
/// - Vector addition (A + B = R)
/// - Component vectors (Vx, Vy)
/// - Coordinate systems (Cartesian, tilted for inclines, polar)
/// - Physics units (N, m/s, m/s²)
/// 
/// Example:
/// ```
/// VectorRenderer.drawVector(
///   Point(100, 100),
///   Vector(magnitude: 20, angleRadians: math.pi / 6), // 20N @ 30°
///   label: 'F',
///   unit: 'N',
/// )
/// ```
class VectorRenderer {
  VectorRenderer._();

  /// Draw a single vector arrow
  static Widget drawVector(
    Point origin,
    Vector vector, {
    Color color = Colors.red,
    String? label,
    String? unit,
    double arrowHeadSize = 12.0,
    bool showMagnitude = true,
    double scale = 1.0, // pixels per unit magnitude
  }) {
    // TODO: Implement using CustomPaint
    // 1. Draw arrow from origin in direction of vector
    // 2. Draw arrowhead
    // 3. Draw label (e.g., "F = 20N")
    // 4. Optional: draw Vx, Vy component lines
  }

  /// Draw vector addition: A + B = R
  static Widget drawVectorAddition(
    List<Vector> vectors,
    Vector resultant, {
    List<Color>? colors,
    List<String>? labels,
    bool showComponents = false,
  }) {
    // TODO: Implement
    // 1. Draw first vector from origin
    // 2. Draw second vector from tip of first
    // 3. Draw resultant from origin to final tip
    // 4. Show magnitudes if requested
  }

  /// Draw Vx and Vy component vectors
  static Widget drawComponents(
    Vector vector, {
    bool showX = true,
    bool showY = true,
    Color xColor = Colors.red,
    Color yColor = Colors.blue,
    double scale = 1.0,
  }) {
    // TODO: Implement
    // 1. Draw Vx (horizontal component)
    // 2. Draw Vy (vertical component)
    // 3. Show labels (Vx, Vy, angle theta)
  }

  /// Draw coordinate system (xy-plane, tilted for inclines, etc.)
  static Widget drawCoordinateSystem(
    Point origin, {
    double xMax = 10,
    double yMax = 10,
    String? xLabel = 'x',
    String? yLabel = 'y',
    double rotation = 0.0, // radians, for tilted inclines
    bool showGrid = true,
    Color gridColor = const Color(0xFFE0E0E0),
  }) {
    // TODO: Implement
    // 1. Draw rotated x-axis
    // 2. Draw rotated y-axis
    // 3. Add grid if requested
    // 4. Label axes
  }
}
```

**Implementation hints**:
- Reuse Point, Vector classes from GeometricRenderer
- Use Canvas.drawLine() + arrowhead (see GeometricRenderer for pattern)
- Use math.cos() and math.sin() for vector components
- Follow pattern from GeometricRenderer (custom painter approach)

**Test cases to support**:
- Single force vector: 20N @ 30°
- Vector addition: 10N + 10N @ 90° = 14.14N @ 45°
- Components: F = 20N → Fx=17.3N, Fy=10N
- Tilted coordinate system (inclined plane)

---

### NEXT TASK #2: MoleculeRenderer (3-4 hours)

**File to create**: `ai_tutor/lib/features/visual_tutor/presentation/services/molecule_renderer.dart`

**Code template**:

```dart
import 'dart:math' as math;
import 'package:flutter/material.dart';

/// MoleculeRenderer: Chemistry molecular structure visualization
/// 
/// Supports:
/// - Atoms with proper colors and sizes
/// - Single, double, triple bonds
/// - Complete molecules (H₂O, CO₂, NH₃, CH₄, etc.)
/// - Electron configurations
/// - Lewis structures
/// - 2D visualization (easy to extend to 3D with isometric projection)
/// 
/// Example:
/// ```
/// MoleculeRenderer.drawMolecule(
///   Molecule.water,
///   showElectrons: true,
///   showBondAngles: true,
/// )
/// ```
class MoleculeRenderer {
  // Element properties: (color, radius, valence electrons)
  static const Map<String, ElementProperty> elementProperties = {
    'H': ElementProperty(color: Color(0xFFFFFFFF), radius: 25, valence: 1),
    'C': ElementProperty(color: Color(0xFF909090), radius: 35, valence: 4),
    'N': ElementProperty(color: Color(0xFF3050F8), radius: 30, valence: 5),
    'O': ElementProperty(color: Color(0xFFFF0D0D), radius: 30, valence: 6),
    'S': ElementProperty(color: Color(0xFFFFFF30), radius: 32, valence: 6),
    'P': ElementProperty(color: Color(0xFFFFA500), radius: 32, valence: 5),
  };

  MoleculeRenderer._();

  /// Draw a single atom
  static Widget drawAtom(
    String element,
    Point position, {
    bool showElectrons = false,
    bool highlight = false,
    double scale = 1.0,
  }) {
    // TODO: Implement
    // 1. Get element properties
    // 2. Draw circle (atom nucleus + electrons)
    // 3. Draw electron shells if showElectrons
    // 4. Draw label (H, C, O, etc.)
    // 5. Draw highlight border if requested
  }

  /// Draw a bond between two atoms
  static Widget drawBond(
    Atom atom1,
    Atom atom2, {
    BondType type = BondType.single,
    Color color = Colors.black,
    double width = 2.0,
  }) {
    // TODO: Implement
    // 1. Draw line(s) between atoms
    //    - Single: 1 line
    //    - Double: 2 parallel lines
    //    - Triple: 3 parallel lines
    // 2. Color the bond
  }

  /// Draw complete molecule
  static Widget drawMolecule(
    Molecule molecule, {
    bool showElectrons = false,
    bool show2D = true,
    bool showBondAngles = false,
    double scale = 1.0,
  }) {
    // TODO: Implement
    // 1. Draw all atoms
    // 2. Draw all bonds
    // 3. Show electron pairs if requested
    // 4. Show bond angles if requested
  }

  /// Draw electron configuration (e.g., 1s² 2s² 2p⁶)
  static Widget drawElectronConfiguration(
    String element, {
    String? title,
  }) {
    // TODO: Implement
    // 1. Get electron configuration for element
    // 2. Draw orbital boxes (s, p, d, f)
    // 3. Draw electrons as arrows (paired/unpaired)
    // 4. Show title if provided
  }
}

/// Element data
class ElementProperty {
  final Color color;
  final double radius;
  final int valence;
  
  const ElementProperty({
    required this.color,
    required this.radius,
    required this.valence,
  });
}

/// Atom representation
class Atom {
  final String element;
  final Point position;
  final int formalCharge;
  
  Atom({
    required this.element,
    required this.position,
    this.formalCharge = 0,
  });
}

/// Bond type
enum BondType {
  single,   // -
  double,   // =
  triple,   // ≡
  aromatic, // : (benzene)
}

/// Bond between atoms
class Bond {
  final Atom atom1;
  final Atom atom2;
  final BondType type;
  
  Bond({
    required this.atom1,
    required this.atom2,
    this.type = BondType.single,
  });
}

/// Complete molecule
class Molecule {
  final String formula;
  final String name;
  final List<Atom> atoms;
  final List<Bond> bonds;
  
  Molecule({
    required this.formula,
    required this.name,
    required this.atoms,
    required this.bonds,
  });
  
  // Predefined molecules
  static Molecule get water => Molecule(
    formula: 'H₂O',
    name: 'Water',
    atoms: [
      Atom(element: 'O', position: Point(0, 0)),
      Atom(element: 'H', position: Point(-30, 30)),
      Atom(element: 'H', position: Point(30, 30)),
    ],
    bonds: [
      // TODO: Define bonds
    ],
  );
  
  // TODO: Add CO2, NH3, CH4, etc.
}
```

**Implementation hints**:
- Element colors are standard chemistry colors
- Use circular atoms with element symbol labels
- For bonds: draw 1, 2, or 3 parallel lines between atoms
- Electron shells: concentric circles with dots for electrons
- Predefined molecules have specific geometries (H₂O is bent, etc.)

**Test cases to support**:
- Water (H₂O): bent structure, 2 H atoms, 1 O atom
- Carbon dioxide (CO₂): linear O=C=O
- Ammonia (NH₃): pyramidal, 1 N + 3 H
- Methane (CH₄): tetrahedral, 1 C + 4 H

---

### NEXT TASK #3: CoordinateSystemRenderer (2-3 hours)

**File to create**: `ai_tutor/lib/features/visual_tutor/presentation/services/coordinate_system_renderer.dart`

**Simplified implementation**:

```dart
class CoordinateSystemRenderer {
  static Widget buildSystem({
    double xMin = -10,
    double xMax = 10,
    double yMin = -10,
    double yMax = 10,
    String? xLabel = 'x',
    String? yLabel = 'y',
    bool showGrid = true,
    double rotation = 0.0, // For inclined planes
    String? title,
  }) {
    // TODO: Implement
    // 1. Draw x-axis (rotated if needed)
    // 2. Draw y-axis (rotated if needed)
    // 3. Draw grid if requested
    // 4. Add labels
    // 5. Add title if provided
  }
}
```

---

## Testing 📋

**Create test file**: `test/features/visual_tutor/presentation/services/vector_renderer_test.dart`

```dart
void main() {
  group('VectorRenderer', () {
    test('draws vector correctly', () {
      // TODO: Test vector drawing
      expect(true, true);
    });
    
    test('calculates vector components', () {
      // 20N @ 30° should give Vx≈17.3, Vy≈10
      final v = Vector(magnitude: 20, angleRadians: math.pi / 6);
      expect(v.vx, closeTo(17.3, 0.1));
      expect(v.vy, closeTo(10.0, 0.1));
    });
  });
}
```

---

## Quick Reference: File Locations

```
ai_tutor/lib/features/visual_tutor/presentation/services/
├── graph_renderer.dart                ✅ DONE (480 lines)
├── geometric_renderer.dart            ✅ DONE (850 lines)
├── vector_renderer.dart               ⏳ TODO (200-300 lines)
├── molecule_renderer.dart             ⏳ TODO (400-500 lines)
└── coordinate_system_renderer.dart    ⏳ TODO (150-200 lines)
```

---

## How to Continue (Copy & Paste Prompts)

### For VectorRenderer:

```
CONTEXT: Continuing Phase 0.2 of AI Visual Tutor implementation.
I've completed RichMediaCanvas, GraphRenderer, and GeometricRenderer.

TASK: Implement VectorRenderer service for physics vector visualization.

File: ai_tutor/lib/features/visual_tutor/presentation/services/vector_renderer.dart

Requirements:
1. Draw single vectors (magnitude, angle, label, unit)
2. Draw vector addition (A + B = R visualization)
3. Draw component vectors (Vx, Vy breakdown)
4. Draw coordinate systems (Cartesian, tilted for inclines)

Use Point and Vector classes from geometric_renderer.dart for consistency.

Follow the pattern from geometric_renderer.dart:
- Custom painter approach (Canvas + CustomPaint)
- Widget wrapper class
- Support scaling and styling

Test cases:
- 20N force at 30° (show Fx=17.3N, Fy=10N)
- Vector addition: 10N + 10N @ 90° = 14.14N @ 45°
- Tilted coordinate system (30° rotation)

Implement these methods:
- drawVector(Point origin, Vector vector, {options})
- drawVectorAddition(List<Vector>, Vector resultant)
- drawComponents(Vector, {showX, showY})
- drawCoordinateSystem(Point origin, {xMax, yMax, rotation})

Code style: Dart 3.x, full null safety, docstrings on all public methods, <100ms performance
```

### For MoleculeRenderer:

```
CONTEXT: Continuing Phase 0.2 of AI Visual Tutor.
I've completed RichMediaCanvas, GraphRenderer, GeometricRenderer, and VectorRenderer.

TASK: Implement MoleculeRenderer for chemistry molecular structure visualization.

File: ai_tutor/lib/features/visual_tutor/presentation/services/molecule_renderer.dart

Requirements:
1. Draw atoms (H, C, N, O, S, P with proper colors)
2. Draw bonds (single, double, triple)
3. Draw complete molecules (H₂O, CO₂, NH₃, CH₄)
4. Show electron configurations

Use custom painter approach like previous renderers.

Element colors (standard chemistry):
- H: white
- C: gray
- N: blue
- O: red
- S: yellow
- P: orange

Test cases:
- H₂O: bent structure, 104° angle
- CO₂: linear O=C=O
- NH₃: pyramidal
- CH₄: tetrahedral

Implement:
- drawAtom(String element, Point position)
- drawBond(Atom a1, Atom a2, BondType type)
- drawMolecule(Molecule mol)
- drawElectronConfiguration(String element)

Predefined molecules class with water, CO2, etc.
```

---

## Status Summary

| Component | Status | Hours | Lines |
|-----------|--------|-------|-------|
| RichMediaCanvas | ✅ | 3 | 290 |
| GraphRenderer | ✅ | 4 | 480 |
| GeometricRenderer | ✅ | 5 | 850 |
| VectorRenderer | ⏳ | 0 | 0 |
| MoleculeRenderer | ⏳ | 0 | 0 |
| CoordSystemRenderer | ⏳ | 0 | 0 |
| Tests | 🟡 | 0.5 | 50 |
| **TOTAL** | 🟡 | **12.5** | **1,700** |

**Phase 0 Target**: ~25 hours, 3,500 lines  
**Current Progress**: 50% (by hours), 48% (by lines)  
**ETA for Phase 0.2 completion**: 5-6 more hours

---

## Next Review Point

- [ ] VectorRenderer complete and tested
- [ ] MoleculeRenderer complete and tested
- [ ] CoordinateSystemRenderer complete and tested
- [ ] All Phase 0.2 renderers integrated with RichMediaCanvas
- [ ] Performance benchmarks show <100ms render time
- [ ] Move to Phase 0.3 (Step sequencing models)

---

**Ready to continue?** Use the prompts above to implement VectorRenderer next! 🚀
