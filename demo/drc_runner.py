#!/usr/bin/env python3
"""
KiCad DRC Runner — Production-ready wrapper for kicad-cli pcb drc

This module provides programmatic DRC (Design Rule Check) support for KiCad PCBs,
with JSON parsing and structured output.

Usage:
    from drc_runner import KicadDrcRunner

    runner = KicadDrcRunner()
    violations = runner.get_violations('board.kicad_pcb')
    print(f"Found {len(violations)} violations")
"""

import json
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum


class DrcSeverity(Enum):
    """DRC violation severity levels."""
    ERROR = "error"
    WARNING = "warning"
    EXCLUSION = "exclusion"


@dataclass
class DrcViolationItem:
    """Single violation instance (one location/occurrence)."""
    uuid: str
    reference: str
    pos_x: float
    pos_y: float
    layer: Optional[str] = None

    def __repr__(self) -> str:
        return f"DrcViolationItem({self.reference}@({self.pos_x},{self.pos_y}):{self.layer})"


@dataclass
class DrcViolation:
    """Grouped DRC violation with all occurrences."""
    violation_type: str
    severity: DrcSeverity
    description: str
    items: List[DrcViolationItem]

    def __repr__(self) -> str:
        return f"DrcViolation({self.violation_type}/{self.severity.value}: {len(self.items)} items)"


class KicadDrcRunner:
    """
    Runs KiCad DRC via kicad-cli and parses JSON output.

    Supports KiCad 8.x and 9.x on macOS, Linux, and Windows.
    """

    DEFAULT_KICAD_CLI_PATHS = {
        'darwin': '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli',
        'linux': '/usr/bin/kicad-cli',
        'linux2': '/usr/bin/kicad-cli',
        'win32': 'C:\\Program Files\\KiCad\\kicad-cli.exe',
    }

    def __init__(self, kicad_cli_path: Optional[str] = None, verbose: bool = False):
        """
        Initialize DRC runner.

        Args:
            kicad_cli_path: Explicit path to kicad-cli binary
            verbose: Print debug messages
        """
        self.verbose = verbose
        self.kicad_cli = self._find_kicad_cli(kicad_cli_path)

        if not self.kicad_cli or not self.kicad_cli.exists():
            raise FileNotFoundError(
                f"kicad-cli not found at {self.kicad_cli}. "
                f"Please install KiCad 8.x or later."
            )

        if self.verbose:
            print(f"Using kicad-cli: {self.kicad_cli}")

    def _find_kicad_cli(self, explicit_path: Optional[str]) -> Optional[Path]:
        """Find kicad-cli binary in standard locations."""
        if explicit_path:
            return Path(explicit_path)

        # Try platform-specific paths
        import platform
        platform_key = sys.platform
        if platform_key in self.DEFAULT_KICAD_CLI_PATHS:
            path = Path(self.DEFAULT_KICAD_CLI_PATHS[platform_key])
            if path.exists():
                return path

        # Try all known paths
        for path_str in self.DEFAULT_KICAD_CLI_PATHS.values():
            path = Path(path_str)
            if path.exists():
                return path

        return None

    def run(self, pcb_file: str, severity: str = 'all',
            units: str = 'mm', all_errors: bool = False,
            schematic_parity: bool = False) -> dict:
        """
        Run DRC on PCB file.

        Args:
            pcb_file: Path to .kicad_pcb file
            severity: 'all', 'error', 'warning', 'exclusions'
            units: 'mm', 'in', 'mils'
            all_errors: Report all errors per segment (vs. consolidated)
            schematic_parity: Check PCB/schematic net parity

        Returns:
            Raw parsed JSON dict from kicad-cli

        Raises:
            FileNotFoundError: PCB file not found
            RuntimeError: DRC execution failed or JSON parse error
        """
        pcb_path = Path(pcb_file)
        if not pcb_path.exists():
            raise FileNotFoundError(f"PCB file not found: {pcb_file}")

        cmd = [
            str(self.kicad_cli),
            'pcb', 'drc',
            str(pcb_path),
            '--format', 'json',
            f'--severity-{severity}',
            '--units', units,
        ]

        if all_errors:
            cmd.append('--all-track-errors')
        if schematic_parity:
            cmd.append('--schematic-parity')

        if self.verbose:
            print(f"Running: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        # Exit code 0 = no violations, 1 = violations found (valid), 3+ = error
        if result.returncode not in [0, 1]:
            raise RuntimeError(
                f"DRC failed with exit code {result.returncode}: {result.stderr}"
            )

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse DRC JSON output: {e}\n"
                f"Stdout: {result.stdout[:500]}\n"
                f"Stderr: {result.stderr}"
            )

    def get_violations(self, pcb_file: str) -> List[DrcViolation]:
        """
        Get structured DRC violations.

        Returns:
            List of DrcViolation objects with parsed positions and references
        """
        raw = self.run(pcb_file)
        violations = []

        for viol_data in raw.get('violations', []):
            # Parse items within this violation
            items = []
            for item in viol_data.get('items', []):
                items.append(DrcViolationItem(
                    uuid=item.get('uuid', ''),
                    reference=item.get('reference', ''),
                    pos_x=float(item.get('pos_x', 0)),
                    pos_y=float(item.get('pos_y', 0)),
                    layer=item.get('layer')
                ))

            # Create violation group
            violations.append(DrcViolation(
                violation_type=viol_data.get('type', 'unknown'),
                severity=DrcSeverity(viol_data.get('severity', 'warning')),
                description=viol_data.get('description', ''),
                items=items
            ))

        return violations

    def error_count(self, pcb_file: str) -> int:
        """Count DRC errors."""
        violations = self.get_violations(pcb_file)
        return sum(1 for v in violations if v.severity == DrcSeverity.ERROR)

    def warning_count(self, pcb_file: str) -> int:
        """Count DRC warnings."""
        violations = self.get_violations(pcb_file)
        return sum(1 for v in violations if v.severity == DrcSeverity.WARNING)

    def summary(self, pcb_file: str) -> Dict:
        """
        Get DRC summary statistics.

        Returns:
            dict with counts by type and severity
        """
        violations = self.get_violations(pcb_file)

        summary_by_type = {}
        for v in violations:
            if v.violation_type not in summary_by_type:
                summary_by_type[v.violation_type] = {
                    'error': 0,
                    'warning': 0,
                    'exclusion': 0,
                    'description': v.description
                }
            summary_by_type[v.violation_type][v.severity.value] += 1

        return {
            'total_violations': len(violations),
            'error_count': self.error_count(pcb_file),
            'warning_count': self.warning_count(pcb_file),
            'by_type': summary_by_type
        }

    def violations_by_type(self, pcb_file: str,
                           violation_type: str) -> List[DrcViolation]:
        """Filter violations by type."""
        violations = self.get_violations(pcb_file)
        return [v for v in violations if v.violation_type == violation_type]

    def violations_by_severity(self, pcb_file: str,
                               severity: DrcSeverity) -> List[DrcViolation]:
        """Filter violations by severity."""
        violations = self.get_violations(pcb_file)
        return [v for v in violations if v.severity == severity]

    def print_report(self, pcb_file: str, verbose: bool = False) -> None:
        """Print human-readable DRC report."""
        print(f"DRC Report: {pcb_file}\n")

        summary = self.summary(pcb_file)
        print(f"Summary:")
        print(f"  Total violations: {summary['total_violations']}")
        print(f"  Errors: {summary['error_count']}")
        print(f"  Warnings: {summary['warning_count']}")
        print()

        if summary['total_violations'] == 0:
            print("✓ No violations found")
            return

        print("Violations by type:")
        for vtype, stats in summary['by_type'].items():
            total = stats['error'] + stats['warning']
            print(f"  {vtype}:")
            if stats['error']:
                print(f"    Errors: {stats['error']}")
            if stats['warning']:
                print(f"    Warnings: {stats['warning']}")
            print(f"    Description: {stats['description']}")

        if verbose:
            print("\nDetailed violations:")
            violations = self.get_violations(pcb_file)
            for v in violations:
                print(f"\n  [{v.severity.value.upper()}] {v.violation_type}")
                print(f"    {v.description}")
                for item in v.items[:3]:  # Show first 3
                    print(f"      @ ({item.pos_x}, {item.pos_y}) {item.layer} - {item.reference}")
                if len(v.items) > 3:
                    print(f"      ... and {len(v.items) - 3} more")


def main():
    """Command-line interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Run KiCad DRC and parse results',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  drc_runner.py board.kicad_pcb
  drc_runner.py board.kicad_pcb --errors-only --json
  drc_runner.py board.kicad_pcb --verbose
        '''
    )

    parser.add_argument('pcb_file', help='Path to .kicad_pcb file')
    parser.add_argument('--errors-only', action='store_true',
                        help='Show errors only (not warnings)')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON')
    parser.add_argument('--verbose', action='store_true',
                        help='Print detailed violations')
    parser.add_argument('--kicad-cli', default=None,
                        help='Path to kicad-cli binary')

    args = parser.parse_args()

    try:
        runner = KicadDrcRunner(args.kicad_cli, verbose=args.verbose)

        if args.json:
            # JSON output
            violations = runner.get_violations(args.pcb_file)
            if args.errors_only:
                violations = [v for v in violations if v.severity == DrcSeverity.ERROR]

            output = {
                'file': str(args.pcb_file),
                'error_count': runner.error_count(args.pcb_file),
                'warning_count': runner.warning_count(args.pcb_file),
                'violations': [
                    {
                        'type': v.violation_type,
                        'severity': v.severity.value,
                        'description': v.description,
                        'count': len(v.items)
                    }
                    for v in violations
                ]
            }
            print(json.dumps(output, indent=2))
        else:
            # Human-readable report
            runner.print_report(args.pcb_file, verbose=args.verbose)

        # Exit code
        errors = runner.error_count(args.pcb_file)
        sys.exit(0 if errors == 0 else 1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
