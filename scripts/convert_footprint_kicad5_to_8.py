#!/usr/bin/env python3
"""
Convert KiCad 5 footprints (.kicad_mod files) to KiCad 8 format.

KiCad 5 uses (module ...) format.
KiCad 8 uses (footprint ...) format.

This script converts the S-expression syntax while preserving all geometric and
electrical data. It handles:
  - Root keyword: (module ...) → (footprint "...")
  - Version field: (version 4) → (version 20240108)
  - Generator tag: auto-adds if missing
  - String quoting: layer names, pad numbers, layer lists
  - Formatting: preserves indentation and structure

Usage:
    python convert_footprint_kicad5_to_8.py <input.kicad_mod> [output.kicad_mod]

    # Batch convert directory
    for f in old_footprints.pretty/*.kicad_mod; do
        python convert_footprint_kicad5_to_8.py "$f"
    done
"""

import re
import sys
from pathlib import Path
from typing import Tuple


def convert_kicad5_to_kicad8(content: str, verbose: bool = False) -> str:
    """
    Convert KiCad 5 (module ...) format to KiCad 8 (footprint ...) format.

    Args:
        content: Raw S-expression string from .kicad_mod file
        verbose: Print conversion steps

    Returns:
        Converted S-expression string
    """

    if verbose:
        print("[*] Converting KiCad 5 → KiCad 8 format...")

    # Step 1: Replace root keyword: (module NAME → (footprint "NAME"
    # Handle both quoted and unquoted names
    original_content = content
    match = re.search(r'\(module\s+(["\s]*)([^"\s)]+)(["\s]*)', content)
    if match:
        name = match.group(2).strip('"')
        content = re.sub(
            r'\(module\s+(["\s]*)([^"\s)]+)(["\s]*)',
            f'(footprint "{name}"',
            content,
            count=1
        )
        if verbose:
            print(f"  ✓ Root keyword: (module {name}) → (footprint \"{name}\")")

    # Step 2: Replace version field: (version 4) → (version 20240108)
    if re.search(r'\(version\s+\d+\)', content):
        content = re.sub(r'\(version\s+\d+\)', '(version 20240108)', content)
        if verbose:
            print("  ✓ Version: 4 → 20240108 (KiCad 8 date-based)")

    # Step 3: Add generator tag if not present
    if '(generator' not in content:
        # Insert after footprint line (after first newline following root)
        content = re.sub(
            r'(\(footprint "[^"]*"\n)',
            r'\1\t(generator "pcbnew")\n',
            content,
            count=1
        )
        if verbose:
            print("  ✓ Added generator tag: (generator \"pcbnew\")")

    # Step 4: Quote unquoted layer names: (layer F.Cu) → (layer "F.Cu")
    def quote_layer(match):
        layer = match.group(1)
        if not layer.startswith('"'):
            return f'(layer "{layer}")'
        return match.group(0)

    layer_pattern = r'\(layer\s+([A-Za-z0-9._-]+)(?:\s|$|\))'
    if re.search(layer_pattern, content):
        content = re.sub(layer_pattern, quote_layer, content)
        if verbose:
            print("  ✓ Quoted layer names in (layer ...) attributes")

    # Step 5: Quote pad numbers: (pad 1 ... → (pad "1" ...
    if re.search(r'\(pad\s+(\d+)\s+', content):
        content = re.sub(r'\(pad\s+(\d+)\s+', r'(pad "\1" ', content)
        if verbose:
            print("  ✓ Quoted pad numbers")

    # Step 6: Quote layer lists in pad definitions: (layers F.Cu ...) → (layers "F.Cu" ...)
    def quote_layers_in_pads(match):
        full_match = match.group(0)
        layers_str = match.group(1)

        # Skip if already quoted
        if layers_str.startswith('"'):
            return full_match

        # Quote each layer name
        layers = layers_str.split()
        quoted_layers = ' '.join(f'"{layer}"' for layer in layers)
        return f'(layers {quoted_layers})'

    layers_pattern = r'\(layers\s+([^)]+)\)'
    if re.search(layers_pattern, content):
        content = re.sub(layers_pattern, quote_layers_in_pads, content)
        if verbose:
            print("  ✓ Quoted layer names in (layers ...) pad attributes")

    # Step 7: Quote unquoted net names: (net 1 GND) → (net 1 "GND")
    # Be careful: nets can be unquoted numbers or quoted strings
    def quote_net_name(match):
        net_str = match.group(0)
        # Only quote if it's a bareword (not already quoted, not a number)
        if re.search(r'\(net\s+\d+\s+[A-Za-z]', net_str) and not re.search(r'\(net\s+\d+\s+"', net_str):
            # Find the bareword net name and quote it
            net_name_match = re.search(r'\(net\s+(\d+)\s+([A-Za-z_][A-Za-z0-9_]*)', net_str)
            if net_name_match:
                return f'(net {net_name_match.group(1)} "{net_name_match.group(2)}"'
        return net_str

    if re.search(r'\(net\s+\d+\s+[A-Za-z_]', content):
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '(net' in line:
                # Quote bareword net names
                line = re.sub(
                    r'\(net\s+(\d+)\s+([A-Za-z_][A-Za-z0-9_]*)(?=[)\s])',
                    r'(net \1 "\2"',
                    line
                )
                lines[i] = line
        content = '\n'.join(lines)
        if verbose:
            print("  ✓ Quoted net names in (net ...) attributes")

    if verbose:
        print("[✓] Conversion complete")

    return content


def detect_kicad_version(content: str) -> int:
    """
    Detect KiCad version from S-expression content.

    Returns:
        5 if (module ...) format detected
        6+ if (footprint ...) format detected
        0 if unable to detect
    """
    if re.search(r'^\s*\(module\s+', content, re.MULTILINE):
        return 5
    elif re.search(r'^\s*\(footprint\s+', content, re.MULTILINE):
        return 6
    return 0


def main():
    """Parse arguments and run conversion."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"✗ Input file not found: {input_file}")
        sys.exit(1)

    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if output_file is None:
        # Generate output filename
        output_file = input_file.with_stem(input_file.stem + "_kicad8")

    # Read input file
    try:
        with open(input_file, 'r') as f:
            original_content = f.read()
    except Exception as e:
        print(f"✗ Failed to read {input_file}: {e}")
        sys.exit(1)

    # Detect version
    version = detect_kicad_version(original_content)
    if version == 5:
        print(f"[*] Detected KiCad 5 format (module ...)")
    elif version == 6:
        print(f"[*] Detected KiCad 6+ format (footprint ...) — already modern")
        print(f"[→] Copying to output without conversion")
        with open(output_file, 'w') as f:
            f.write(original_content)
        print(f"[✓] Output: {output_file}")
        return
    else:
        print(f"[!] Warning: Could not detect KiCad version — proceeding with conversion attempt")

    # Convert
    try:
        converted_content = convert_kicad5_to_kicad8(original_content, verbose=True)
    except Exception as e:
        print(f"✗ Conversion failed: {e}")
        sys.exit(1)

    # Write output
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(converted_content)
    except Exception as e:
        print(f"✗ Failed to write {output_file}: {e}")
        sys.exit(1)

    # Verify conversion
    output_version = detect_kicad_version(converted_content)
    if output_version == 6:
        print(f"[✓] Output: {output_file}")
        print(f"[✓] Verification: KiCad 8 format confirmed (footprint ...)")

        # Optional: show diff summary
        if len(sys.argv) <= 2:
            lines_original = len(original_content.split('\n'))
            lines_converted = len(converted_content.split('\n'))
            print(f"[→] Lines: {lines_original} → {lines_converted}")
    else:
        print(f"[!] Warning: Output verification inconclusive")
        print(f"[→] Please review: {output_file}")


if __name__ == '__main__':
    main()
