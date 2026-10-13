import ast
from pathlib import Path

ROOT = Path(r"D:\IMVU-Music-Bot")

YT = ROOT / "music" / "youtube_owned.py"
RADIO = ROOT / "radio_server" / "server.py"


def read_source(path):
    # utf-8-sig transparently removes a UTF-8 BOM if present.
    return path.read_text(encoding="utf-8-sig")


def is_subprocess_call(node, method):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        and node.func.attr == method
    )


def patch_calls(path, method, expected):
    text = read_source(path)

    tree = ast.parse(
        text,
        filename=str(path),
    )

    calls = [
        node
        for node in ast.walk(tree)
        if is_subprocess_call(node, method)
    ]

    calls.sort(key=lambda node: node.lineno)

    print()
    print(f"{path.name}")
    print(f"subprocess.{method} calls:")

    for node in calls:
        print(f"  line {node.lineno}")

    if len(calls) != expected:
        raise RuntimeError(
            f"{path.name}: expected {expected} "
            f"subprocess.{method} calls but found {len(calls)}"
        )

    lines = text.splitlines(keepends=True)

    # Bottom-up insertion preserves AST line positions.
    for node in reversed(calls):

        if any(
            keyword.arg == "creationflags"
            for keyword in node.keywords
        ):
            print(
                f"  line {node.lineno}: "
                "creationflags already exists"
            )
            continue

        closing_index = node.end_lineno - 1

        closing_line = lines[closing_index]

        closing_indent = (
            closing_line[
                :len(closing_line) - len(closing_line.lstrip())
            ]
        )

        argument_indent = closing_indent + "    "

        insertion = (
            argument_indent
            + "creationflags=(\n"
            + argument_indent
            + "    subprocess.CREATE_NO_WINDOW\n"
            + argument_indent
            + '    if hasattr(subprocess, "CREATE_NO_WINDOW")\n'
            + argument_indent
            + "    else 0\n"
            + argument_indent
            + "),\n"
        )

        lines.insert(
            closing_index,
            insertion,
        )

        print(
            f"  line {node.lineno}: "
            "CREATE_NO_WINDOW added"
        )

    patched = "".join(lines)

    # Validate BEFORE writing.
    ast.parse(
        patched,
        filename=str(path),
    )

    # Save as normal UTF-8 without BOM.
    path.write_text(
        patched,
        encoding="utf-8",
        newline="\n",
    )


# ============================================================
# yt-dlp
# Exactly three subprocess.run calls:
#   search
#   resolve/metadata
#   download
# ============================================================

patch_calls(
    YT,
    "run",
    3,
)


# ============================================================
# Radio
# Exactly one subprocess.Popen:
#   persistent FFmpeg broadcaster
# ============================================================

patch_calls(
    RADIO,
    "Popen",
    1,
)


print()
print("[OK] Console suppression patch completed.")
