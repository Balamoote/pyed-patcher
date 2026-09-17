#!/usr/bin/env python3
"""
Pyed-Patcher — Local alternative to codex-apply-patch.
Applies a custom patch format to the filesystem.
Reads patch from file or stdin. Only uses Python 3 standard library.
Features: colored output, automatic backups, patch comments display,
          dry-run mode, undo from backups, file filtering, interactive mode,
          validation, diff viewing, logging, save patch from stdin,
          template variables, multiple patches in one run,
          in-memory patch application, patch generation, Python API.
"""

import difflib
import os
import re
import shutil
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# --- Terminal Colors ---
class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def color_print(message: str, color: str = "", file=sys.stdout, end: str = "\n"):
    """Print colored message to terminal."""
    if sys.stdout.isatty() and color:
        print(f"{color}{message}{Colors.RESET}", file=file, end=end)
    else:
        print(message, file=file, end=end)


def colorize_files(message: str, filepaths: List[str]) -> str:
    """Replace all occurrences of filepaths in message with cyan-colored versions."""
    if not filepaths:
        return message

    sorted_paths = sorted(filepaths, key=len, reverse=True)

    for path in sorted_paths:
        if path and path in message:
            message = message.replace(path, f"{Colors.CYAN}{path}{Colors.RESET}")

    return message


def success(message: str, end: str = "\n"):
    """Print success message in green."""
    if sys.stdout.isatty():
        print(f"{Colors.GREEN}{message}{Colors.RESET}", end=end)
    else:
        print(message, end=end)


def error(message: str, filepaths: List[str] = None):
    """Print error message in red. File paths in message are colored cyan."""
    if filepaths:
        message = colorize_files(message, filepaths)
    color_print(f"Error: {message}", Colors.RED, file=sys.stderr)


def info(message: str, end: str = "\n", filepaths: List[str] = None):
    """Print info message in green."""
    if filepaths:
        message = colorize_files(message, filepaths)
    color_print(message, Colors.GREEN, file=sys.stderr, end=end)


def warn(message: str, filepaths: List[str] = None):
    """Print warning message: 'Warning:' in yellow, rest without color."""
    if filepaths:
        message = colorize_files(message, filepaths)
    color_print("Warning: ", Colors.YELLOW, file=sys.stderr, end="")
    print(message, file=sys.stderr)


def prompt(message: str) -> str:
    """Print cyan prompt and get user input."""
    color_print(message, Colors.CYAN, file=sys.stderr)
    return input()


# --- Logging ---
LOG_FILE = ".pyed-patcher.log"


def log_action(action: str, details: str = ""):
    """Log an action to the log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {action}"
    if details:
        entry += f" | {details}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except OSError:
        pass


# --- Backup System ---
def get_next_backup_number(filepath: str) -> str:
    """Find the next available backup number for a file."""
    directory = os.path.dirname(filepath) or "."
    filename = os.path.basename(filepath)

    pattern = re.compile(rf"{re.escape(filename)}\.(\d{{2}})$")
    existing_numbers = []

    try:
        for entry in os.listdir(directory):
            match = pattern.match(entry)
            if match:
                existing_numbers.append(int(match.group(1)))
    except OSError:
        pass

    if not existing_numbers:
        return "01"

    return f"{max(existing_numbers) + 1:02d}"


def create_backup(filepath: str) -> Optional[str]:
    """Create a backup of the file with incremental number extension."""
    if not os.path.exists(filepath):
        return None

    backup_num = get_next_backup_number(filepath)
    backup_path = f"{filepath}.{backup_num}"

    try:
        shutil.copy2(filepath, backup_path)
        info("Backup: ", end="")
        color_print(backup_path, Colors.CYAN, file=sys.stderr, end="")
        color_print(" ✓", Colors.GREEN, file=sys.stderr, end="\n")
        return backup_path
    except OSError as e:
        warn(f"Backup failed: {filepath} — {e}", filepaths=[filepath])
        return None


def find_latest_backup(filepath: str) -> Optional[str]:
    """Find the latest backup file for given filepath."""
    directory = os.path.dirname(filepath) or "."
    filename = os.path.basename(filepath)

    pattern = re.compile(rf"{re.escape(filename)}\.(\d{{2}})$")
    backups = []

    try:
        for entry in os.listdir(directory):
            match = pattern.match(entry)
            if match:
                num = int(match.group(1))
                backups.append((num, os.path.join(directory, entry)))
    except OSError:
        pass

    if not backups:
        return None

    backups.sort(key=lambda x: x[0], reverse=True)
    return backups[0][1]


def undo_file(filepath: str):
    """Restore a file from its latest backup."""
    if os.path.exists(filepath):
        create_backup(filepath)

    backup_path = find_latest_backup(filepath)
    if not backup_path:
        error(f"No backups: {filepath}", filepaths=[filepath])
        sys.exit(1)

    try:
        shutil.copy2(backup_path, filepath)
        success("Restored: ", end="")
        color_print(filepath, Colors.CYAN)
        success(f" ← {os.path.basename(backup_path)} ✓")
        log_action("UNDO", f"Restored {filepath} from {os.path.basename(backup_path)}")
    except OSError as e:
        error(f"Restore failed: {filepath} — {e}", filepaths=[filepath])
        sys.exit(1)


def undo_all_files():
    """Restore all files that have backups in current directory."""
    pattern = re.compile(r"^(.+)\.(\d{2})$")
    restored = set()

    try:
        for entry in sorted(os.listdir(".")):
            match = pattern.match(entry)
            if match:
                original_name = match.group(1)
                if original_name not in restored:
                    backup_path = find_latest_backup(original_name)
                    if backup_path:
                        if os.path.exists(original_name):
                            create_backup(original_name)
                        shutil.copy2(backup_path, original_name)
                        success("Restored: ", end="")
                        color_print(original_name, Colors.CYAN)
                        success(f" ← {os.path.basename(backup_path)} ✓")
                        restored.add(original_name)
    except OSError as e:
        error(f"Failed during undo-all: {e}")
        sys.exit(1)

    if not restored:
        warn("No backups found.")
    else:
        info(f"Restored {len(restored)} file(s).")
    log_action("UNDO-ALL", f"Restored {len(restored)} files")


# --- Template System ---
def resolve_templates(text: str, variables: Dict[str, str]) -> str:
    """Replace {{VAR}} placeholders with values from variables dict.
    Supports {{VAR:default}} syntax for default values."""

    def replace_var(match):
        inner = match.group(1)
        if ":" in inner:
            var_name, default = inner.split(":", 1)
            return variables.get(var_name.strip(), default.strip())
        return variables.get(inner, f"{{{{{inner}}}}}")

    return re.sub(r"\{\{(.+?)\}\}", replace_var, text)


def parse_template_vars(args: List[str]) -> Dict[str, str]:
    """Parse --var NAME=VALUE arguments into a dict."""
    variables = {}
    i = 0
    while i < len(args):
        if args[i] == "--var" and i + 1 < len(args):
            pair = args[i + 1]
            if "=" in pair:
                key, value = pair.split("=", 1)
                variables[key.strip()] = value.strip()
            i += 2
        else:
            i += 1
    return variables


# --- Custom Errors ---
class ApplyPatchError(Exception):
    """Base exception for patch application errors."""

    pass


class PatchParseError(ApplyPatchError):
    """Error during patch parsing."""

    def __init__(self, message, line_number=None):
        self.line_number = line_number
        loc = f" on line {line_number}" if line_number is not None else ""
        super().__init__(f"Patch parse error{loc}: {message}")


class PatchApplyError(ApplyPatchError):
    """Error during patch application to filesystem."""

    def __init__(self, message, file_path=None, backup_path=None):
        self.file_path = file_path
        self.backup_path = backup_path
        loc = f" for file '{file_path}'" if file_path else ""
        backup_info = f" (backup saved at {backup_path})" if backup_path else ""
        super().__init__(f"Patch apply error{loc}: {message}{backup_info}")


# --- Patch Parsing Structures ---
class Hunk:
    """Represents a single hunk in a patch."""

    pass


class AddFile(Hunk):
    def __init__(self, path: str, content: str):
        self.path = path
        self.content = content


class DeleteFile(Hunk):
    def __init__(self, path: str):
        self.path = path


class UpdateFile(Hunk):
    def __init__(self, path: str, chunks: List["ChangeChunk"], move_path: Optional[str] = None):
        self.path = path
        self.chunks = chunks
        self.move_path = move_path


class ChangeChunk:
    """Represents a single change block within an Update File hunk."""

    def __init__(self, context: Optional[str], old_lines: List[str], new_lines: List[str], is_eof: bool):
        self.context = context
        self.old_lines = old_lines
        self.new_lines = new_lines
        self.is_eof = is_eof


# --- Core Parsing Logic ---
def parse_patch(patch_text: str) -> Tuple[List[Hunk], List[str]]:
    """Parses the patch text and returns a list of Hunks and comments."""
    lines = patch_text.strip().splitlines()
    if not lines:
        raise PatchParseError("Patch is empty.")

    if lines[0].strip() != "*** Begin Patch":
        raise PatchParseError("Patch must start with '*** Begin Patch'.", line_number=1)
    if lines[-1].strip() != "*** End Patch":
        raise PatchParseError("Patch must end with '*** End Patch'.", line_number=len(lines))

    hunks = []
    inner_lines = lines[1:-1]
    i = 0
    line_no = 2
    comments = []

    while i < len(inner_lines):
        line = inner_lines[i]
        if not line.strip():
            i += 1
            line_no += 1
            continue

        if line.startswith("*** Add File: "):
            path = line[len("*** Add File: ") :].strip()
            content_lines = []
            i += 1
            line_no += 1
            while i < len(inner_lines) and inner_lines[i].startswith("+"):
                content_lines.append(inner_lines[i][1:])
                i += 1
                line_no += 1
            hunks.append(AddFile(path, "\n".join(content_lines) + "\n"))

        elif line.startswith("*** Delete File: "):
            path = line[len("*** Delete File: ") :].strip()
            hunks.append(DeleteFile(path))
            i += 1
            line_no += 1

        elif line.startswith("*** Update File: "):
            path = line[len("*** Update File: ") :].strip()
            i += 1
            line_no += 1

            move_path = None
            if i < len(inner_lines) and inner_lines[i].startswith("*** Move to: "):
                move_path = inner_lines[i][len("*** Move to: ") :].strip()
                i += 1
                line_no += 1

            chunks, consumed = parse_chunks(inner_lines, i, line_no)
            if not chunks:
                raise PatchParseError(f"Update file hunk for '{path}' is empty", line_no)
            hunks.append(UpdateFile(path, chunks, move_path))
            i += consumed
            line_no += consumed

        elif line.startswith("***"):
            if not line.startswith("*** Comment:"):
                warn(f"Skipping unknown marker: {line}")
            else:
                comment_text = line[len("*** Comment:") :].strip()
                if comment_text:
                    comments.append(comment_text)
            i += 1
            line_no += 1
        else:
            raise PatchParseError(f"Invalid hunk header: '{line}'", line_no)

    return hunks, comments


def parse_chunks(lines: List[str], start_idx: int, start_line_no: int) -> Tuple[List[ChangeChunk], int]:
    """Parses change chunks within an Update File hunk."""
    chunks = []
    i = start_idx
    line_no = start_line_no
    total_consumed = 0

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            line_no += 1
            total_consumed += 1
            continue
        if line.startswith("***"):
            break

        context = None
        is_eof = False
        chunk_start_line_no = line_no

        if line.startswith("@@ "):
            context = line[3:].strip()
            i += 1
            line_no += 1
            total_consumed += 1
        elif line == "@@":
            i += 1
            line_no += 1
            total_consumed += 1

        old_lines, new_lines = [], []
        chunk_consumed = 0

        while i + chunk_consumed < len(lines):
            current_line = lines[i + chunk_consumed]
            if current_line == "*** End of File":
                is_eof = True
                chunk_consumed += 1
                break
            if current_line.startswith("***") and not current_line.startswith("*** End of File"):
                break

            if current_line.startswith(" "):
                old_lines.append(current_line[1:])
                new_lines.append(current_line[1:])
            elif current_line.startswith("-"):
                old_lines.append(current_line[1:])
            elif current_line.startswith("+"):
                new_lines.append(current_line[1:])
            else:
                if chunk_consumed == 0:
                    raise PatchParseError(f"Unexpected line in update hunk: '{current_line}'", line_no + chunk_consumed)
                break
            chunk_consumed += 1

        if chunk_consumed == 0:
            raise PatchParseError("Update hunk does not contain any lines", chunk_start_line_no)

        chunks.append(ChangeChunk(context, old_lines, new_lines, is_eof))
        i += chunk_consumed
        line_no += chunk_consumed
        total_consumed += chunk_consumed

    return chunks, total_consumed


# --- Validation ---
def validate_hunks(hunks: List[Hunk]) -> List[str]:
    """Validate that hunks can be applied. Returns list of issues."""
    issues = []
    for hunk in hunks:
        if isinstance(hunk, AddFile):
            if os.path.exists(hunk.path):
                issues.append(f"File already exists: {hunk.path}")
        elif isinstance(hunk, DeleteFile):
            if not os.path.exists(hunk.path):
                issues.append(f"File not found for deletion: {hunk.path}")
        elif isinstance(hunk, UpdateFile):
            if not os.path.exists(hunk.path):
                issues.append(f"File not found for update: {hunk.path}")
            else:
                try:
                    with open(hunk.path, "r") as f:
                        content = f.read()
                    apply_changes(content, hunk.chunks, hunk.path)
                except ApplyPatchError as e:
                    issues.append(f"Cannot apply to {hunk.path}: {e}")
    return issues


def show_diff(hunks: List[Hunk]):
    """Show what changes would be made by the patch."""
    for hunk in hunks:
        if isinstance(hunk, AddFile):
            success("\nNew: ", end="")
            color_print(hunk.path, Colors.CYAN)
            for line in hunk.content.split("\n"):
                if line:
                    color_print(f"+ {line}", Colors.GREEN)

        elif isinstance(hunk, DeleteFile):
            color_print("\nDelete: ", Colors.RED, end="")
            color_print(hunk.path, Colors.CYAN)
            if os.path.exists(hunk.path):
                with open(hunk.path, "r") as f:
                    for line in f.read().split("\n"):
                        if line:
                            color_print(f"- {line}", Colors.RED)

        elif isinstance(hunk, UpdateFile):
            if hasattr(hunk, "move_path") and hunk.move_path:
                info(f"\nMove: {hunk.path} → {hunk.move_path}", filepaths=[hunk.path, hunk.move_path])
            else:
                info(f"\nModify: {hunk.path}", filepaths=[hunk.path])

            if os.path.exists(hunk.path):
                with open(hunk.path, "r") as f:
                    original = f.read()
                try:
                    new = apply_changes(original, hunk.chunks, hunk.path)
                    orig_lines = original.split("\n")
                    new_lines = new.split("\n")
                    diff = list(
                        difflib.unified_diff(
                            orig_lines, new_lines, fromfile=hunk.path, tofile=hunk.path, lineterm="", n=3
                        )
                    )
                    for dline in diff:
                        if dline.startswith("---") or dline.startswith("+++"):
                            continue
                        if dline.startswith("@@"):
                            color_print(f"  {dline}", Colors.CYAN)
                        elif dline.startswith("-"):
                            color_print(f"  {dline}", Colors.RED)
                        elif dline.startswith("+"):
                            color_print(f"  {dline}", Colors.GREEN)
                        else:
                            print(f"  {Colors.DIM}{dline}{Colors.RESET}")
                except ApplyPatchError as e:
                    color_print("Error: ", Colors.RED, file=sys.stderr, end="")
                    print(f"Cannot generate diff for ", file=sys.stderr, end="")
                    color_print(hunk.path, Colors.CYAN, file=sys.stderr, end="")
                    print(f": {e}", file=sys.stderr)


# --- File System Application Logic ---
def apply_hunks(hunks: List[Hunk], comments: List[str] = None, dry_run: bool = False, interactive: bool = False):
    """Applies parsed hunks to the filesystem.
    Returns dict of backups made: {filepath: backup_path}."""
    patch_comment = ""
    if comments:
        info("Comments:")
        for comment in comments:
            print(f"  • {comment}")
        patch_comment = " | ".join(comments)

    if dry_run:
        info("─── DRY RUN MODE — No files will be modified ───")
        print()

    added, modified, deleted = [], [], []
    backups_made = {}

    for hunk in hunks:
        if interactive:
            if isinstance(hunk, AddFile):
                color_print("Add new file: ", Colors.CYAN, file=sys.stderr, end="")
                color_print(hunk.path, Colors.CYAN, file=sys.stderr, end="")
                print("? [y/N/q]: ", file=sys.stderr, end="")
                answer = input().strip().lower()
            elif isinstance(hunk, DeleteFile):
                color_print("Delete file: ", Colors.CYAN, file=sys.stderr, end="")
                color_print(hunk.path, Colors.CYAN, file=sys.stderr, end="")
                print("? [y/N/q]: ", file=sys.stderr, end="")
                answer = input().strip().lower()
            elif isinstance(hunk, UpdateFile):
                info("Modify file: ", end="")
                color_print(hunk.path, Colors.CYAN, file=sys.stderr, end="")
                print("? [y/N/q]: ", file=sys.stderr, end="")
                answer = input().strip().lower()
            else:
                msg = f"Apply this change?"
                answer = prompt(f"{msg} [y/N/q]: ").strip().lower()
            if answer == "q":
                info("Aborted by user.")
                break
            if answer != "y":
                info("Skipping: ", end="")
                color_print(hunk.path, Colors.CYAN, file=sys.stderr)
                continue

        if isinstance(hunk, AddFile):
            if dry_run:
                info(f"Would create: {hunk.path}", filepaths=[hunk.path])
                preview = hunk.content.strip()[:120]
                if len(hunk.content.strip()) > 120:
                    preview += "..."
                for line in preview.split("\n")[:5]:
                    print(f"  + {line}")
                added.append(hunk.path)
            else:
                try:
                    os.makedirs(os.path.dirname(hunk.path) or ".", exist_ok=True)
                    with open(hunk.path, "w") as f:
                        f.write(hunk.content)
                    added.append(hunk.path)
                    log_action("ADD", f"Comment: {patch_comment} | File: {hunk.path}")
                except OSError as e:
                    raise PatchApplyError(f"Failed to add file: {e}", hunk.path)

        elif isinstance(hunk, DeleteFile):
            if dry_run:
                if os.path.exists(hunk.path):
                    info(f"Would delete: {hunk.path}", filepaths=[hunk.path])
                    deleted.append(hunk.path)
                else:
                    warn(f"File not found: {hunk.path}", filepaths=[hunk.path])
            else:
                try:
                    if os.path.exists(hunk.path):
                        backup_path = create_backup(hunk.path)
                        if backup_path:
                            backups_made[hunk.path] = backup_path
                        os.remove(hunk.path)
                        deleted.append(hunk.path)
                        log_action(
                            "DELETE",
                            f"Comment: {patch_comment} | File: {hunk.path} | Backup: {backups_made.get(hunk.path, 'none')}",
                        )
                    else:
                        raise PatchApplyError(f"File not found", hunk.path)
                except OSError as e:
                    raise PatchApplyError(f"Failed to delete: {e}", hunk.path)

        elif isinstance(hunk, UpdateFile):
            if dry_run:
                if os.path.exists(hunk.path):
                    with open(hunk.path, "r") as f:
                        original = f.read()
                    try:
                        new = apply_changes(original, hunk.chunks, hunk.path)
                        if hunk.move_path:
                            info(
                                f"Would move & modify: {hunk.path} -> {hunk.move_path}",
                                filepaths=[hunk.path, hunk.move_path],
                            )
                        else:
                            info(f"Would modify: {hunk.path}", filepaths=[hunk.path])
                        orig_lines = original.split("\n")
                        new_lines = new.split("\n")
                        diff = list(
                            difflib.unified_diff(
                                orig_lines, new_lines, fromfile=hunk.path, tofile=hunk.path, lineterm="", n=3
                            )
                        )
                        for dline in diff:
                            if dline.startswith("---") or dline.startswith("+++"):
                                continue
                            if dline.startswith("@@"):
                                print(f"  {Colors.BOLD}{dline}{Colors.RESET}")
                            elif dline.startswith("-"):
                                color_print(f"  {dline}", Colors.RED)
                            elif dline.startswith("+"):
                                color_print(f"  {dline}", Colors.GREEN)
                            else:
                                print(f"  {dline}")
                        if hunk.move_path:
                            modified.append(hunk.move_path)
                        else:
                            modified.append(hunk.path)
                    except ApplyPatchError as e:
                        color_print("Error: ", Colors.RED, file=sys.stderr, end="")
                        message = colorize_files(f"Would fail: {e}", [hunk.path])
                        print(message, file=sys.stderr)
                else:
                    warn(f"File not found: {hunk.path}", filepaths=[hunk.path])
            else:
                try:
                    with open(hunk.path, "r") as f:
                        original = f.read()
                    new = apply_changes(original, hunk.chunks, hunk.path)
                    # Бэкап создаём только после успешного apply_changes
                    backup_path = create_backup(hunk.path)
                    if backup_path:
                        backups_made[hunk.path] = backup_path
                    if hunk.move_path:
                        os.makedirs(os.path.dirname(hunk.move_path) or ".", exist_ok=True)
                        with open(hunk.move_path, "w") as f:
                            f.write(new)
                        os.remove(hunk.path)
                        modified.append(hunk.move_path)
                        log_action(
                            "MOVE",
                            f"Comment: {patch_comment} | File: {hunk.path} -> {hunk.move_path} | Backup: {backups_made.get(hunk.path, 'none')}",
                        )
                    else:
                        with open(hunk.path, "w") as f:
                            f.write(new)
                        modified.append(hunk.path)
                        log_action(
                            "MODIFY",
                            f"Comment: {patch_comment} | File: {hunk.path} | Backup: {backups_made.get(hunk.path, 'none')}",
                        )
                except FileNotFoundError:
                    raise PatchApplyError(f"File not found.", hunk.path)
                except OSError as e:
                    raise PatchApplyError(f"Failed to update: {e}", hunk.path, backup_path)

    # Print summary
    if dry_run:
        print()
        info("DRY RUN — no files modified")

    if added or modified or deleted:
        success("Updated:")
        for p in added:
            prefix = "Would add    " if dry_run else "A"
            success(f"  {prefix}  ", end="")
            color_print(f"{p}", Colors.CYAN)
        for p in modified:
            prefix = "Would modify " if dry_run else "M"
            success(f"  {prefix}  ", end="")
            color_print(f"{p}", Colors.CYAN)
        for p in deleted:
            prefix = "Would delete " if dry_run else "D"
            success(f"  {prefix}  ", end="")
            color_print(f"{p}", Colors.CYAN)
        if not dry_run:
            summary_parts = []
            if added:
                summary_parts.append(f"Added: {', '.join(added)}")
            if modified:
                summary_parts.append(f"Modified: {', '.join(modified)}")
            if deleted:
                summary_parts.append(f"Deleted: {', '.join(deleted)}")
            if backups_made:
                backups_list = ", ".join(f"{k} -> {v}" for k, v in backups_made.items())
                summary_parts.append(f"Backups: {backups_list}")
            log_action("SUCCESS: PATCH_APPLIED", " | ".join(summary_parts))
    else:
        if dry_run:
            warn("No changes.")

    return backups_made


def apply_changes(original_content: str, chunks: List[ChangeChunk], file_path: str) -> str:
    """Applies a list of ChangeChunks to the original file content."""
    lines = original_content.split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    replacements = []
    line_index = 0

    for chunk in chunks:
        if chunk.context:
            found = False
            for idx in range(line_index, len(lines)):
                if lines[idx].strip() == chunk.context.strip():
                    line_index = idx + 1
                    found = True
                    break
            if not found:
                raise PatchApplyError(f"Could not find context '{chunk.context}'", file_path)

        if not chunk.old_lines:
            insertion_idx = len(lines)
            replacements.append((insertion_idx, 0, chunk.new_lines))
            continue

        pattern = chunk.old_lines
        start_idx = seek_sequence(lines, pattern, line_index, chunk.is_eof)

        new_pattern = chunk.new_lines
        if start_idx is None and pattern and pattern[-1] == "":
            pattern = pattern[:-1]
            if new_pattern and new_pattern[-1] == "":
                new_pattern = new_pattern[:-1]
            start_idx = seek_sequence(lines, pattern, line_index, chunk.is_eof)

        if start_idx is not None:
            replacements.append((start_idx, len(pattern), new_pattern))
            line_index = start_idx + len(pattern)
        else:
            raise PatchApplyError(f"Could not find expected lines: {chunk.old_lines}", file_path)

    for start_idx, old_len, new_lines in reversed(replacements):
        del lines[start_idx : start_idx + old_len]
        for offset, line in enumerate(new_lines):
            lines.insert(start_idx + offset, line)

    if not lines or lines[-1] != "":
        lines.append("")
    return "\n".join(lines)


def seek_sequence(lines: List[str], pattern: List[str], start: int, is_eof: bool) -> Optional[int]:
    """Finds pattern in lines with flexible matching."""
    if not pattern:
        return start

    if len(pattern) > len(lines) - start:
        return None

    search_start = start
    if is_eof and len(lines) >= len(pattern):
        search_start = len(lines) - len(pattern)

    for i in range(search_start, len(lines) - len(pattern) + 1):
        if lines[i : i + len(pattern)] == pattern:
            return i

    for i in range(search_start, len(lines) - len(pattern) + 1):
        if all(a.rstrip() == b.rstrip() for a, b in zip(lines[i : i + len(pattern)], pattern)):
            return i

    for i in range(search_start, len(lines) - len(pattern) + 1):
        if all(a.strip() == b.strip() for a, b in zip(lines[i : i + len(pattern)], pattern)):
            return i

    def normalize(s: str) -> str:
        s = s.strip()
        replacements = {
            "\u2010": "-",
            "\u2011": "-",
            "\u2012": "-",
            "\u2013": "-",
            "\u2014": "-",
            "\u2015": "-",
            "\u2212": "-",
            "\u2018": "'",
            "\u2019": "'",
            "\u201a": "'",
            "\u201b": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u201e": '"',
            "\u201f": '"',
            "\u00a0": " ",
            "\u2002": " ",
            "\u2003": " ",
            "\u2004": " ",
            "\u2005": " ",
            "\u2006": " ",
            "\u2007": " ",
            "\u2008": " ",
            "\u2009": " ",
            "\u200a": " ",
            "\u202f": " ",
            "\u205f": " ",
            "\u3000": " ",
        }
        return "".join(replacements.get(c, c) for c in s)

    for i in range(search_start, len(lines) - len(pattern) + 1):
        if all(normalize(a) == normalize(b) for a, b in zip(lines[i : i + len(pattern)], pattern)):
            return i

    return None


# =============================================================================
# NEW FEATURES FROM ORIGINAL: In-Memory Application, Patch Generation, API
# =============================================================================


class InMemoryPatchResult:
    """Result of applying a patch to in-memory files."""

    def __init__(self):
        self.files: Dict[str, str] = {}
        self.deleted: List[str] = []
        self.added: List[str] = []
        self.modified: List[str] = []

    def __repr__(self):
        return (
            f"InMemoryPatchResult(files={len(self.files)}, "
            f"deleted={len(self.deleted)}, added={len(self.added)}, "
            f"modified={len(self.modified)})"
        )


def apply_patch_in_memory(patch: str, files: Dict[str, str]) -> InMemoryPatchResult:
    """Apply a patch to in-memory files instead of the filesystem.

    Args:
        patch: The patch text to apply.
        files: Dictionary mapping file paths to their current contents.

    Returns:
        InMemoryPatchResult with modified files, added, modified, deleted lists.
    """
    hunks, comments = parse_patch(patch)
    result = InMemoryPatchResult()

    result.files = dict(files)

    for hunk in hunks:
        if isinstance(hunk, AddFile):
            result.files[hunk.path] = hunk.content
            result.added.append(hunk.path)

        elif isinstance(hunk, DeleteFile):
            if hunk.path not in result.files:
                raise ApplyPatchError(f"Cannot delete file that doesn't exist: {hunk.path}")
            del result.files[hunk.path]
            result.deleted.append(hunk.path)

        elif isinstance(hunk, UpdateFile):
            if hunk.path not in result.files:
                raise ApplyPatchError(f"Cannot update file that doesn't exist: {hunk.path}")

            current_content = result.files[hunk.path]
            new_content = apply_changes(current_content, hunk.chunks, hunk.path)

            if hunk.move_path:
                result.files[hunk.move_path] = new_content
                del result.files[hunk.path]
                result.modified.append(hunk.move_path)
            else:
                result.files[hunk.path] = new_content
                result.modified.append(hunk.path)

    return result


def generate_patch(path: str, original_content: Optional[str], new_content: Optional[str]) -> str:
    """Generate a patch in the custom format from original and new file contents.

    Args:
        path: The file path (used in the patch output).
        original_content: The original file content (None if file is being added).
        new_content: The new file content (None if file is being deleted).

    Returns:
        A string containing the patch in the custom format.
    """
    patch = "*** Begin Patch\n"

    if original_content is None and new_content is not None:
        patch += f"*** Add File: {path}\n"
        for line in new_content.split("\n"):
            if line:
                patch += f"+{line}\n"

    elif original_content is not None and new_content is None:
        patch += f"*** Delete File: {path}\n"

    elif original_content is not None and new_content is not None:
        patch += f"*** Update File: {path}\n"

        if original_content == new_content:
            patch += "@@\n"
            if original_content.split("\n"):
                patch += f" {original_content.split(chr(10))[0]}\n"
        else:
            diff = list(
                difflib.unified_diff(
                    original_content.split("\n"), new_content.split("\n"), fromfile=path, tofile=path, lineterm="", n=3
                )
            )
            patch += "@@\n"
            for line in diff:
                if line.startswith("---") or line.startswith("+++"):
                    continue
                if line.startswith("@@"):
                    continue
                if line.startswith("-"):
                    patch += f"{line}\n"
                elif line.startswith("+"):
                    patch += f"{line}\n"
                elif line.startswith(" "):
                    patch += f"{line}\n"
                else:
                    patch += f" {line}\n"

    else:
        raise ApplyPatchError("Both original and new content cannot be None")

    patch += "*** End Patch"
    return patch


def generate_patch_from_files(file_changes: Dict[str, Tuple[Optional[str], Optional[str]]]) -> str:
    """Generate a patch for multiple files.

    Args:
        file_changes: Dictionary mapping file paths to (original_content, new_content) tuples.

    Returns:
        A string containing the patch in the custom format for all files.
    """
    patch = "*** Begin Patch\n"

    for path, (original, new) in file_changes.items():
        file_patch = generate_patch(path, original, new)
        lines = file_patch.split("\n")
        for line in lines[1:-1]:
            patch += line + "\n"

    patch += "*** End Patch"
    return patch


def parse_patch_info(patch: str) -> Tuple[List[str], List[str]]:
    """Parse a patch and return descriptions of its hunks and comments.

    Args:
        patch: The patch text to parse.

    Returns:
        Tuple of (hunk descriptions, comments).
    """
    hunks, comments = parse_patch(patch)
    descriptions = []

    for hunk in hunks:
        if isinstance(hunk, AddFile):
            descriptions.append(f"AddFile: {hunk.path}")
        elif isinstance(hunk, DeleteFile):
            descriptions.append(f"DeleteFile: {hunk.path}")
        elif isinstance(hunk, UpdateFile):
            move_info = f" -> {hunk.move_path}" if hunk.move_path else ""
            descriptions.append(f"UpdateFile: {hunk.path}{move_info} ({len(hunk.chunks)} chunks)")

    return descriptions, comments


# --- Main CLI Handler ---
def print_usage():
    """Print usage information."""
    print("Usage: python3 pyed-patcher.py [options] [patch1.txt] [patch2.txt ...]")
    print("       echo '...' | python3 pyed-patcher.py [options]")
    print("")
    print("Options:")
    print("  --dry-run          Preview changes without applying")
    print("  --undo FILE        Restore file from latest backup")
    print("  --undo-all         Restore all files with backups")
    print("  --only FILES...    Apply patch only to specified files")
    print("  --int              Interactive mode (confirm each change)")
    print("  --val              Validate patch without applying")
    print("  --show             Show diff of changes without applying")
    print("  --save [FILE]      Save patch from stdin to file")
    print("  --var KEY=VALUE    Replace {{KEY}} in patch with VALUE")
    print("  --parse            Parse patch and show structure")
    print("  --generate ORIG NEW [--as PATH]")
    print("                     Generate patch from two files")
    print("  --memory           Apply patch in memory (test mode, no disk changes)")
    print("  --help, -h         Show this help")
    print("")
    print("Multiple patch files can be specified — they will be applied in order.")
    print("Templates: use {{VAR}} or {{VAR:default}} in patches and --var to fill them.")
    print("")
    print("In-Memory API (Python):")
    print("  apply_patch_in_memory(patch_text, files_dict) -> InMemoryPatchResult")
    print("  generate_patch(path, original, new) -> patch_text")
    print("  generate_patch_from_files({path: (original, new)}) -> patch_text")
    print("  parse_patch_info(patch_text) -> (descriptions, comments)")
    print("")
    print("Patch file format example:")
    print("  *** Begin Patch")
    print("  *** Comment: Optional comment")
    print("  *** Add File: path/to/file.txt")
    print("  +content line 1")
    print("  +content line 2")
    print("  *** Update File: path/to/existing.txt")
    print("  @@")
    print("   context line")
    print("  -old line")
    print("  +new line")
    print("  *** End Patch")


def apply_single_patch(
    patch_content: str,
    flags: Dict[str, bool],
    only_files: List[str],
    variables: Dict[str, str],
    patch_name: str = "patch",
) -> bool:
    """Apply a single patch with all options."""
    if variables:
        patch_content = resolve_templates(patch_content, variables)
        info(f"Templates resolved ({len(variables)} variable(s))")

    try:
        hunks, comments = parse_patch(patch_content)
    except ApplyPatchError as e:
        color_print("Error: ", Colors.RED, file=sys.stderr, end="")
        message = colorize_files(f"{patch_name}: {e}", [patch_name])
        print(message, file=sys.stderr)
        return False

    if not hunks:
        warn(f"{patch_name}: No changes found.", filepaths=[patch_name])
        return True

    if flags.get("--parse", False):
        descriptions, comments = parse_patch_info(patch_content)

        if comments:
            info("Patch comments:")
            for comment in comments:
                print(f"  • {comment}")

        info(f"Patch structure ({len(descriptions)} hunk(s)):")
        for desc in descriptions:
            # Красим имена файлов в описании
            filepaths_in_desc = []
            for hunk in hunks:
                hpath = getattr(hunk, "path", "")
                if hpath and hpath in desc:
                    filepaths_in_desc.append(hpath)
            if filepaths_in_desc:
                colored_desc = colorize_files(desc, filepaths_in_desc)
                print(f"  • {colored_desc}")
            else:
                print(f"  • {desc}")
        return True

    if flags["--only"] and only_files:
        filtered = [h for h in hunks if hasattr(h, "path") and h.path in only_files]
        if not filtered:
            warn(f"No matching files in {patch_name} for: {', '.join(only_files)}", filepaths=[patch_name] + only_files)
            return True
        hunks = filtered
        info(f"Filtered to {len(hunks)} file(s): {', '.join(only_files)}", filepaths=only_files)

    if flags["--val"]:
        issues = validate_hunks(hunks)
        if issues:
            warn(f"Validation: {patch_name} — {len(issues)} issue(s)", filepaths=[patch_name])
            for issue in issues:
                print("  • ", file=sys.stderr, end="")
                # Красим все вхождения имён файлов из hunks
                filepaths_in_issue = []
                for hunk in hunks:
                    hpath = getattr(hunk, "path", "")
                    if hpath and hpath in issue:
                        filepaths_in_issue.append(hpath)
                if filepaths_in_issue:
                    colored_issue = colorize_files(issue, filepaths_in_issue)
                    print(colored_issue, file=sys.stderr)
                else:
                    print(issue, file=sys.stderr)
            return False
        else:
            success(f"Valid: {patch_name} ✓ ({len(hunks)} file(s))")
            return True

    if flags["--show"]:
        show_diff(hunks)
        return True

    try:
        apply_hunks(hunks, comments, dry_run=flags["--dry-run"], interactive=flags["--int"])
        return True
    except ApplyPatchError as e:
        color_print("Error: ", Colors.RED, file=sys.stderr, end="")
        # Собираем все имена файлов для окрашивания
        all_paths = [patch_name]
        if hasattr(e, "file_path") and e.file_path:
            all_paths.append(e.file_path)
        message = f"In {patch_name}: {e}"
        message = colorize_files(message, all_paths)
        print(message, file=sys.stderr)
        # Логируем FAIL
        fail_details = f"{patch_name}: {e}"
        log_action("FAIL: NO_ACTION", f"{fail_details} | Backups: NONE")
        return False
    except Exception as e:
        color_print("Error: ", Colors.RED, file=sys.stderr, end="")
        message = f"In {patch_name}: Unexpected error: {e}"
        message = colorize_files(message, [patch_name])
        print(message, file=sys.stderr)
        log_action("FAIL: NO_ACTION", f"{patch_name}: Unexpected: {e} | Backups: NONE")
        return False


def main():
    """Reads patch from file argument or stdin and applies it."""
    raw_args = sys.argv[1:]
    flags = {
        "--dry-run": False,
        "--undo": False,
        "--undo-all": False,
        "--only": False,
        "--int": False,
        "--val": False,
        "--show": False,
        "--save": False,
        "--parse": False,
        "--help": False,
        "--generate": False,
        "--memory": False,
    }

    if "-h" in raw_args:
        raw_args.remove("-h")
        raw_args.append("--help")

    flag_names = set(flags.keys())
    positional = []
    only_files = []
    save_path = None
    variables = {}
    i = 0

    while i < len(raw_args):
        arg = raw_args[i]
        if arg in flag_names:
            flags[arg] = True
            if arg == "--only":
                i += 1
                while i < len(raw_args) and not raw_args[i].startswith("--"):
                    only_files.append(raw_args[i])
                    i += 1
                continue
            if arg == "--save":
                i += 1
                if i < len(raw_args) and not raw_args[i].startswith("--"):
                    save_path = raw_args[i]
                continue
            if arg == "--var":
                i += 1
                if i < len(raw_args) and "=" in raw_args[i]:
                    key, value = raw_args[i].split("=", 1)
                    variables[key.strip()] = value.strip()
                continue
        else:
            positional.append(arg)
        i += 1

    if flags["--help"]:
        print_usage()
        sys.exit(0)

    if flags["--generate"]:
        if len(positional) < 2:
            error("Usage: python3 pyed-patcher.py --generate <original_file> <new_file> [--as <path_in_patch>]")
            sys.exit(1)
        orig_file = positional[0]
        new_file = positional[1]
        patch_path = positional[2] if len(positional) > 2 else new_file

        try:
            with open(orig_file, "r", encoding="utf-8") as f:
                original = f.read()
            with open(new_file, "r", encoding="utf-8") as f:
                new = f.read()
        except FileNotFoundError as e:
            error(f"File not found: {e.filename}", filepaths=[e.filename])
            sys.exit(1)
        except Exception as e:
            error(f"Cannot read files: {e}")
            sys.exit(1)

        patch = generate_patch(patch_path, original, new)
        print(patch)
        sys.exit(0)

    if flags["--memory"]:
        if not positional:
            error("Usage: python3 pyed-patcher.py --memory <patch_file> [--var KEY=VALUE ...]")
            sys.exit(1)

        patch_file = positional[0]
        try:
            with open(patch_file, "r", encoding="utf-8") as f:
                patch_content = f.read()
        except FileNotFoundError:
            error(f"File not found: {patch_file}", filepaths=[patch_file])
            sys.exit(1)
        except Exception as e:
            error(f"Cannot read: {patch_file} — {e}", filepaths=[patch_file])
            sys.exit(1)

        if variables:
            patch_content = resolve_templates(patch_content, variables)
            info(f"Templates resolved ({len(variables)} variable(s))")

        try:
            hunks, comments = parse_patch(patch_content)
        except ApplyPatchError as e:
            error(f"{patch_file}: {e}", filepaths=[patch_file])
            sys.exit(2)

        files = {}
        for hunk in hunks:
            if isinstance(hunk, (UpdateFile, DeleteFile)):
                if os.path.exists(hunk.path):
                    with open(hunk.path, "r", encoding="utf-8") as f:
                        files[hunk.path] = f.read()
                else:
                    warn(f"File not found (skipped in memory): {hunk.path}", filepaths=[hunk.path])

        try:
            result = apply_patch_in_memory(patch_content, files)
        except ApplyPatchError as e:
            color_print("Error: ", Colors.RED, file=sys.stderr, end="")
            all_paths = [patch_file] + list(files.keys())
            message = colorize_files(f"In memory: {e}", all_paths)
            print(message, file=sys.stderr)
            sys.exit(2)

        success("Memory test result:")
        if result.added:
            success("  Added:")
            for p in result.added:
                color_print(f"    {p}", Colors.CYAN)
        if result.modified:
            success("  Modified:")
            for p in result.modified:
                color_print(f"    {p}", Colors.CYAN)
        if result.deleted:
            success("  Deleted:")
            for p in result.deleted:
                color_print(f"    {p}", Colors.CYAN)

        if flags.get("--show", False):
            info("\nFiles in memory after patch:")
            for path, content in result.files.items():
                color_print(f"  {path}", Colors.CYAN)
                for line in content.split("\n"):
                    if line:
                        print(f"    {line}")

        sys.exit(0)

    if flags["--undo-all"]:
        undo_all_files()
        sys.exit(0)
    if flags["--undo"]:
        if not positional:
            error("Usage: python3 pyed-patcher.py --undo <file>")
            sys.exit(1)
        for f in positional:
            undo_file(f)
        sys.exit(0)

    patch_files = []
    if positional:
        patch_files = positional
    elif not sys.stdin.isatty():
        patch_content = sys.stdin.read()
        info("Patch: stdin")

        if flags["--save"]:
            dest = save_path if save_path else f"patch-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
            try:
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(patch_content)
                success(f"Saved: {dest} ✓")
            except OSError as e:
                error(f"Save failed: {e}")
                sys.exit(1)
            sys.exit(0)

        success_all = apply_single_patch(patch_content, flags, only_files, variables, "stdin")
        sys.exit(0 if success_all else 2)
    else:
        print_usage()
        sys.exit(1)

    total = len(patch_files)
    success_count = 0
    for idx, patch_file in enumerate(patch_files):
        if total > 1:
            info(f"\n{'=' * 50}")
            info(f"Patch {idx + 1}/{total}: ", end="")
            color_print(patch_file, Colors.CYAN, file=sys.stderr)
            info(f"{'=' * 50}")

        try:
            with open(patch_file, "r", encoding="utf-8") as f:
                patch_content = f.read()
            info("Patch file: ", end="")
            color_print(patch_file, Colors.CYAN, file=sys.stderr)
        except FileNotFoundError:
            error(f"File not found: {patch_file}", filepaths=[patch_file])
            continue
        except Exception as e:
            error(f"Cannot read: {patch_file} — {e}", filepaths=[patch_file])
            continue

        if apply_single_patch(patch_content, flags, only_files, variables, patch_file):
            success_count += 1
        else:
            if total > 1:
                warn(f"Continuing with next patch...")

    if total > 1:
        info(f"\n{'=' * 50}")
        if success_count == total:
            success(f"All {total} patches applied ✓")
        else:
            warn(f"Applied {success_count}/{total} ({total - success_count} failed)")

    sys.exit(0 if success_count == total else 2)


if __name__ == "__main__":
    main()
