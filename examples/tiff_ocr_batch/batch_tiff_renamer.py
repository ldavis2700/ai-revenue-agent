#!/usr/bin/env python3
"""Offline, review-first batch TIFF renaming by a user-specified captured text pattern.

No network calls; never overwrites a file. Tesseract and its language pack must
already be installed. This is a capability demo, NOT an accepted client deliverable.
"""
from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
import unicodedata


TIFF_EXTENSIONS = {'.tif', '.tiff'}
ALLOWED_PSM = (3, 6)  # default auto segmentation or opt-in uniform block


@dataclass(frozen=True)
class Decision:
    source: Path
    destination: Path | None
    status: str
    note: str = ''


def safe_stem(text: str, max_length: int = 80) -> str:
    """Normalize a captured label to a safe, portable, bounded filename stem."""
    ascii_text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    label = re.sub(r'[^A-Za-z0-9_-]+', '_', ascii_text).strip('._-')
    label = re.sub(r'_+', '_', label)[:max_length].rstrip('._-')
    if not label or label in {'.', '..'}:
        raise ValueError('unsafe_or_empty_capture')
    if label.upper() in {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'LPT1'}:
        raise ValueError('reserved_filename')
    return label


def extract_text(path: Path, *, language: str = 'eng', timeout: float = 20, page_segmentation: int = 3) -> str:
    """Run locally installed OCR; do not read or emit full source text in logs."""
    if type(page_segmentation) is not int or page_segmentation not in ALLOWED_PSM:
        raise ValueError('unsupported_page_segmentation')
    proc = subprocess.run(['tesseract', str(path), 'stdout', '-l', language, '--psm', str(page_segmentation)],
                          capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise RuntimeError('ocr_failed')
    return proc.stdout


def discover(directory: Path, recursive: bool, max_files: int) -> list[Path]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('input_must_be_real_directory')
    iterator = directory.rglob('*') if recursive else directory.iterdir()
    paths = sorted((p for p in iterator if p.suffix.lower() in TIFF_EXTENSIONS),
                   key=lambda p: str(p).casefold())
    if len(paths) > max_files:
        raise ValueError('file_count_exceeds_cap')
    return paths


def make_plan(files: list[Path], expression: str, language: str = 'eng', timeout: float = 20, page_segmentation: int = 3) -> list[Decision]:
    if type(page_segmentation) is not int or page_segmentation not in ALLOWED_PSM:
        raise ValueError('unsupported_page_segmentation')
    pattern = re.compile(expression)
    if pattern.groups != 1:
        raise ValueError('pattern_must_have_exactly_one_capture_group')
    results: list[Decision] = []
    used_targets: set[str] = set()
    original_names = {str(p.resolve(strict=False)).casefold() for p in files}
    for path in files:
        if path.is_symlink() or not path.is_file():
            results.append(Decision(path, None, 'blocked', 'non_regular_or_symlink'))
            continue
        try:
            text = extract_text(path, language=language, timeout=timeout, page_segmentation=page_segmentation)
            match = pattern.search(text)
            if not match:
                results.append(Decision(path, None, 'skipped', 'pattern_not_found'))
                continue
            stem = safe_stem(match.group(1))
            target = path.with_name(stem + path.suffix.lower())
            folded = str(target.resolve(strict=False)).casefold()
            if target == path:
                results.append(Decision(path, target, 'unchanged', 'already_named'))
            elif (target.exists() or folded in original_names or folded in used_targets):
                results.append(Decision(path, target, 'blocked', 'target_collision'))
            else:
                used_targets.add(folded)
                results.append(Decision(path, target, 'ready', ''))
        except (RuntimeError, ValueError, subprocess.TimeoutExpired, OSError) as exc:
            reason = ('ocr_timeout' if isinstance(exc, subprocess.TimeoutExpired) else
                      str(exc) if isinstance(exc, (RuntimeError, ValueError)) else 'io_error')
            results.append(Decision(path, None, 'blocked', reason))
    return results


def apply_plan(plan: list[Decision]) -> list[Decision]:
    if any(d.status == 'blocked' for d in plan):
        raise ValueError('blocked_plan_must_be_resolved_before_apply')
    updated: list[Decision] = []
    failed = False
    for d in plan:
        if failed or d.status != 'ready':
            updated.append(Decision(d.source, d.destination, 'not_attempted', 'previous_failure') if failed and d.status=='ready' else d)
            continue
        assert d.destination is not None
        if d.source.is_symlink() or d.destination.exists() or not d.source.is_file():
            updated.append(Decision(d.source, d.destination, 'blocked', 'changed_since_plan'))
            failed = True
            continue
        try:
            # An atomic hardlink-create refuses to replace a destination even if
            # another process creates one after the preflight check. Only then
            # remove the original; a failure can leave TWO copies, never data loss.
            os.link(d.source, d.destination, follow_symlinks=False)
            d.source.unlink()
            updated.append(Decision(d.source, d.destination, 'renamed', ''))
        except OSError:
            updated.append(Decision(d.source, d.destination, 'blocked', 'rename_io_error'))
            failed = True
    return updated


def write_manifest(path: Path, plan: list[Decision]) -> None:
    # Exclusive creation: never overwrite an earlier audit or accidentally store OCR text.
    with path.open('x', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['source', 'target', 'status', 'reason'])
        for d in plan:
            writer.writerow([str(d.source), str(d.destination or ''), d.status, d.note])


def apply_with_manifest(path: Path, plan: list[Decision]) -> list[Decision]:
    """Reserve and durably record the intended changes BEFORE mutating any input.

    On crash, an audit may contain only the planned phase. Reconcile actual
    source/destination state before retrying. Never blindly replay.
    """
    if any(d.status == 'blocked' for d in plan):
        raise ValueError('blocked_plan_must_be_resolved_before_apply')
    with path.open('x', newline='', encoding='utf-8') as audit:
        writer = csv.writer(audit)
        writer.writerow(['phase', 'source', 'target', 'status', 'reason'])
        for d in plan:
            writer.writerow(['planned', str(d.source), str(d.destination or ''), d.status, d.note])
        audit.flush()
        os.fsync(audit.fileno())
        results = apply_plan(plan)
        for d in results:
            writer.writerow(['result', str(d.source), str(d.destination or ''), d.status, d.note])
        audit.flush()
        os.fsync(audit.fileno())
        return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--pattern', required=True, help='regex with ONE capture group (e.g. Invoice: (\\w+))')
    parser.add_argument('--recursive', action='store_true')
    parser.add_argument('--language', default='eng')
    parser.add_argument('--ocr-timeout', type=float, default=20)
    parser.add_argument('--ocr-psm', type=int, choices=ALLOWED_PSM, default=3,
                        help='Tesseract segmentation: 3 auto (default), 6 uniform block; compare previews before apply')
    parser.add_argument('--max-files', type=int, default=1000)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--apply', action='store_true', help='actually rename after safe dry-run planning')
    args = parser.parse_args(argv)
    if args.max_files <= 0 or not 0 < args.ocr_timeout <= 120 or not re.fullmatch(r'[A-Za-z0-9_+-]+', args.language):
        parser.error('invalid safety limits or OCR language')
    if args.apply and not args.manifest:
        parser.error('apply_requires_manifest')
    try:
        plan = make_plan(discover(args.directory, args.recursive, args.max_files),
                         args.pattern, args.language, args.ocr_timeout, args.ocr_psm)
        # Preflight audit destination BEFORE any source rename; an existing or
        # unavailable manifest must never cause an unlogged partial apply.
        if args.manifest:
            if args.manifest.exists():
                raise ValueError('manifest_already_exists')
            if not args.manifest.parent.is_dir():
                raise ValueError('manifest_parent_missing')
        if args.apply:
            plan = apply_with_manifest(args.manifest, plan)
        elif args.manifest:
            write_manifest(args.manifest, plan)
    except (ValueError, OSError, re.error) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2
    for d in plan:
        print(f'{d.status.upper():9s} {d.source.name} -> {d.destination.name if d.destination else "-"}'
              + (f' [{d.note}]' if d.note else ''))
    print('SUMMARY ' + ', '.join(f'{k}={sum(d.status==k for d in plan)}'
                              for k in ('ready','renamed','unchanged','skipped','blocked')))
    return 1 if any(d.status == 'blocked' for d in plan) else 0


if __name__ == '__main__':
    sys.exit(main())
