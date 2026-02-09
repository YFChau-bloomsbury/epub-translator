#!/usr/bin/env python3
"""
Check for duplicate IDs in XML templates within log files in temp/logs.

Each XML root node is checked once, as the same XML may appear 1-3 times (request, response, retry).
Only IDs within the root node are checked for duplicates.
"""

import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


def extract_xml_blocks(log_content: str) -> list[tuple[str, int, int]]:
    """
    Extract all XML code blocks from log content.

    Returns: [(xml_content, start_line, end_line), ...]
    """
    lines = log_content.split("\n")
    blocks = []
    i = 0

    while i < len(lines):
        line = lines[i]
        # Check if it's the start of an XML code block
        if re.match(r"```[Xx][Mm][Ll]", line):
            start_line = i + 1  # Line numbers start at 1, and skip the ```XML line
            xml_lines = []
            i += 1

            # Collect XML content until ``` is encountered
            while i < len(lines):
                if lines[i].strip() == "```":
                    end_line = i  # End line number (excluding the ``` line)
                    xml_content = "\n".join(xml_lines)
                    blocks.append((xml_content, start_line + 1, end_line))  # +1 to convert to 1-based
                    break
                xml_lines.append(lines[i])
                i += 1

        i += 1

    return blocks


def extract_ids_from_xml(xml_string: str) -> list[str]:
    """Extract all id attributes from an XML string"""
    try:
        root = ET.fromstring(xml_string)
        ids = []

        # Traverse all elements (excluding the root node)
        for element in root.iter():
            if element is not root:  # Skip root node
                id_value = element.get("id")
                if id_value is not None:
                    ids.append(id_value)

        return ids
    except ET.ParseError as e:
        print(f"  Warning: Failed to parse XML: {e}", file=sys.stderr)
        return []


def check_duplicate_ids(ids: list[str]) -> list[str]:
    """Check for duplicates in a list of IDs and return the duplicate IDs"""
    counter = Counter(ids)
    duplicates = [id_val for id_val, count in counter.items() if count > 1]
    return duplicates


def check_log_file(log_file: Path) -> dict[str, Any]:
    """
    Check a single log file.

    Returns format:
    {
        'file': Path,
        'has_duplicates': bool,
        'xml_blocks': [
            {
                'index': int,
                'start_line': int,
                'end_line': int,
                'duplicate_ids': list[str],
                'id_counts': dict[str, int]
            }
        ]
    }
    """
    result = {"file": log_file, "has_duplicates": False, "xml_blocks": []}

    try:
        content = log_file.read_text(encoding="utf-8")
        xml_blocks = extract_xml_blocks(content)

        # To avoid duplication, we track checked XML content
        seen_xmls = set()

        for i, (xml_block, start_line, end_line) in enumerate(xml_blocks):
            # De-duplication: if this XML has already been checked, skip it
            if xml_block in seen_xmls:
                continue
            seen_xmls.add(xml_block)

            ids = extract_ids_from_xml(xml_block)
            if not ids:
                continue

            duplicates = check_duplicate_ids(ids)
            if duplicates:
                result["has_duplicates"] = True
                counter = Counter(ids)
                result["xml_blocks"].append(
                    {
                        "index": i,
                        "start_line": start_line,
                        "end_line": end_line,
                        "duplicate_ids": duplicates,
                        "id_counts": {id_val: counter[id_val] for id_val in duplicates},
                    }
                )

    except Exception as e:
        print(f"Error reading {log_file}: {e}", file=sys.stderr)

    return result


def main():
    # Get temp/logs directory
    script_dir = Path(__file__).parent
    logs_dir = script_dir.parent / "temp" / "logs"

    if not logs_dir.exists():
        print(f"Error: Logs directory not found: {logs_dir}")
        sys.exit(1)

    # Find all .log files
    log_files = sorted(logs_dir.glob("*.log"))

    if not log_files:
        print(f"No log files found in {logs_dir}")
        return

    print(f"Checking {len(log_files)} log files in {logs_dir}...")
    print()

    # Check each file
    total_issues = 0
    problematic_files = []

    for log_file in log_files:
        result = check_log_file(log_file)

        if result["has_duplicates"]:
            total_issues += 1
            problematic_files.append(result)

            for block_info in result["xml_blocks"]:
                # VSCode clickable format: file_path:line_start-line_end
                file_location = f"{log_file.absolute()}:{block_info['start_line']}-{block_info['end_line']}"
                print(f"❌ {file_location}")
                print(f"  XML block #{block_info['index']}:")
                for dup_id, count in block_info["id_counts"].items():
                    print(f"    - ID '{dup_id}' appears {count} times")
                print()

    # Summary
    print("=" * 60)
    if total_issues == 0:
        print("✅ No duplicate IDs found in any log files!")
    else:
        print(f"❌ Found duplicate IDs in {total_issues} log file(s)")
    print("=" * 60)

    # Return non-zero exit code if there are issues
    sys.exit(1 if total_issues > 0 else 0)


if __name__ == "__main__":
    main()
