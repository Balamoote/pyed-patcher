# Pyed-Patcher

A CLI tool for applying patches using a custom patch format designed for AI coding assistants.

This project's idea is based on
[Codex Apply Patch](https://socket.dev/pypi/package/codex-apply-patch) 
which is a rewrite of OpenAI's original 
[codex apply-patch tool](https://github.com/openai/codex/tree/main/scripts/apply_patch.py).

This tool may contain errors, check the results and always keep backups. Use at your own risk.

For AI instructions and some more info see [INSTRUCTIONS.en.md](INSTRUCTIONS.en.md).

## Core Features

- Apply patches with `*** Add File`, `*** Delete File`, `*** Update File` operations
- File move/rename support (`*** Move to:`)
- Context-based change chunks with `@@` markers
- End-of-file marker support (`*** End of File`)
- Flexible line matching (exact, trimmed, Unicode normalization)
- Detailed error messages with line numbers
- Reading patches from file or stdin

## Additional Features

- Pure Python 3 implementation (no external dependencies)
- Colored terminal output (green for info, red for errors, yellow for warnings, 
  cyan for file names)
- Patch comments support (`*** Comment:`)
- Automatic backups with incremental numbering (`.01`, `.02`, ...)
- Undo functionality (`--undo`, `--undo-all`)
- Dry-run mode (`--dry-run`)
- Interactive mode (`--int`)
- Patch validation (`--val`)
- Diff preview (`--show`)
- File filtering (`--only`)
- Save patch from stdin (`--save`)
- Template variables with defaults (`--var`, `{{VAR}}`, `{{VAR:default}}`)
- Multiple patches in a single run
- In-memory patch application (`--memory`)
- Patch generation from two files (`--generate`)
- Parse patch structure (`--parse`)
- Action logging to `.pyed-patcher.log`

## Usage

```bash
# Apply patch from file
python3 pyed-patcher.py patch.txt

# Apply patch from stdin
echo '*** Begin Patch
*** Add File: hello.py
+print("Hello!")
*** End Patch' | python3 pyed-patcher.py

# Multiple patches
python3 pyed-patcher.py patch1.txt patch2.txt patch3.txt
```

## CLI Flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview changes without applying |
| `--undo` | Interactively restore files from available LOGGED backups |
| `--undo [FILE]` | Restore file from latest backup of FILE |
| `--undo-all` | Restore all files with backups |
| `--cleanup` | Delete all backups found in the log")
| `--cleanup [FILE]` | Delete backups of a FILE found in the log")
| `--cleanlog` | Remove log entries that reference missing backups")
| `--dellog` | Delete the log file")
| `--only FILES...` | Apply patch only to specified files |
| `--int` | Interactive mode (confirm each change) |
| `--val` | Validate patch without applying |
| `--show` | Show diff of changes |
| `--save [FILE]` | Save patch from stdin to file |
| `--var KEY=VALUE` | Substitute value into `{{KEY}}` template |
| `--parse` | Show patch structure and comments |
| `--generate ORIG NEW [--as PATH]` | Generate patch from two files |
| `--memory` | Apply patch in memory (test mode) |
| `--help, -h` | Show help |
| `--version` | Show version |

## Quick Examples

```bash
# Preview before applying
python3 pyed-patcher.py --dry-run patch.txt

# Interactive apply
python3 pyed-patcher.py --int patch.txt

# Apply only to specific files
python3 pyed-patcher.py --only src/main.py patch.txt

# Use templates
python3 pyed-patcher.py --var VERSION=2.0.0 release.patch

# Test in memory
python3 pyed-patcher.py --memory --show patch.txt

# Generate patch from two files
python3 pyed-patcher.py --generate old.py new.py --as src/main.py > changes.patch

# Rollback
python3 pyed-patcher.py --undo src/main.py
python3 pyed-patcher.py --undo-all
```

## Python API

```python
import pyed_patcher

# Apply patch in memory
files = {"main.py": "old content\n"}
patch = "*** Begin Patch\n*** Update File: main.py\n@@\n-old content\n+new content\n*** End Patch"
result = pyed_patcher.apply_patch_in_memory(patch, files)
print(result.files)      # {'main.py': 'new content\n'}
print(result.modified)   # ['main.py']

# Generate patch
patch = pyed_patcher.generate_patch("main.py", "old\n", "new\n")
print(patch)

# Generate patch for multiple files
patch = pyed_patcher.generate_patch_from_files({
    "new.py": (None, "print('hello')\n"),
    "old.py": ("content\n", None),
    "update.py": ("old\n", "new\n"),
})

# Parse patch info
descriptions, comments = pyed_patcher.parse_patch_info(patch)
```

## License

Licensed under the Apache License, Version 2.0, as both of the source projects 
are licensed under the same license.
