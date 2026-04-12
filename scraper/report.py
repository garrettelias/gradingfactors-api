"""
Human-readable diff output to the terminal.
"""
import json

from scraper.diff import FactorDiff, FieldChange, GrainDiff, ThresholdChange


def _fmt_value(v: object) -> str:
    if v is None:
        return "(null)"
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _fmt_threshold(t: dict | None) -> str:
    if t is None:
        return "(removed)"
    vtype = t.get("value_type", "?")
    val = t.get("value")
    note = t.get("threshold_note")
    s = f"{vtype}: {val}"
    if note:
        s += f" [{note}]"
    return s


def _print_field_changes(changes: list[FieldChange], indent: str = "  ") -> None:
    for change in changes:
        print(f"{indent}{change.field}:")
        print(f"{indent}  old: {_fmt_value(change.old_value)}")
        print(f"{indent}  new: {_fmt_value(change.new_value)}")


def _print_threshold_changes(changes: list[ThresholdChange], indent: str = "    ") -> None:
    for change in changes:
        old_s = _fmt_threshold(change.old) if change.old is not None else "(new grade)"
        new_s = _fmt_threshold(change.new) if change.new is not None else "(grade removed)"
        print(f"{indent}{change.grade}: {old_s}  →  {new_s}")


def _print_factor_diff(fd: FactorDiff) -> None:
    tag = f"[{fd.group_id} / {fd.factor_id}]"
    if fd.status == "added":
        print(f"  + {tag} {fd.factor_label}  (ADDED)")
    elif fd.status == "removed":
        print(f"  - {tag} {fd.factor_label}  (REMOVED)")
    else:
        print(f"  ~ {tag} {fd.factor_label}  (CHANGED)")
        if fd.field_changes:
            print("    field changes:")
            _print_field_changes(fd.field_changes, indent="      ")
        if fd.threshold_changes:
            print("    threshold changes:")
            _print_threshold_changes(fd.threshold_changes, indent="      ")


def print_report(diff: GrainDiff) -> None:
    """Print a human-readable diff report to stdout."""
    print(f"\n{'=' * 60}")
    print(f"  Diff report: {diff.grain_id}")
    print(f"{'=' * 60}")

    if diff.is_new:
        print("  STATUS: grain not found in DB — would be inserted as new.\n")
        return

    if not diff.has_changes:
        print("  No changes detected.\n")
        return

    if diff.grain_field_changes:
        print("\nGRAIN FIELDS CHANGED:")
        _print_field_changes(diff.grain_field_changes)

    added = [fd for fd in diff.factor_diffs if fd.status == "added"]
    removed = [fd for fd in diff.factor_diffs if fd.status == "removed"]
    changed = [fd for fd in diff.factor_diffs if fd.status == "changed"]

    if added:
        print(f"\nFACTORS ADDED ({len(added)}):")
        for fd in added:
            _print_factor_diff(fd)

    if removed:
        print(f"\nFACTORS REMOVED ({len(removed)}):")
        for fd in removed:
            _print_factor_diff(fd)

    if changed:
        print(f"\nFACTORS CHANGED ({len(changed)}):")
        for fd in changed:
            _print_factor_diff(fd)

    total = len(added) + len(removed) + len(changed)
    grain_changes = len(diff.grain_field_changes)
    print(
        f"\nSummary: {grain_changes} grain field(s) changed, "
        f"{total} factor(s) affected "
        f"({len(added)} added, {len(removed)} removed, {len(changed)} changed).\n"
    )
