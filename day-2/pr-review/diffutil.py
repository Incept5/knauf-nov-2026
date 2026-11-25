"""Small helpers for reading unified diffs. Used by review.py and risk_gate.py. Standard library only."""
import re


def split_by_file(diff_text):
    """Return [(path, text_of_that_file's_diff), ...] in the order the files appear."""
    chunks, current = [], []
    for line in diff_text.splitlines(keepends=True):
        if line.startswith("diff --git ") and current:
            chunks.append("".join(current))
            current = []
        current.append(line)
    if current:
        chunks.append("".join(current))
    return [(file_path(chunk), chunk) for chunk in chunks if chunk.strip()]


def file_path(file_diff):
    """The file a per-file diff is about (the new name; the old name if the file was deleted)."""
    for line in file_diff.splitlines():
        if line.startswith("+++ ") and not line.startswith("+++ /dev/null"):
            return re.sub(r"^b/", "", line[4:].strip())
        if line.startswith("--- ") and not line.startswith("--- /dev/null"):
            old = re.sub(r"^a/", "", line[4:].strip())
            if "+++ /dev/null" in file_diff:
                return old
    return "(unknown file)"


def changed_lines(file_diff):
    """(added, removed) line counts. Header lines before the first @@ are not counted."""
    added = removed = 0
    in_hunk = False
    for line in file_diff.splitlines():
        if line.startswith("@@"):
            in_hunk = True
        elif in_hunk and line.startswith("+"):
            added += 1
        elif in_hunk and line.startswith("-"):
            removed += 1
    return added, removed


def total_changed(diff_text):
    """Added + removed lines over the whole diff."""
    return sum(sum(changed_lines(text)) for _, text in split_by_file(diff_text))


def added_lines(diff_text):
    """Every added line (without the leading +), for scanning."""
    out = []
    for _, text in split_by_file(diff_text):
        in_hunk = False
        for line in text.splitlines():
            if line.startswith("@@"):
                in_hunk = True
            elif in_hunk and line.startswith("+"):
                out.append(line[1:])
    return out


def is_test_file(path):
    name = path.rsplit("/", 1)[-1]
    return path.startswith("tests/") or "/tests/" in path or name.startswith("test_") or name.endswith("_test.py")


def is_doc_file(path):
    return path.lower().endswith((".md", ".txt", ".rst"))
