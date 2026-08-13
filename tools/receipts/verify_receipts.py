#!/usr/bin/env python3
"""Verify append-only evidence receipts and public-asset boundaries."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import sys


CLASSES = {
    "D0_DISCOVERY",
    "E1_ENGINEERING",
    "M2_MODEL_SELECTION",
    "S3_STRENGTH",
    "R4_RELEASE",
    "P5_POST_RELEASE",
}
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def run_git(root: pathlib.Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def verify_receipt(path: pathlib.Path) -> list[str]:
    errors: list[str] = []
    relative = path.as_posix()
    try:
        raw = path.read_bytes()
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{relative}: invalid JSON: {exc}"]

    evidence_class = data.get("evidence_class")
    if data.get("receipt_version") != 1:
        errors.append(f"{relative}: receipt_version must be 1")
    if evidence_class not in CLASSES:
        errors.append(f"{relative}: unknown evidence_class {evidence_class!r}")
    if evidence_class != path.parent.name:
        errors.append(
            f"{relative}: directory {path.parent.name!r} does not match "
            f"evidence_class {evidence_class!r}"
        )
    receipt_id = data.get("receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id.startswith(f"{evidence_class}-"):
        errors.append(f"{relative}: receipt_id must start with {evidence_class}-")
    timestamp = data.get("created_at_utc")
    if not isinstance(timestamp, str) or not UTC_RE.fullmatch(timestamp):
        errors.append(f"{relative}: created_at_utc must be second-precision UTC")
    else:
        try:
            dt.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            errors.append(f"{relative}: invalid created_at_utc: {exc}")

    sidecar = path.with_suffix(".sha256")
    if not sidecar.is_file():
        errors.append(f"{relative}: missing {sidecar.name}")
    else:
        expected_line = f"{hashlib.sha256(raw).hexdigest()}  {path.name}"
        actual_line = sidecar.read_text(encoding="ascii").strip()
        if actual_line != expected_line:
            errors.append(f"{sidecar.as_posix()}: digest or filename mismatch")
    return errors


def verify_immutability(root: pathlib.Path, base: str) -> list[str]:
    errors: list[str] = []
    diff = run_git(root, "diff", "--name-status", f"{base}...HEAD", "--", "receipts")
    for line in diff.splitlines():
        if not line:
            continue
        status, *paths = line.split("\t")
        if status != "A":
            errors.append(
                f"committed receipt is not append-only: status={status} "
                f"paths={' '.join(paths)}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        help="Git base commit/ref; existing receipts may only be added, never modified or deleted",
    )
    args = parser.parse_args()

    root = pathlib.Path(__file__).resolve().parents[2]
    errors: list[str] = []
    receipts_root = root / "receipts"
    json_receipts = sorted(receipts_root.glob("*/*.json"))
    if not json_receipts:
        errors.append("no evidence receipts found")
    for receipt in json_receipts:
        errors.extend(verify_receipt(receipt))

    tracked_networks = [
        line for line in run_git(root, "ls-files", "--", "*.nnue").splitlines() if line
    ]
    if tracked_networks:
        errors.append("tracked NNUE files are forbidden: " + ", ".join(tracked_networks))

    if args.base:
        errors.extend(verify_immutability(root, args.base))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"verified {len(json_receipts)} append-only receipt(s); no NNUE bytes tracked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
