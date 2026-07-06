#!/usr/bin/env python3
"""Sample -> real config merge for the LIDALDI installer (T10).

Treats config.toml.sample / .env.sample as the schema. Keys present in the
sample but missing from the live file are ADDED (with the sample's raw line,
comments preserved); existing live values are NEVER overwritten. Keys present
in the live file but absent from the sample are reported for manual review.

Stdlib only; requires Python >= 3.12 (decision D3).

Usage:
    merge_config.py --mode toml --sample config.toml.sample --live config.toml
    merge_config.py --mode env  --sample .env.sample        --live .env
    Add --dry-run to print planned changes without writing.

Exit codes: 0 = no changes needed, 3 = changes needed/applied, 2 = error.
"""

import argparse
import os
import re
import sys
import tempfile

if sys.version_info < (3, 12):
    sys.exit(
        "merge_config.py requires Python >= 3.12 (decision "
        "D3); found %s." % ".".join(str(p) for p in sys.version_info[:3])
    )

import tomllib  # noqa: E402

_SECTION_RE = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*(#.*)?$")
_TOML_KEY_RE = re.compile(r"^\s*(?P<key>[A-Za-z0-9_-]+|\"[^\"]+\")\s*=")
_ENV_KEY_RE = re.compile(r"^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)=")

# Keys that look like secrets and must not live in TOML (T9 verifier
# follow-up: cover more than the Telegram keys, at any nesting depth).
_SECRETY = re.compile(
    r"(token|secret|password|passwd|api_key|apikey|private_key)", re.I
)


def _flatten(table, prefix=""):
    out = {}
    for key, value in table.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(_flatten(value, f"{dotted}."))
        else:
            out[dotted] = value
    return out


def _toml_sections(text):
    """Map section name -> list of (key, raw_line) of top-level keys."""
    sections = {"": []}
    current = ""
    for line in text.splitlines():
        m = _SECTION_RE.match(line)
        if m:
            current = m.group("name").strip()
            sections.setdefault(current, [])
            continue
        k = _TOML_KEY_RE.match(line)
        if k:
            key = k.group("key").strip('"')
            sections[current].append((key, line))
    return sections


def _commented_toml_keys(text):
    """Set of dotted keys shown as commented optional fields in the sample."""
    known = set()
    current = ""
    for line in text.splitlines():
        m = _SECTION_RE.match(line)
        if m:
            current = m.group("name").strip()
            continue
        k = re.match(r"^\s*#\s*(?P<key>[A-Za-z0-9_-]+|\"[^\"]+\")\s*=", line)
        if k:
            key = k.group("key").strip('"')
            known.add(f"{current}.{key}" if current else key)
    return known


def _write_atomic(path, text):
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".merge_config.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            st = os.stat(path)
            os.chmod(tmp, st.st_mode & 0o777)
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def merge_toml(sample_path, live_path, dry_run):
    with open(sample_path, "rb") as fh:
        sample = tomllib.load(fh)
    with open(live_path, "rb") as fh:
        live = tomllib.load(fh)

    sample_flat = _flatten(sample)
    live_flat = _flatten(live)
    with open(sample_path, encoding="utf-8") as fh:
        sample_text = fh.read()
    sample_known = set(sample_flat) | _commented_toml_keys(sample_text)

    for dotted in sorted(live_flat):
        leaf = dotted.rsplit(".", 1)[-1]
        if _SECRETY.search(leaf):
            print(f"WARN secret-looking key in TOML (move to .env): {dotted}")

    for dotted in sorted(set(live_flat) - sample_known):
        print(f"REVIEW live key absent from sample (removed/renamed?): {dotted}")

    missing = sorted(set(sample_flat) - set(live_flat))
    if not missing:
        return 0

    with open(live_path, encoding="utf-8") as fh:
        live_text = fh.read()

    sample_sections = _toml_sections(sample_text)
    # section -> [(key, raw_line)] to add, in sample order
    to_add = {}
    for dotted in missing:
        if "." in dotted:
            section, key = dotted.rsplit(".", 1)
        else:
            section, key = "", dotted
        for k, raw in sample_sections.get(section, []):
            if k == key:
                to_add.setdefault(section, []).append((key, raw))
                print(f"ADD [{section}] {key} = (sample default)")
                break
        else:
            print(f"WARN cannot locate sample line for {dotted}; skipped")

    if not to_add:
        return 0
    if dry_run:
        return 3

    lines = live_text.splitlines()
    live_section_names = []
    for line in lines:
        m = _SECTION_RE.match(line)
        if m:
            live_section_names.append(m.group("name").strip())

    out = []
    current = ""

    def _flush(section):
        for _key, raw in to_add.pop(section, []):
            out.append(raw)

    for line in lines:
        m = _SECTION_RE.match(line)
        if m:
            _flush(current)
            current = m.group("name").strip()
        out.append(line)
    _flush(current)
    for section in list(to_add):
        out.append("")
        out.append(f"[{section}]")
        _flush(section)

    _write_atomic(live_path, "\n".join(out) + "\n")
    return 3


def _env_keys(text, include_commented=False):
    keys = {}
    for line in text.splitlines():
        candidate = line
        if include_commented:
            candidate = re.sub(r"^\s*#\s*", "", line, count=1)
        m = _ENV_KEY_RE.match(candidate)
        if m:
            keys[m.group("key")] = line
    return keys


def merge_env(sample_path, live_path, dry_run):
    with open(sample_path, encoding="utf-8") as fh:
        sample_text = fh.read()
    with open(live_path, encoding="utf-8") as fh:
        live_text = fh.read()

    sample_keys = _env_keys(sample_text)
    sample_known = set(_env_keys(sample_text, include_commented=True))
    live_keys = _env_keys(live_text)

    for key in sorted(set(live_keys) - sample_known):
        print(f"REVIEW live key absent from sample (removed/renamed?): {key}")

    missing = [k for k in sample_keys if k not in live_keys]
    if not missing:
        return 0
    for key in missing:
        print(f"ADD {key} = (sample default)")
    if dry_run:
        return 3

    out = live_text
    if out and not out.endswith("\n"):
        out += "\n"
    for key in missing:
        out += sample_keys[key] + "\n"
    _write_atomic(live_path, out)
    return 3


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("toml", "env"), required=True)
    parser.add_argument("--sample", required=True)
    parser.add_argument("--live", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    for path in (args.sample, args.live):
        if not os.path.isfile(path):
            print(f"ERROR no such file: {path}", file=sys.stderr)
            return 2
    try:
        if args.mode == "toml":
            return merge_toml(args.sample, args.live, args.dry_run)
        return merge_env(args.sample, args.live, args.dry_run)
    except tomllib.TOMLDecodeError as exc:
        print(f"ERROR invalid TOML: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
