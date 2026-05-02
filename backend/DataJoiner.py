"""
DataJoiner.py
Reads QueryOutput.json (DB results) and llm_output.json (join plan from LLM),
performs the in-memory join using the LLM-specified conditions, and prints the
final merged result to the screen in a formatted table.
"""

import json
import re
import sys
import os
from datetime import date, datetime

# Force UTF-8 on Windows console
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_condition(condition: str):
    """
    Parse an LLM join condition like:
        "Postgres_Sales_DB.customer_id = Mongo_Customer_DB.Customer.Customer_ID"
    Returns: (left_db, left_field, right_db, right_field)
    """
    parts = condition.split("=")
    if len(parts) != 2:
        raise ValueError(f"Cannot parse join condition: '{condition}'")
    
    def _split_path(path):
        segments = path.strip().split(".")
        if len(segments) < 2:
            raise ValueError(f"Invalid path in condition: '{path}'")
        db = segments[0]
        field = segments[-1]
        return db, field

    left_db, left_field = _split_path(parts[0])
    right_db, right_field = _split_path(parts[1])
    return left_db, left_field, right_db, right_field


def _get_field(row: dict, field: str):
    """Case-insensitive field lookup, handles dotted prefixes."""
    # 1. Direct match
    if field in row:
        return row[field]
    
    # 2. Case-insensitive direct match
    for k, v in row.items():
        if k.lower() == field.lower():
            return v
            
    # 3. Handle prefixes like DB.Table.Field -> match 'Field'
    if "." in field:
        short_field = field.split(".")[-1]
        for k, v in row.items():
            if k.lower() == short_field.lower():
                return v
                
    return None


def _coerce(val):
    """Normalize value for comparison (int/str coercion)."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return str(val)


# ---------------------------------------------------------------------------
# Core join logic
# ---------------------------------------------------------------------------
def _join_two(
    left_rows: list,
    right_rows: list,
    left_field: str,
    right_field: str,
    join_type: str = "inner",
) -> list:
    """
    Join two lists of dicts on the specified fields.
    Supports: inner, left, right.
    Returns merged rows (dicts).
    """
    # Verify keys exist
    l_key_count = sum(1 for r in left_rows if _get_field(r, left_field) is not None)
    r_key_count = sum(1 for r in right_rows if _get_field(r, right_field) is not None)
    
    if l_key_count == 0:
        print(f"  [CRITICAL] Join key '{left_field}' missing from ALL left rows!")
    if r_key_count == 0:
        print(f"  [CRITICAL] Join key '{right_field}' missing from ALL right rows!")

    # Build lookup index on the right side
    index: dict = {}
    for row in right_rows:
        key = _coerce(_get_field(row, right_field))
        if key is not None:
            index.setdefault(key, []).append(row)

    merged = []
    matched_right_keys = set()

    for left_row in left_rows:
        key = _coerce(_get_field(left_row, left_field))
        right_matches = index.get(key, [])

        if right_matches:
            for right_row in right_matches:
                combined = {**left_row}
                for k, v in right_row.items():
                    if k not in combined:
                        combined[k] = v
                    else:
                        combined[f"{k}_right"] = v   # avoid collision
                merged.append(combined)
                matched_right_keys.add(key)
        elif join_type in ("left", "full"):
            merged.append({**left_row})

    if join_type in ("right", "full"):
        for right_row in right_rows:
            key = _coerce(_get_field(right_row, right_field))
            if key not in matched_right_keys:
                merged.append({**right_row})

    return merged


# ---------------------------------------------------------------------------
# Pretty-print table
# ---------------------------------------------------------------------------
def _print_table(rows: list, title: str = "", max_rows: int = 100):
    if not rows:
        print(f"  [INFO] No rows to display.\n")
        return

    cols = list(rows[0].keys())
    col_widths = {
        c: max(len(str(c)), max(len(str(r.get(c, "") or "")) for r in rows))
        for c in cols
    }

    sep    = "+" + "+".join("-" * (col_widths[c] + 2) for c in cols) + "+"
    header = "|" + "|".join(f" {c:<{col_widths[c]}} " for c in cols) + "|"

    if title:
        print(f"\n  {title}")
    print("  " + sep)
    print("  " + header)
    print("  " + sep)
    for row in rows[:max_rows]:
        line = "|" + "|".join(f" {str(row.get(c, '') or ''):<{col_widths[c]}} " for c in cols) + "|"
        print("  " + line)
    print("  " + sep)
    if len(rows) > max_rows:
        print(f"  ... and {len(rows) - max_rows} more rows")
    print(f"\n  Total: {len(rows)} row(s)\n")


# ---------------------------------------------------------------------------
# Main join pipeline
# ---------------------------------------------------------------------------
def run_join(
    plan_file: str = "Outputs/llm_output.json",
    data_file: str = "Outputs/QueryOutput.json",
    output_file: str = "Outputs/FinalResult.json",
):
    plan = _load_json(plan_file)
    data = _load_json(data_file)

    join_info = plan.get("join", {})
    if join_info is None: join_info = {}
    
    join_type = join_info.get("type", "inner")
    if join_type is None: join_type = "inner"
    join_type = join_type.lower()
    
    conditions  = join_info.get("conditions", []) or []
    final_cols  = plan.get("final_select", [])
    user_prompt = plan.get("user_prompt", "")

    print("\n" + "=" * 70)
    print("  DataJoiner — merging cross-database results")
    if user_prompt:
        print(f"  Query: {user_prompt}")
    print("=" * 70)

    # ── Print per-DB summaries ────────────────────────────────────────────
    print("\n  Source datasets loaded:")
    for db_name, entry in data.items():
        print(f"    [{entry['db_type'].upper():10s}]  {db_name:30s}  {entry['row_count']} row(s)")

    # ── Collect all DB result sets ────────────────────────────────────────
    db_results = {name: entry["results"] for name, entry in data.items()}

    if not conditions:
        print("\n  [INFO] No join conditions found in plan. Proceeding with single dataset.")

    # ── Perform robust joins using available conditions ──────────────────
    print(f"\n  Join type : {join_type.upper()}")
    print(f"  Conditions: {len(conditions)}")
    for c in conditions:
        print(f"    - {c}")
    print()

    # We use a set of "available" datasets and "pending" conditions
    available_dbs = {name: rows for name, rows in db_results.items() if rows}
    pending_conditions = conditions[:]
    
    # We'll start by taking the first DB from the first condition as our starting "merged" set
    merged_rows = None
    applied_dbs = set()

    if pending_conditions:
        # Initial step: try to find a starting DB
        first_cond = pending_conditions[0]
        try:
            l_db, _, r_db, _ = _parse_condition(first_cond)
            if l_db in available_dbs:
                merged_rows = available_dbs[l_db][:]
                applied_dbs.add(l_db)
            elif r_db in available_dbs:
                merged_rows = available_dbs[r_db][:]
                applied_dbs.add(r_db)
        except: pass

    # Iteratively apply conditions that link to our "applied_dbs" set
    changed = True
    while changed and pending_conditions:
        changed = False
        remaining = []
        for condition in pending_conditions:
            try:
                l_db, l_field, r_db, r_field = _parse_condition(condition)
                
                # Case 1: Left is already in merged, Right is new
                if l_db in applied_dbs and r_db in available_dbs and r_db not in applied_dbs:
                    print(f"  Joining: {l_db}.{l_field} = {r_db}.{r_field}")
                    merged_rows = _join_two(merged_rows, available_dbs[r_db], l_field, r_field, join_type)
                    applied_dbs.add(r_db)
                    changed = True
                # Case 2: Right is already in merged, Left is new
                elif r_db in applied_dbs and l_db in available_dbs and l_db not in applied_dbs:
                    print(f"  Joining: {r_db}.{r_field} = {l_db}.{l_field}")
                    merged_rows = _join_two(merged_rows, available_dbs[l_db], r_field, l_field, join_type)
                    applied_dbs.add(l_db)
                    changed = True
                # Case 3: Both already in merged (redundant but possible)
                elif l_db in applied_dbs and r_db in applied_dbs:
                    # We could further filter here, but usually LLM uses this for multi-field joins
                    # For now, we skip to avoid duplicating rows if not careful
                    pass
                else:
                    remaining.append(condition)
            except Exception as e:
                print(f"  [SKIP] Error in condition '{condition}': {e}")
        
        pending_conditions = remaining

    # If merged_rows is still None (no conditions or no matching DBs), pick the first available DB
    if merged_rows is None:
        for name, rows in available_dbs.items():
            merged_rows = rows[:]
            applied_dbs.add(name)
            break

    # ── Include any remaining DBs as "islands" or fill with None ───────────
    for db_name, rows in available_dbs.items():
        if db_name not in applied_dbs:
            print(f"  [INFO] {db_name} not linked in join conditions — columns will be empty for merged rows")
            if merged_rows:
                for row in merged_rows:
                    for k in (rows[0] if rows else {}).keys():
                        if k not in row:
                            row[k] = None
            else:
                merged_rows = rows[:]
                applied_dbs.add(db_name)

    if merged_rows is None:
        merged_rows = []

    # ── Apply final_select projection ─────────────────────────────────────
    if final_cols:
        projected = []
        for row in merged_rows:
            proj_row = {}
            for col in final_cols:
                # Use only the base name (after last dot) for the final display key
                display_key = col.split(".")[-1]
                val = _get_field(row, col)
                proj_row[display_key] = val
            projected.append(proj_row)
    else:
        projected = merged_rows

    # ── Display final result ───────────────────────────────────────────────
    _print_table(
        projected,
        title=f"Final Result  (join: {join_type.upper()}, {len(projected)} row(s))",
    )

    # ── Save to file ───────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {"join_type": join_type if conditions else "none", "conditions": conditions,
             "final_select": final_cols, "row_count": len(projected), "results": projected},
            f, indent=4, default=str
        )

    print("=" * 70)
    print(f"  Final result saved to: {output_file}")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run_join(
        plan_file="Outputs/llm_output.json",
        data_file="Outputs/QueryOutput.json",
        output_file="Outputs/FinalResult.json",
    )
