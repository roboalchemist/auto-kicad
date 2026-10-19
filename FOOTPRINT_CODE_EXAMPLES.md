# KiCad Footprint Generation - Code Examples

Complete, runnable examples for generating footprints with KicadModTree.

---

## Example 1: Basic SMD Resistor (0603)

**File**: `generate_basic_resistor.py`

```python
#!/usr/bin/env python3
"""
Generate a simple 0603 SMD resistor footprint.
This is the minimal working example for KicadModTree.
"""

from KicadModTree import *

def create_resistor_0603():
    # Create footprint object
    kicad_mod = Footprint("R_0603")

    # Set description
    kicad_mod.setDescription("Resistor 0603 (1.6mm x 0.8mm)")
    kicad_mod.setTags("resistor 0603")

    # Component dimensions (from datasheet)
    comp_width = 1.6   # Body width
    comp_height = 0.8  # Body height

    # Pad dimensions (from datasheet)
    pad_width = 0.8
    pad_height = 1.0

    # Courtyard clearance (IPC standard: min 0.25mm)
    courtyard_clearance = 0.25

    # ===== Pads (Electrical) =====
    # Pad 1 (Left)
    kicad_mod.append(Pad(
        number="1",
        type=PAD_TYPE_SMD,
        shape=PAD_SHAPE_RECT,
        at=[-comp_width/2 - pad_width/2, 0],
        size=[pad_width, pad_height],
        layers=LAYERS_SMD  # F.Cu, F.Mask, F.Paste
    ))

    # Pad 2 (Right)
    kicad_mod.append(Pad(
        number="2",
        type=PAD_TYPE_SMD,
        shape=PAD_SHAPE_RECT,
        at=[comp_width/2 + pad_width/2, 0],
        size=[pad_width, pad_height],
        layers=LAYERS_SMD
    ))

    # ===== Silk screen (reference/visual) =====
    # Top edge
    kicad_mod.append(Line(
        start=[-0.3, -comp_height/2],
        end=[0.3, -comp_height/2],
        layer="F.SilkS",
        width=0.1
    ))

    # Bottom edge
    kicad_mod.append(Line(
        start=[-0.3, comp_height/2],
        end=[0.3, comp_height/2],
        layer="F.SilkS",
        width=0.1
    ))

    # ===== Body outline (Fabrication layer) =====
    kicad_mod.append(RectLine(
        start=[-comp_width/2, -comp_height/2],
        end=[comp_width/2, comp_height/2],
        layer="F.Fab",
        width=0.1
    ))

    # ===== Courtyard (Assembly clearance) =====
    kicad_mod.append(RectLine(
        start=[
            -comp_width/2 - pad_width/2 - courtyard_clearance,
            -comp_height/2 - courtyard_clearance
        ],
        end=[
            comp_width/2 + pad_width/2 + courtyard_clearance,
            comp_height/2 + courtyard_clearance
        ],
        layer="F.CrtYd",
        width=0.05
    ))

    # ===== Text labels =====
    # Reference designator (on silk)
    kicad_mod.append(Text(
        type="reference",
        text="R?",
        at=[0, -1.3],
        layer="F.SilkS",
        size=[1, 1],
        thickness=0.15
    ))

    # Value (on fabrication layer)
    kicad_mod.append(Text(
        type="value",
        text="10k",
        at=[0, 1.3],
        layer="F.Fab",
        size=[1, 1],
        thickness=0.15
    ))

    return kicad_mod

if __name__ == "__main__":
    fp = create_resistor_0603()
    fp.save("R_0603.kicad_mod")
    print("Generated: R_0603.kicad_mod")
```

**Run:**
```bash
python3 generate_basic_resistor.py
# Output: R_0603.kicad_mod
```

---

## Example 2: Generate Multiple Sizes from Loop

**File**: `generate_resistor_series.py`

```python
#!/usr/bin/env python3
"""
Generate resistor footprints in common sizes: 0603, 0805, 1206, 1210.
Demonstrates parametric generation with a loop.
"""

from KicadModTree import *

# Component specifications (from datasheets)
RESISTOR_SIZES = {
    "0603": {
        "width": 1.6,
        "height": 0.8,
        "pad_width": 0.8,
        "pad_height": 1.0,
    },
    "0805": {
        "width": 2.0,
        "height": 1.25,
        "pad_width": 1.0,
        "pad_height": 1.2,
    },
    "1206": {
        "width": 3.2,
        "height": 1.6,
        "pad_width": 1.6,
        "pad_height": 1.8,
    },
    "1210": {
        "width": 3.2,
        "height": 2.5,
        "pad_width": 1.6,
        "pad_height": 2.7,
    },
}

def create_resistor_footprint(size_name, specs):
    """Create a resistor footprint with given specifications."""

    kicad_mod = Footprint(f"R_{size_name}")
    kicad_mod.setDescription(f"Resistor {size_name}")
    kicad_mod.setTags(f"resistor {size_name}")

    w = specs["width"]
    h = specs["height"]
    pw = specs["pad_width"]
    ph = specs["pad_height"]

    # Pads
    kicad_mod.append(Pad(
        number="1",
        type=PAD_TYPE_SMD,
        shape=PAD_SHAPE_RECT,
        at=[-(w/2 + pw/2), 0],
        size=[pw, ph],
        layers=LAYERS_SMD
    ))

    kicad_mod.append(Pad(
        number="2",
        type=PAD_TYPE_SMD,
        shape=PAD_SHAPE_RECT,
        at=[w/2 + pw/2, 0],
        size=[pw, ph],
        layers=LAYERS_SMD
    ))

    # Silk screen
    silk_start_x = 0.15
    kicad_mod.append(Line(
        start=[-silk_start_x, -h/2],
        end=[silk_start_x, -h/2],
        layer="F.SilkS",
        width=0.1
    ))

    kicad_mod.append(Line(
        start=[-silk_start_x, h/2],
        end=[silk_start_x, h/2],
        layer="F.SilkS",
        width=0.1
    ))

    # Body outline
    kicad_mod.append(RectLine(
        start=[-w/2, -h/2],
        end=[w/2, h/2],
        layer="F.Fab",
        width=0.1
    ))

    # Courtyard
    cy_margin = 0.25
    kicad_mod.append(RectLine(
        start=[-(w/2 + pw/2 + cy_margin), -(h/2 + cy_margin)],
        end=[w/2 + pw/2 + cy_margin, h/2 + cy_margin],
        layer="F.CrtYd",
        width=0.05
    ))

    # Text labels
    kicad_mod.append(Text(
        type="reference",
        text="R?",
        at=[0, -h/2 - 1.0],
        layer="F.SilkS",
        size=[1, 1],
        thickness=0.15
    ))

    kicad_mod.append(Text(
        type="value",
        text="10k",
        at=[0, h/2 + 1.0],
        layer="F.Fab",
        size=[1, 1],
        thickness=0.15
    ))

    return kicad_mod

if __name__ == "__main__":
    import os

    output_dir = "generated_resistors"
    os.makedirs(output_dir, exist_ok=True)

    for size_name, specs in RESISTOR_SIZES.items():
        fp = create_resistor_footprint(size_name, specs)
        output_file = f"{output_dir}/R_{size_name}.kicad_mod"
        fp.save(output_file)
        print(f"Generated: {output_file}")

    print(f"\nTotal: {len(RESISTOR_SIZES)} footprints generated")
```

**Run:**
```bash
python3 generate_resistor_series.py
# Output: generated_resistors/R_0603.kicad_mod, etc.
```

---

## Example 3: IC Package with Pin Array (16-pin DIP)

**File**: `generate_dip_package.py`

```python
#!/usr/bin/env python3
"""
Generate a 16-pin DIP (Dual In-line Package) footprint.
Demonstrates through-hole pad generation.
"""

from KicadModTree import *

def create_dip_footprint(pin_count, pitch=2.54):
    """
    Create a DIP footprint.

    Args:
        pin_count: Number of pins (8, 14, 16, 20, 24, 28, 40)
        pitch: Pin spacing (default 2.54mm for standard DIP)
    """

    kicad_mod = Footprint(f"DIP_{pin_count}")
    kicad_mod.setDescription(f"DIP Package, {pin_count} pins")
    kicad_mod.setTags(f"dip {pin_count}pin")

    # DIP body dimensions (approximate)
    body_width = 8.0 if pin_count <= 16 else 12.0
    body_height = pitch * (pin_count / 2 - 1) + 3.0

    # Through-hole pad dimensions
    drill_diameter = 0.8  # Hole diameter
    pad_diameter = 1.5    # Pad diameter

    pins_per_side = pin_count // 2

    # ===== Create pads =====
    for i in range(pin_count):
        # Alternate left and right
        if i < pins_per_side:
            # Left side
            pin_number = i + 1
            x = -body_width / 2
            y = (pins_per_side - 1 - i) * pitch - pitch / 2 * (pins_per_side - 1)
        else:
            # Right side
            pin_number = pin_count - i
            x = body_width / 2
            y = (i - pins_per_side) * pitch - pitch / 2 * (pins_per_side - 1)

        kicad_mod.append(Pad(
            number=str(pin_number),
            type=PAD_TYPE_THU,  # Through-hole
            shape=PAD_SHAPE_CIRCLE,
            at=[x, y],
            size=[pad_diameter, pad_diameter],
            drill=drill_diameter,
            layers=LAYERS_THU  # F.Cu, B.Cu, F.Mask, B.Mask
        ))

    # ===== Silk screen outline =====
    kicad_mod.append(Line(
        start=[-body_width/2, -body_height/2],
        end=[-body_width/2, body_height/2],
        layer="F.SilkS",
        width=0.1
    ))

    kicad_mod.append(Line(
        start=[-body_width/2, body_height/2],
        end=[body_width/2, body_height/2],
        layer="F.SilkS",
        width=0.1
    ))

    kicad_mod.append(Line(
        start=[body_width/2, body_height/2],
        end=[body_width/2, -body_height/2],
        layer="F.SilkS",
        width=0.1
    ))

    # Arc at bottom (indicates pin 1 side)
    kicad_mod.append(Arc(
        center=[-body_width/2 + 1.0, -body_height/2],
        start=[-body_width/2 + 1.0 - 0.5, -body_height/2],
        angle=180,
        layer="F.SilkS",
        width=0.1
    ))

    # ===== Fabrication layer outline =====
    kicad_mod.append(RectLine(
        start=[-body_width/2, -body_height/2],
        end=[body_width/2, body_height/2],
        layer="F.Fab",
        width=0.1
    ))

    # ===== Courtyard =====
    cy_clearance = 0.5
    kicad_mod.append(RectLine(
        start=[-body_width/2 - cy_clearance, -body_height/2 - cy_clearance],
        end=[body_width/2 + cy_clearance, body_height/2 + cy_clearance],
        layer="F.CrtYd",
        width=0.05
    ))

    # ===== Text =====
    kicad_mod.append(Text(
        type="reference",
        text="U?",
        at=[0, -body_height/2 - 1.5],
        layer="F.SilkS",
        size=[1, 1],
        thickness=0.15
    ))

    kicad_mod.append(Text(
        type="value",
        text=f"DIP{pin_count}",
        at=[0, body_height/2 + 1.5],
        layer="F.Fab",
        size=[1, 1],
        thickness=0.15
    ))

    return kicad_mod

if __name__ == "__main__":
    import os

    output_dir = "generated_dip"
    os.makedirs(output_dir, exist_ok=True)

    # Generate common DIP sizes
    for pin_count in [8, 14, 16, 20, 24, 28, 40]:
        fp = create_dip_footprint(pin_count)
        output_file = f"{output_dir}/DIP_{pin_count}.kicad_mod"
        fp.save(output_file)
        print(f"Generated: {output_file}")
```

**Run:**
```bash
python3 generate_dip_package.py
# Output: generated_dip/DIP_8.kicad_mod, DIP_14.kicad_mod, etc.
```

---

## Example 4: BGA Package (Ball Grid Array)

**File**: `generate_bga_package.py`

```python
#!/usr/bin/env python3
"""
Generate a BGA (Ball Grid Array) package footprint.
Example: 14x14 BGA with 0.5mm pitch, 0.35mm ball diameter.
"""

from KicadModTree import *
import math

def create_bga_footprint(rows, cols, pitch=0.5, ball_diameter=0.35):
    """
    Create a BGA footprint.

    Args:
        rows: Number of rows
        cols: Number of columns
        pitch: Ball-to-ball spacing (mm)
        ball_diameter: Solder ball diameter (mm)
    """

    name = f"BGA_{rows}x{cols}_P{pitch}mm"
    kicad_mod = Footprint(name)
    kicad_mod.setDescription(f"BGA {rows}x{cols}, {pitch}mm pitch")
    kicad_mod.setTags(f"bga {rows}x{cols}")

    # Package body dimensions (approximate)
    body_size = (max(rows, cols) - 1) * pitch + 2.0

    # Pad specifications
    pad_diameter = ball_diameter + 0.1  # Add solder margin

    # Generate pads in grid
    pin_counter = 1
    for row in range(rows):
        for col in range(cols):
            # Calculate position (center at origin)
            x = (col - (cols - 1) / 2) * pitch
            y = (row - (rows - 1) / 2) * pitch

            # Create pad
            kicad_mod.append(Pad(
                number=str(pin_counter),
                type=PAD_TYPE_SMD,
                shape=PAD_SHAPE_CIRCLE,
                at=[x, y],
                size=[pad_diameter, pad_diameter],
                layers=LAYERS_SMD  # Only front side for BGA
            ))

            pin_counter += 1

    # ===== Body outline =====
    kicad_mod.append(RectLine(
        start=[-body_size/2, -body_size/2],
        end=[body_size/2, body_size/2],
        layer="F.Fab",
        width=0.1
    ))

    # ===== Courtyard =====
    cy_clearance = 0.25
    kicad_mod.append(RectLine(
        start=[-body_size/2 - cy_clearance, -body_size/2 - cy_clearance],
        end=[body_size/2 + cy_clearance, body_size/2 + cy_clearance],
        layer="F.CrtYd",
        width=0.05
    ))

    # ===== Silk screen =====
    # Mark corner with line (indicates orientation)
    corner_size = 1.0
    kicad_mod.append(Line(
        start=[-body_size/2, -body_size/2],
        end=[-body_size/2 + corner_size, -body_size/2],
        layer="F.SilkS",
        width=0.1
    ))

    kicad_mod.append(Line(
        start=[-body_size/2, -body_size/2],
        end=[-body_size/2, -body_size/2 + corner_size],
        layer="F.SilkS",
        width=0.1
    ))

    # ===== Text =====
    kicad_mod.append(Text(
        type="reference",
        text="U?",
        at=[0, -body_size/2 - 1.5],
        layer="F.SilkS",
        size=[1.5, 1.5],
        thickness=0.15
    ))

    kicad_mod.append(Text(
        type="value",
        text=name,
        at=[0, body_size/2 + 1.5],
        layer="F.Fab",
        size=[1.5, 1.5],
        thickness=0.15
    ))

    return kicad_mod

if __name__ == "__main__":
    import os

    output_dir = "generated_bga"
    os.makedirs(output_dir, exist_ok=True)

    # Generate common BGA sizes
    configs = [
        (10, 10, 0.5),
        (14, 14, 0.5),
        (16, 16, 0.5),
        (12, 12, 1.0),
    ]

    for rows, cols, pitch in configs:
        fp = create_bga_footprint(rows, cols, pitch)
        output_file = f"{output_dir}/BGA_{rows}x{cols}_P{pitch}mm.kicad_mod"
        fp.save(output_file)
        print(f"Generated: {output_file}")
```

**Run:**
```bash
python3 generate_bga_package.py
# Output: generated_bga/BGA_10x10_P0.5mm.kicad_mod, etc.
```

---

## Example 5: Using YAML Configuration

**File**: `components.yaml`

```yaml
resistors:
  0603:
    description: "Resistor 0603 (1.6mm x 0.8mm)"
    width: 1.6
    height: 0.8
    pad_width: 0.8
    pad_height: 1.0

  0805:
    description: "Resistor 0805 (2.0mm x 1.25mm)"
    width: 2.0
    height: 1.25
    pad_width: 1.0
    pad_height: 1.2

  1206:
    description: "Resistor 1206 (3.2mm x 1.6mm)"
    width: 3.2
    height: 1.6
    pad_width: 1.6
    pad_height: 1.8

capacitors:
  0603:
    description: "Capacitor 0603"
    width: 1.6
    height: 0.8
    pad_width: 0.8
    pad_height: 1.0

  0805:
    description: "Capacitor 0805"
    width: 2.0
    height: 1.25
    pad_width: 1.0
    pad_height: 1.2
```

**File**: `generate_from_yaml.py`

```python
#!/usr/bin/env python3
"""
Generate footprints from YAML configuration file.
This demonstrates parameterized batch generation.
"""

import yaml
from KicadModTree import *

def create_footprint_from_spec(component_type, variant_name, spec):
    """Create footprint from specification dict."""

    fp_name = f"{component_type[0].upper()}_{variant_name}"
    kicad_mod = Footprint(fp_name)
    kicad_mod.setDescription(spec.get("description", ""))
    kicad_mod.setTags(f"{component_type} {variant_name}")

    w = spec["width"]
    h = spec["height"]
    pw = spec["pad_width"]
    ph = spec["pad_height"]

    # Pads
    kicad_mod.append(Pad(
        number="1",
        type=PAD_TYPE_SMD,
        shape=PAD_SHAPE_RECT,
        at=[-(w/2 + pw/2), 0],
        size=[pw, ph],
        layers=LAYERS_SMD
    ))

    kicad_mod.append(Pad(
        number="2",
        type=PAD_TYPE_SMD,
        shape=PAD_SHAPE_RECT,
        at=[w/2 + pw/2, 0],
        size=[pw, ph],
        layers=LAYERS_SMD
    ))

    # Silk screen
    kicad_mod.append(Line(
        start=[-0.2, -h/2],
        end=[0.2, -h/2],
        layer="F.SilkS",
        width=0.1
    ))

    kicad_mod.append(Line(
        start=[-0.2, h/2],
        end=[0.2, h/2],
        layer="F.SilkS",
        width=0.1
    ))

    # Body outline
    kicad_mod.append(RectLine(
        start=[-w/2, -h/2],
        end=[w/2, h/2],
        layer="F.Fab",
        width=0.1
    ))

    # Courtyard
    cy = 0.25
    kicad_mod.append(RectLine(
        start=[-(w/2 + pw/2 + cy), -(h/2 + cy)],
        end=[w/2 + pw/2 + cy, h/2 + cy],
        layer="F.CrtYd",
        width=0.05
    ))

    # Text
    kicad_mod.append(Text(
        type="reference",
        text="R?" if component_type == "resistors" else "C?",
        at=[0, -h/2 - 1.0],
        layer="F.SilkS",
        size=[1, 1],
        thickness=0.15
    ))

    kicad_mod.append(Text(
        type="value",
        text="10k" if component_type == "resistors" else "10u",
        at=[0, h/2 + 1.0],
        layer="F.Fab",
        size=[1, 1],
        thickness=0.15
    ))

    return kicad_mod

if __name__ == "__main__":
    import os

    # Load configuration
    with open("components.yaml") as f:
        config = yaml.safe_load(f)

    output_dir = "generated_from_yaml"
    os.makedirs(output_dir, exist_ok=True)

    # Generate footprints
    count = 0
    for component_type, variants in config.items():
        for variant_name, spec in variants.items():
            fp = create_footprint_from_spec(component_type, variant_name, spec)

            # Save with organized directory structure
            type_dir = f"{output_dir}/{component_type}"
            os.makedirs(type_dir, exist_ok=True)

            output_file = f"{type_dir}/{fp.name}.kicad_mod"
            fp.save(output_file)
            print(f"Generated: {output_file}")
            count += 1

    print(f"\nTotal: {count} footprints generated")
```

**Run:**
```bash
pip install PyYAML
python3 generate_from_yaml.py
# Output: generated_from_yaml/resistors/*.kicad_mod,
#         generated_from_yaml/capacitors/*.kicad_mod, etc.
```

---

## Example 6: Reading and Modifying Existing Footprints

**File**: `modify_footprints.py`

```python
#!/usr/bin/env python3
"""
Example of reading a KiCad footprint and modifying it.
Requires: pip install kicad-python
"""

# Note: This example requires the atait/kicad-python library
# It demonstrates batch modification of existing footprints

from kicad.pcbnew import Footprint
import os
import glob

def scale_footprint_pads(input_file, scale_factor, output_file):
    """
    Load a footprint and scale all pads by a factor.

    Args:
        input_file: Path to .kicad_mod file
        scale_factor: Scaling factor (1.1 = 10% larger)
        output_file: Output path
    """

    fp = Footprint.from_file(input_file)

    # Access and modify pads
    for pad in fp.pads:
        # Scale pad size
        if hasattr(pad, 'size'):
            pad.size[0] *= scale_factor
            pad.size[1] *= scale_factor

    # Save modified footprint
    fp.save(output_file)
    return fp

if __name__ == "__main__":
    import shutil

    # Example: Scale all footprints in a directory
    input_dir = "original_footprints"
    output_dir = "scaled_footprints"
    scale = 1.05  # 5% larger

    os.makedirs(output_dir, exist_ok=True)

    # Find all .kicad_mod files
    for kicad_mod_file in glob.glob(f"{input_dir}/*.kicad_mod"):
        basename = os.path.basename(kicad_mod_file)
        output_file = f"{output_dir}/{basename}"

        try:
            scale_footprint_pads(kicad_mod_file, scale, output_file)
            print(f"Scaled: {basename}")
        except Exception as e:
            print(f"Error processing {basename}: {e}")
```

---

## Example 7: Connector Footprint (USB Micro-B)

**File**: `generate_usb_connector.py`

```python
#!/usr/bin/env python3
"""
Generate USB Micro-B connector footprint.
This demonstrates a more complex component with mixed pad types.
"""

from KicadModTree import *

def create_usb_micro_b():
    """Create USB Micro-B connector footprint."""

    kicad_mod = Footprint("USB_Micro-B")
    kicad_mod.setDescription("USB Micro-B Connector")
    kicad_mod.setTags("usb micro b connector")

    # Component dimensions (from datasheet)
    body_length = 6.85
    body_height = 2.55
    body_width = 1.65

    # ===== Create pads =====
    # SMD pads for contacts
    smd_pads = [
        {"num": 1, "name": "GND", "x": -1.5, "y": 0},      # GND
        {"num": 2, "name": "D+", "x": -0.75, "y": 0},      # D+
        {"num": 3, "name": "D-", "x": 0, "y": 0},          # D-
        {"num": 4, "name": "VBUS", "x": 0.75, "y": 0},     # VBUS
        {"num": 5, "name": "ID", "x": 1.5, "y": 0},        # ID
    ]

    for pad in smd_pads:
        kicad_mod.append(Pad(
            number=str(pad["num"]),
            type=PAD_TYPE_SMD,
            shape=PAD_SHAPE_RECT,
            at=[pad["x"], pad["y"]],
            size=[0.8, 1.2],
            layers=LAYERS_SMD
        ))

    # Shield pads (through-hole for mechanical support)
    shield_pads = [
        {"num": 6, "x": -3.0, "y": 1.5},
        {"num": 7, "x": 3.0, "y": 1.5},
        {"num": 8, "x": -3.0, "y": -1.5},
        {"num": 9, "x": 3.0, "y": -1.5},
    ]

    for pad in shield_pads:
        kicad_mod.append(Pad(
            number=str(pad["num"]),
            type=PAD_TYPE_THU,
            shape=PAD_SHAPE_CIRCLE,
            at=[pad["x"], pad["y"]],
            size=[1.8, 1.8],
            drill=1.0,
            layers=LAYERS_THU
        ))

    # ===== Body outline =====
    kicad_mod.append(RectLine(
        start=[-body_length/2, -body_height/2],
        end=[body_length/2, body_height/2],
        layer="F.Fab",
        width=0.1
    ))

    # ===== Courtyard =====
    cy = 0.5
    kicad_mod.append(RectLine(
        start=[-body_length/2 - cy, -body_height/2 - cy],
        end=[body_length/2 + cy, body_height/2 + cy],
        layer="F.CrtYd",
        width=0.05
    ))

    # ===== Silk screen =====
    # Outline
    kicad_mod.append(Line(
        start=[-body_length/2, -body_height/2],
        end=[body_length/2, -body_height/2],
        layer="F.SilkS",
        width=0.1
    ))

    kicad_mod.append(Line(
        start=[-body_length/2, body_height/2],
        end=[body_length/2, body_height/2],
        layer="F.SilkS",
        width=0.1
    ))

    # ===== Text =====
    kicad_mod.append(Text(
        type="reference",
        text="J?",
        at=[0, -body_height/2 - 1.5],
        layer="F.SilkS",
        size=[1, 1],
        thickness=0.15
    ))

    kicad_mod.append(Text(
        type="value",
        text="USB_Micro-B",
        at=[0, body_height/2 + 1.5],
        layer="F.Fab",
        size=[1, 1],
        thickness=0.15
    ))

    return kicad_mod

if __name__ == "__main__":
    fp = create_usb_micro_b()
    fp.save("USB_Micro-B.kicad_mod")
    print("Generated: USB_Micro-B.kicad_mod")
```

---

## Installation & Dependencies

All examples require KicadModTree:

```bash
# Install
pip install KicadModTree

# For YAML examples, also install
pip install PyYAML

# For atait/kicad-python examples, install
pip install kicad-python
```

---

## Testing Generated Footprints

After generating, verify in KiCad:

1. **Open KiCad PCBNew**
2. **Place the footprint**: PCB Editor → Add Footprint
3. **Select your generated .kicad_mod file**
4. **Visual inspection**:
   - Pads aligned correctly
   - Silk screen visible and readable
   - Courtyard not overlapping pads
   - Text positioned appropriately

5. **Measure in KiCad**: Use the measurement tool to verify dimensions against datasheet

6. **Check 3D view**: If 3D model referenced, verify it aligns

---

## Common Modifications

### Adjust pad size for better solder joint
Increase pad dimensions by 10%:
```python
pad_width = 0.8 * 1.1  # 10% larger
pad_height = 1.0 * 1.1
```

### Add solder mask expansion
```python
kicad_mod.append(Pad(
    ...
    mask_expand=0.05  # Reduce mask by 0.05mm
))
```

### Add paste mask contraction
```python
kicad_mod.append(Pad(
    ...
    paste_shrink=0.1  # Shrink paste by 0.1mm
))
```

### Change silk screen width
```python
kicad_mod.append(Line(
    ...
    width=0.15  # Thicker line
))
```

---

## Next Steps

1. Run Example 1 (basic resistor)
2. Modify the dimensions and regenerate
3. Run Example 2 (multiple sizes)
4. Open generated files in KiCad and inspect
5. Use Examples 3-5 as templates for your components
6. Combine with Example 5 (YAML) for scalable generation

All examples are self-contained and can be run independently.
