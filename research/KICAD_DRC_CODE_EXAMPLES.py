#!/usr/bin/env python3
"""
KiCad 8.x Headless DRC Examples
Practical code snippets for running DRC programmatically

Author: Claude Code Research
Date: March 15, 2026
"""

import sys
import os
from pathlib import Path

# Set up pcbnew import path (adjust for your KiCad installation)
# macOS
sys.path.insert(0, '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/lib/python3.9/site-packages')
# Linux: usually in system path already
# Windows: sys.path.insert(0, r'C:\Program Files\KiCad\bin')

try:
    import pcbnew
except ImportError as e:
    print(f"Error importing pcbnew: {e}")
    print("Make sure KiCad is installed and the path is correct.")
    sys.exit(1)


# ============================================================================
# Example 1: Basic DRC Report Generation
# ============================================================================

def example_basic_drc(board_path):
    """
    Load a board and generate a DRC report file

    Args:
        board_path (str): Path to .kicad_pcb file
    """
    print("\n=== Example 1: Basic DRC Report ===")

    try:
        # Load the board
        print(f"Loading: {board_path}")
        board = pcbnew.LoadBoard(board_path)

        # Generate DRC report
        report_path = "drc_report.txt"
        success = pcbnew.WriteDRCReport(
            board,
            report_path,
            pcbnew.MM,  # Use millimeters (or pcbnew.INCHES)
            True        # Report all track errors
        )

        if success:
            print(f"✓ DRC report generated: {report_path}")

            # Read and display report
            with open(report_path, 'r') as f:
                print("\n--- DRC Report Content ---")
                print(f.read()[:500])  # First 500 chars
                print("...")
        else:
            print("✗ DRC report generation failed")

    except Exception as e:
        print(f"✗ Exception: {e}")


# ============================================================================
# Example 2: Access DRC Markers Directly
# ============================================================================

def example_read_markers(board_path):
    """
    Load a board and read DRC violation markers

    Note: Markers are populated after WriteDRCReport() or if DRC was run
    in the GUI and results were saved with the board.

    Args:
        board_path (str): Path to .kicad_pcb file
    """
    print("\n=== Example 2: Read DRC Markers ===")

    try:
        board = pcbnew.LoadBoard(board_path)

        # Run DRC first to populate markers
        print("Running DRC...")
        pcbnew.WriteDRCReport(board, "temp_drc.txt", pcbnew.MM, True)

        # Now read markers
        marker_count = board.GetMARKERCount()
        print(f"Found {marker_count} DRC markers")

        # Iterate through markers
        for i in range(marker_count):
            marker = board.GetMARKER(i)

            print(f"\nMarker {i}:")
            try:
                print(f"  Message: {marker.GetErrorMessage()}")
                print(f"  Severity: {marker.GetSeverity()}")
                pos = marker.GetPosition()
                print(f"  Position: ({pos.x}, {pos.y})")
            except AttributeError as e:
                print(f"  (Could not read marker properties: {e})")

    except Exception as e:
        print(f"✗ Exception: {e}")


# ============================================================================
# Example 3: Parse DRC Report File
# ============================================================================

def example_parse_drc_report(report_file):
    """
    Parse DRC report text file for violation count and types

    Args:
        report_file (str): Path to DRC report file
    """
    print("\n=== Example 3: Parse DRC Report ===")

    try:
        with open(report_file, 'r') as f:
            content = f.read()

        # Count different violation types
        violations = {
            'clearance': 0,
            'connection': 0,
            'unconnected': 0,
            'via': 0,
            'track': 0,
        }

        for line in content.split('\n'):
            line_lower = line.lower()
            if 'clearance' in line_lower:
                violations['clearance'] += 1
            elif 'connection' in line_lower or 'unconnected' in line_lower:
                violations['connection'] += 1
            elif 'via' in line_lower:
                violations['via'] += 1
            elif 'track' in line_lower:
                violations['track'] += 1

        print(f"Report file: {report_file}")
        print("\nViolation Summary:")
        for vtype, count in violations.items():
            if count > 0:
                print(f"  {vtype}: {count}")

    except FileNotFoundError:
        print(f"✗ Report file not found: {report_file}")
    except Exception as e:
        print(f"✗ Exception: {e}")


# ============================================================================
# Example 4: Batch DRC Check
# ============================================================================

def example_batch_drc(board_dir, output_dir="drc_results"):
    """
    Run DRC on all .kicad_pcb files in a directory

    Args:
        board_dir (str): Directory containing .kicad_pcb files
        output_dir (str): Directory to write DRC reports
    """
    print("\n=== Example 4: Batch DRC ===")

    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Find all board files
    board_files = list(Path(board_dir).glob("*.kicad_pcb"))

    if not board_files:
        print(f"No .kicad_pcb files found in {board_dir}")
        return

    print(f"Found {len(board_files)} board files\n")

    results = []

    for board_path in board_files:
        print(f"Processing: {board_path.name}...")

        try:
            board = pcbnew.LoadBoard(str(board_path))

            # Generate DRC report
            report_name = board_path.stem + "_drc.txt"
            report_path = os.path.join(output_dir, report_name)

            success = pcbnew.WriteDRCReport(
                board,
                report_path,
                pcbnew.MM,
                True
            )

            if success:
                # Count markers
                marker_count = board.GetMARKERCount()
                results.append({
                    'board': board_path.name,
                    'status': 'OK',
                    'markers': marker_count,
                    'report': report_path
                })
                print(f"  ✓ {marker_count} violations found")
            else:
                results.append({
                    'board': board_path.name,
                    'status': 'FAILED',
                    'markers': -1,
                    'report': None
                })
                print(f"  ✗ DRC failed")

        except Exception as e:
            results.append({
                'board': board_path.name,
                'status': 'ERROR',
                'markers': -1,
                'report': None,
                'error': str(e)
            })
            print(f"  ✗ Exception: {e}")

    # Summary
    print(f"\n=== Batch DRC Summary ===")
    print(f"Total boards: {len(results)}")
    print(f"Successful: {sum(1 for r in results if r['status'] == 'OK')}")
    print(f"Failed: {sum(1 for r in results if r['status'] in ['FAILED', 'ERROR'])}")

    total_violations = sum(r.get('markers', 0) for r in results if r.get('markers', -1) >= 0)
    print(f"Total violations: {total_violations}")


# ============================================================================
# Example 5: Full Pipeline with Error Handling
# ============================================================================

def example_robust_drc(board_path, output_dir="drc_output"):
    """
    Robust DRC pipeline with error handling and fallback

    Args:
        board_path (str): Path to .kicad_pcb file
        output_dir (str): Directory for output files

    Returns:
        dict: Results with keys 'success', 'marker_count', 'report_file', 'errors'
    """
    print("\n=== Example 5: Robust DRC Pipeline ===")

    results = {
        'success': False,
        'marker_count': 0,
        'report_file': None,
        'errors': []
    }

    # Validate input
    if not os.path.exists(board_path):
        results['errors'].append(f"Board file not found: {board_path}")
        return results

    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    report_path = os.path.join(output_dir, "drc_report.txt")

    try:
        print(f"Step 1: Loading board...")
        board = pcbnew.LoadBoard(board_path)
        print("  ✓ Board loaded")

        print(f"Step 2: Running DRC...")
        drc_success = pcbnew.WriteDRCReport(
            board,
            report_path,
            pcbnew.MM,
            True
        )

        if not drc_success:
            results['errors'].append("WriteDRCReport returned False")
            print("  ⚠ DRC reported failure (but may have succeeded)")

        print("  ✓ DRC completed")

        print(f"Step 3: Reading markers...")
        marker_count = board.GetMARKERCount()
        results['marker_count'] = marker_count
        print(f"  ✓ Found {marker_count} markers")

        print(f"Step 4: Generating summary...")
        violations_by_type = {}

        for i in range(marker_count):
            try:
                marker = board.GetMARKER(i)
                msg = str(marker.GetErrorMessage())

                # Categorize by first word
                category = msg.split()[0] if msg else "Unknown"
                violations_by_type[category] = violations_by_type.get(category, 0) + 1

            except Exception as e:
                print(f"  ⚠ Could not read marker {i}: {e}")

        print("  ✓ Summary generated")

        results['success'] = True
        results['report_file'] = report_path
        results['violations_by_type'] = violations_by_type

        # Print summary
        print(f"\n=== Results ===")
        print(f"Report: {report_path}")
        print(f"Total markers: {marker_count}")
        if violations_by_type:
            print("Violation types:")
            for vtype, count in violations_by_type.items():
                print(f"  {vtype}: {count}")

    except Exception as e:
        results['errors'].append(f"Exception during DRC: {str(e)}")
        print(f"  ✗ Exception: {e}")

    # Print errors if any
    if results['errors']:
        print(f"\n⚠ Errors encountered:")
        for error in results['errors']:
            print(f"  - {error}")

    return results


# ============================================================================
# Example 6: Integration with kicad-cli (More Stable Fallback)
# ============================================================================

def example_drc_with_fallback(board_path):
    """
    Try Python API first, fall back to kicad-cli if needed

    Args:
        board_path (str): Path to .kicad_pcb file
    """
    print("\n=== Example 6: DRC with kicad-cli Fallback ===")

    report_file = "drc_report.txt"

    # Try Python API first
    print("Attempting DRC via Python API...")
    try:
        board = pcbnew.LoadBoard(board_path)
        success = pcbnew.WriteDRCReport(board, report_file, pcbnew.MM, True)

        if success:
            print("✓ Python API DRC successful")
            return report_file

    except Exception as e:
        print(f"⚠ Python API failed: {e}")

    # Fall back to kicad-cli
    print("\nAttempting DRC via kicad-cli...")
    try:
        cmd = f"kicad-cli pcb drc {board_path} -o {report_file}"
        ret = os.system(cmd)

        if ret == 0:
            print(f"✓ kicad-cli DRC successful")
            return report_file
        else:
            print(f"✗ kicad-cli failed with code {ret}")

    except Exception as e:
        print(f"✗ kicad-cli exception: {e}")

    print("✗ Both DRC methods failed")
    return None


# ============================================================================
# Main: Run Examples
# ============================================================================

def main():
    """Run all examples"""

    print("=" * 70)
    print("KiCad 8.x Headless DRC Examples")
    print("=" * 70)

    # You would provide an actual board path
    # board_path = "path/to/your/board.kicad_pcb"

    # For demonstration, we'll just show what would run:
    print("\nExample code available:")
    print("  1. example_basic_drc(board_path)")
    print("  2. example_read_markers(board_path)")
    print("  3. example_parse_drc_report(report_file)")
    print("  4. example_batch_drc(board_dir)")
    print("  5. example_robust_drc(board_path, output_dir)")
    print("  6. example_drc_with_fallback(board_path)")

    print("\nTo use these examples:")
    print("  board_path = '/path/to/your/board.kicad_pcb'")
    print("  example_basic_drc(board_path)")

    # Uncomment to run with real board:
    # board_path = sys.argv[1] if len(sys.argv) > 1 else "board.kicad_pcb"
    # example_robust_drc(board_path)


if __name__ == '__main__':
    main()
