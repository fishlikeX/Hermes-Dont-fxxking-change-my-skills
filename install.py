"""skill-guard installer (manual / clone-based path).

Preferred install is the official CLI:

    hermes plugins install fishlikeX/Hermes-Dont-fxxking-change-my-skills --enable

Reach for this script only when you want a manual clone-based install. It:
  1) copies the plugin files into $HERMES_HOME/plugins/dont-change-my-skills/
  2) copies the Desktop half into $HERMES_HOME/desktop-plugins/ (optional surface)
  3) adds the plugin name to plugins.enabled in config.yaml
     (idempotent, preserves the file's newline style, changes nothing else)

No network access. Touches only the two install paths and config.yaml.
"""
import os
import shutil
import sys
from pathlib import Path

NAME = "dont-change-my-skills"
SRC = Path(__file__).resolve().parent
FILES = ["plugin.yaml", "__init__.py",
         "dashboard/manifest.json", "dashboard/plugin_api.py"]
CRLF = "\r\n"
LF = "\n"
BOM = b"\xef\xbb\xbf"


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            sys.exit("LOCALAPPDATA is unset; set HERMES_HOME explicitly")
        return Path(local) / "hermes"
    return Path.home() / ".hermes"


def copy_tree(dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    for rel in FILES:
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SRC / rel, dst / rel)
    print("copied -> " + str(dst))


def copy_desktop(root: Path) -> None:
    """The Desktop UI half is optional; the backend guard works fully without it."""
    src = SRC / "desktop" / "plugin.js"
    if not src.is_file():
        print("desktop half not found in source; skipped (guard unaffected)")
        return
    dst_dir = root / "desktop-plugins" / NAME
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_dir / "plugin.js")
    print("desktop panel -> " + str(dst_dir / "plugin.js"))


def _is_list_entry(line, indent):
    stripped = line.strip()
    return line.startswith(indent + "- ") and stripped[2:].strip() == NAME


def enable_in_config(cfg: Path) -> None:
    raw = cfg.read_bytes()
    if raw[:3] == BOM:
        sys.exit("config.yaml carries a BOM; refusing to rewrite it")
    text = raw.decode("utf-8")
    nl = CRLF if CRLF in text else LF
    lines = text.split(nl)

    # already enabled? (any indentation level)
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") and stripped[2:].strip() == NAME:
            print("config: already enabled")
            return

    # locate the plugins: block, then its enabled: list
    plugins_at = None
    for i, line in enumerate(lines):
        if line.rstrip() == "plugins:":
            plugins_at = i
            break
    if plugins_at is None:
        sys.exit("no `plugins:` block in config.yaml; run `hermes plugins enable` instead")
    end = plugins_at + 1
    while end < len(lines) and (not lines[end].strip() or lines[end].startswith(" ")):
        end += 1

    enabled_at = None
    for i in range(plugins_at + 1, end):
        if lines[i].rstrip() == "  enabled:":
            enabled_at = i
            break

    entry = "    - " + NAME
    if enabled_at is None:
        lines[plugins_at + 1:plugins_at + 1] = ["  enabled:", entry]
    else:
        lines.insert(enabled_at + 1, entry)

    staged = nl.join(lines)
    check = staged.split(nl)
    if not any(_is_list_entry(l, "    ") or (l.strip().startswith("- ") and l.strip()[2:].strip() == NAME)
               for l in check):
        sys.exit("internal error: entry missing after rewrite (nothing was written)")
    if sum(1 for l in check if l.strip() == "- " + NAME) != 1:
        sys.exit("internal error: duplicate entry (nothing was written)")

    tmp = cfg.with_suffix(".yaml.tmp")
    tmp.write_bytes(staged.encode("utf-8"))
    back = tmp.read_bytes().decode("utf-8")
    if sum(1 for l in back.split(nl) if l.strip() == "- " + NAME) != 1:
        sys.exit("internal error: staged file on disk is wrong (nothing was written)")
    os.replace(tmp, cfg)
    print("config: enabled")


def main() -> None:
    root = hermes_home()
    cfg = root / "config.yaml"
    if not cfg.is_file():
        sys.exit("config.yaml not found at " + str(cfg) + " - is Hermes installed here?")
    copy_tree(root / "plugins" / NAME)
    copy_desktop(root)
    enable_in_config(cfg)
    print("done. Restart the gateway (or reload plugins) to activate the guard.")


if __name__ == "__main__":
    main()
