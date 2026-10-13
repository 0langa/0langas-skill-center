#!/usr/bin/env python3
"""skillctl - deterministic cross-provider skill management CLI.

Stdlib-only. Windows-aware. Reads registry/skills.json as the source of truth
and reconciles the skill scan directories of Codex, Kimi Code, Claude Code and
VS Code Copilot against it.

Subcommands: audit, sync, verify, update, archive, register, discover,
unregister, snapshot, plugins.

Hard rules enforced here:
- NEVER hard-delete anything; removals are moves into _archive/<YYYYMMDD>/.
- Never touch ~/.claude/plugins, ~/.kimi-code/plugins, ~/.codex, home-dir
  config files, or anything outside provider scan dirs + the repo _archive.
- Print every planned/performed action. Identical inputs -> identical plan.

Set SKILLCTL_HOME to make "~" mean another directory, e.g. a throwaway one
for tests and CI. Nothing then reads or writes the real home directory.
"""

import argparse
import contextlib
import datetime
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "registry" / "skills.json"
UPSTREAM_CACHE_PATH = REPO_ROOT / "registry" / ".upstream-cache.json"
ARCHIVE_ROOT = REPO_ROOT / "_archive"
ARCHIVE_LOG = ARCHIVE_ROOT / "LOG.md"


def home_dir():
    """The home directory whose provider scan dirs skillctl manages.

    SKILLCTL_HOME overrides it, so tests and CI can install into a throwaway
    directory instead of the real ~/.agents, ~/.claude and ~/.kimi-code.
    """
    override = os.environ.get("SKILLCTL_HOME")
    if override:
        return os.path.normpath(os.path.abspath(override))
    return os.path.normpath(os.path.expanduser("~"))


def expand_home(path):
    """os.path.expanduser() that honours SKILLCTL_HOME; returns a normpath."""
    p = str(path)
    if p == "~" or p.startswith(("~/", "~\\")):
        return os.path.normpath(os.path.join(home_dir(), p[2:]))
    return os.path.normpath(os.path.expanduser(p))


AGENTS_DIR = expand_home("~/.agents/skills")
KIMI_DIR = expand_home("~/.kimi-code/skills")
CLAUDE_PLUGINS_JSON = expand_home("~/.claude/plugins/installed_plugins.json")

# Provenance. The repo is a personal skill collection: only skills authored
# here may live inside it. Third-party skills are tracked by the registry but
# always stay outside the repo, under a provider directory or their own repo.
#   mine     - authored by the repo owner; may use canonical type "repo"
#   vendored - written by someone else; must live outside this repo
#   unknown  - authorship not yet established; treated as "not mine"
ORIGINS = ("mine", "vendored", "unknown")
FOREIGN_ORIGINS = ("vendored", "unknown")

# install-value bases (relative skill location inside a provider-visible tree)
BASE_INSTALLS = {
    "agents": AGENTS_DIR,
    "agents/skills": os.path.join(AGENTS_DIR, "skills"),
    "kimi": KIMI_DIR,
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def norm(p):
    """Normalize a path for comparison (Windows case-insensitive)."""
    return os.path.normcase(os.path.normpath(str(p)))


def is_link(path):
    """True if `path` itself is a junction or symlink, dangling or not.

    Reads the entry's own reparse tag (os.path.islink misses junctions).
    Comparing realpath() with abspath() instead also fires for real
    directories under a linked or 8.3-spelled parent (C:\\Users\\RUNNER~1 on
    CI runners), which made every entry under such a home look like a link.
    """
    try:
        st = os.lstat(path)
    except (OSError, ValueError):
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    return getattr(st, "st_reparse_tag", 0) == stat.IO_REPARSE_TAG_MOUNT_POINT


def resolved(path):
    """Normalized realpath: the spelling to compare link targets in."""
    return norm(os.path.realpath(path))


def link_target(path):
    return resolved(path)


_resolved_canonicals = {}


def canonical_target(skill):
    """resolved() of a skill's canonical directory, cached for this run.

    A link target is fully resolved, so it must be compared with the resolved
    canonical: when ~ or the repo is reached through a link or an 8.3 name,
    the plain canonical path never matches and every sync relinks again.
    """
    canon = canonical_path(skill)
    if canon not in _resolved_canonicals:
        _resolved_canonicals[canon] = resolved(canon)
    return _resolved_canonicals[canon]


def parse_frontmatter(skill_md):
    """Return dict with 'name', 'description', 'error' keys."""
    try:
        # utf-8-sig: tolerate a BOM — many Windows editors emit one
        text = Path(skill_md).read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        return {"name": None, "description": None, "error": f"unreadable: {exc}"}
    m = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", text, re.S)
    if not m:
        return {"name": None, "description": None, "error": "no YAML frontmatter block"}
    fields = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        mm = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", lines[i])
        if mm:
            val = mm.group(2).strip()
            if val in ("", ">", "|", ">-", "|-"):
                # YAML folded/literal block or empty value: join indented continuation lines
                cont = []
                j = i + 1
                while j < len(lines) and (lines[j].startswith(" ") or lines[j].startswith("\t")):
                    cont.append(lines[j].strip())
                    j += 1
                if cont:
                    val = " ".join(c for c in cont if c)
                    i = j - 1
            fields[mm.group(1)] = val.strip('"').strip("'")
        i += 1
    err = None
    if not fields.get("name"):
        err = "frontmatter missing 'name'"
    elif not fields.get("description"):
        err = "frontmatter missing 'description'"
    return {"name": fields.get("name"), "description": fields.get("description"), "error": err}


def dir_hash(path):
    """Deterministic content hash of a directory tree."""
    h = hashlib.sha256()
    for root, dirs, files in os.walk(path):
        dirs.sort()
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, path).replace(os.sep, "/")
            h.update(rel.encode("utf-8"))
            try:
                with open(fp, "rb") as f:
                    h.update(f.read())
            except OSError:
                h.update(b"<unreadable>")
    return h.hexdigest()


def today_stamp():
    return datetime.datetime.now().strftime("%Y%m%d")


def load_registry():
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def skill_dir_name(skill):
    return skill.get("dir", skill["name"])


def skill_origin(skill):
    return skill.get("origin", "unknown")


def check_origin_invariants(registry):
    """Provenance rules. Returns (failures, unknowns).

    The hard rule: a skill the owner did not write never lives inside this
    repo. Enforced here rather than by convention, because `update --apply`
    and `register` both write to a skill's canonical path.
    """
    failures, unknowns = [], []
    for skill in registry.get("skills", []):
        name = skill.get("name", "<unnamed>")
        origin = skill.get("origin")
        if origin is None:
            failures.append(f"'{name}': missing 'origin' (one of {', '.join(ORIGINS)})")
            continue
        if origin not in ORIGINS:
            failures.append(f"'{name}': invalid origin '{origin}' "
                            f"(expected one of {', '.join(ORIGINS)})")
            continue
        if origin in FOREIGN_ORIGINS:
            if (skill.get("canonical") or {}).get("type") == "repo":
                failures.append(
                    f"'{name}': origin '{origin}' but canonical type is 'repo' - "
                    f"only skills with origin 'mine' may live inside this repo")
            if origin == "unknown":
                unknowns.append(name)
    return failures, unknowns


def canonical_path(skill, repo_root=REPO_ROOT):
    c = skill["canonical"]
    if c["type"] == "repo":
        return os.path.normpath(str(repo_root / c["path"]))
    return expand_home(c["path"])


def expected_locations(skill, provider):
    """List of absolute paths where this skill must appear for the provider."""
    inst = skill["install"].get(provider, "none")
    d = skill_dir_name(skill)
    if inst in BASE_INSTALLS:
        return [os.path.join(BASE_INSTALLS[inst], d)]
    if inst.startswith("junction:"):
        return [expand_home(inst.split(":", 1)[1])]
    if inst.startswith("path:"):
        # canonical lives directly at this provider-visible location
        return [expand_home(inst.split(":", 1)[1])]
    return []


def scan_provider_dirs(registry):
    """Scan every provider scan dir.

    Returns {provider: [entry, ...]} where entry = {
      'path', 'name' (dir entry name), 'real', 'is_link', 'fm' (or None),
      'container_child' (bool)}
    """
    containers = {norm(expand_home(c)) for c in registry.get("containers", {})}
    out = {}
    for provider, pconf in registry["providers"].items():
        entries = []
        for scan in pconf["scan"]:
            base = expand_home(scan)
            if not os.path.isdir(base):
                continue
            for name in sorted(os.listdir(base)):
                p = os.path.join(base, name)
                if norm(p) in containers and os.path.isdir(p) and not is_link(p):
                    # declared container: scan one level deeper
                    for sub in sorted(os.listdir(p)):
                        sp = os.path.join(p, sub)
                        if os.path.isdir(sp):
                            entries.append(make_entry(sp, sub, container_child=True))
                    continue
                entries.append(make_entry(p, name, container_child=False))
        out[provider] = entries
    return out


def make_entry(path, name, container_child):
    e = {
        "path": path,
        "name": name,
        "real": link_target(path),
        "is_link": is_link(path),
        "container_child": container_child,
        "fm": None,
        "is_dir": os.path.isdir(path),
    }
    # A link whose target no longer exists: isdir() is False, but this is a
    # repairable broken link, not a stray file. Callers must not archive it
    # blindly - the registry-side repair pass relinks it.
    e["dangling"] = e["is_link"] and not os.path.exists(path)
    sk = os.path.join(path, "SKILL.md")
    if e["is_dir"] and os.path.isfile(sk):
        e["fm"] = parse_frontmatter(sk)
    return e


def match_skill(registry, entry, provider):
    """Return the registry skill this scan entry belongs to, or None."""
    ep = norm(entry["path"])
    er = entry["real"]
    for skill in registry["skills"]:
        for loc in expected_locations(skill, provider):
            if norm(loc) == ep:
                return skill
        if er == canonical_target(skill):
            return skill
    return None


def archive_move(src, reason, dest_name=None, apply=False):
    """Move src into _archive/<YYYYMMDD>/<dest_name or basename> and log it."""
    dest_dir = ARCHIVE_ROOT / today_stamp()
    name = dest_name or os.path.basename(src.rstrip(os.sep))
    dest = dest_dir / name
    i = 2
    while dest.exists():
        dest = dest_dir / f"{name}-{i}"
        i += 1
    if apply:
        dest_dir.mkdir(parents=True, exist_ok=True)
        if is_link(src) and not os.path.exists(src):
            # dangling junction/symlink: target is gone; move the link itself
            os.rename(src, str(dest))
        else:
            shutil.move(src, str(dest))
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        ARCHIVE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ARCHIVE_LOG, "a", encoding="utf-8") as f:
            f.write(f"- {ts} | `{src}` -> `_archive/{today_stamp()}/{dest.name}` | {reason}\n")
    return str(dest)


def remove_link(path, apply=False):
    """Remove a junction/symlink itself (never the target).

    Tolerates a dangling link (target gone) and an already-absent path, so a
    relink of a broken junction cannot fail before it recreates the link.
    """
    if not apply:
        return
    path = os.path.normpath(path)
    if not os.path.lexists(path):
        return
    r = subprocess.run(["cmd", "/c", "rmdir", path], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if r.returncode == 0 or not os.path.lexists(path):
        return
    # rmdir refuses some reparse points; remove the link entry directly.
    for fn in (os.remove, os.rmdir):
        try:
            fn(path)
            return
        except OSError:
            continue
    raise RuntimeError(f"could not remove link {path}: {r.stdout} {r.stderr}")


def make_junction(link, target, apply=False):
    if apply:
        link, target = os.path.normpath(link), os.path.normpath(target)
        os.makedirs(os.path.dirname(link), exist_ok=True)
        r = subprocess.run(["cmd", "/c", "mklink", "/J", link, target],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError(f"mklink failed for {link}: {r.stdout} {r.stderr}")


# --------------------------------------------------------------------------
# audit
# --------------------------------------------------------------------------

def cmd_audit(_args):
    registry = load_registry()
    scan = scan_provider_dirs(registry)
    problems = {k: [] for k in
                ("missing", "broken", "stray", "duplicate", "junction",
                 "provenance", "validation", "unexpected")}
    warnings = []

    origin_failures, origin_unknowns = check_origin_invariants(registry)
    problems["provenance"].extend(origin_failures)
    if origin_unknowns:
        warnings.append(
            f"[registry] {len(origin_unknowns)} skill(s) with origin 'unknown' - "
            f"set each to 'mine' or 'vendored' so provenance is explicit: "
            + ", ".join(origin_unknowns))

    # 1. scan-dir findings
    for provider, entries in scan.items():
        by_fm = {}
        for e in entries:
            skill = match_skill(registry, e, provider)
            if e["dangling"]:
                owner = f"'{skill['name']}'" if skill else "no registry owner"
                problems["broken"].append(
                    f"[{provider}] dead link {e['path']} -> {os.path.realpath(e['path'])} ({owner})")
                continue
            if not e["is_dir"]:
                problems["stray"].append(f"[{provider}] non-skill file in scan dir: {e['path']}")
                continue
            if e["fm"] is None:
                if skill and skill.get("bundle"):
                    continue  # bundle container (e.g. usage-pulse), declared
                problems["stray"].append(
                    f"[{provider}] directory without SKILL.md, not in registry: {e['path']}")
                continue
            if e["fm"]["error"]:
                problems["validation"].append(f"[{provider}] {e['path']}: {e['fm']['error']}")
            fm_name = e["fm"]["name"] or e["name"]
            by_fm.setdefault(fm_name, []).append(e)
            if skill is None:
                problems["stray"].append(
                    f"[{provider}] skill '{fm_name}' at {e['path']} is not in the registry")
            else:
                reg_name = skill["name"]
                if fm_name != reg_name:
                    problems["validation"].append(
                        f"[{provider}] {e['path']}: frontmatter name '{fm_name}' "
                        f"!= registry name '{reg_name}'")
                if fm_name != e["name"]:
                    warnings.append(
                        f"[{provider}] {e['path']}: frontmatter name '{fm_name}' "
                        f"!= directory name '{e['name']}'")
        for fm_name, es in sorted(by_fm.items()):
            reals = {e["real"] for e in es}
            if len(es) > 1 and len(reals) > 1:
                locs = ", ".join(e["path"] for e in es)
                problems["duplicate"].append(
                    f"[{provider}] name '{fm_name}' visible {len(es)}x with different targets: {locs}")

    # 2. registry-side findings
    for skill in registry["skills"]:
        canon = canonical_path(skill)
        for provider in registry["providers"]:
            inst = skill["install"].get(provider, "none")
            if inst in BASE_INSTALLS:
                loc = expected_locations(skill, provider)[0]
                sk = os.path.join(loc, "SKILL.md")
                if not os.path.isfile(sk):
                    problems["missing"].append(
                        f"[{provider}] '{skill['name']}' required at {loc} ({inst}) but no SKILL.md there")
            elif inst.startswith("junction:"):
                loc = expected_locations(skill, provider)[0]
                if not os.path.isdir(loc) and not is_link(loc):
                    problems["junction"].append(
                        f"[{provider}] '{skill['name']}': junction missing at {loc}")
                elif not is_link(loc):
                    problems["junction"].append(
                        f"[{provider}] '{skill['name']}': {loc} is a real directory, "
                        f"expected junction -> {canon}")
                elif link_target(loc) != canonical_target(skill):
                    problems["junction"].append(
                        f"[{provider}] '{skill['name']}': junction {loc} targets "
                        f"{os.path.realpath(loc)}, expected {canon}")
                elif not os.path.exists(loc):
                    problems["junction"].append(
                        f"[{provider}] '{skill['name']}': junction {loc} points at "
                        f"{canon}, which does not exist (stale registry canonical?)")
            elif inst == "inherit":
                visible = any(
                    match_skill(registry, e, provider) is skill
                    for e in scan.get(provider, []) if e["is_dir"])
                if not visible:
                    problems["missing"].append(
                        f"[{provider}] '{skill['name']}' (inherit) not visible in any scan dir")
            elif inst == "none":
                for e in scan.get(provider, []):
                    if e["is_dir"] and match_skill(registry, e, provider) is skill:
                        problems["unexpected"].append(
                            f"[{provider}] '{skill['name']}' marked 'none' but visible at {e['path']}")
            # plugin: verify-only, handled in verify

    # report
    print("skillctl audit")
    print("=" * 60)
    for cls, items in problems.items():
        print(f"{cls.upper()} ({len(items)})")
        for it in items:
            print(f"  - {it}")
    print(f"WARNINGS ({len(warnings)})")
    for w in warnings:
        print(f"  - {w}")
    print("-" * 60)
    print("per-provider summary:")
    for provider, entries in scan.items():
        skills_seen = sum(1 for e in entries if e["fm"] is not None)
        print(f"  {provider:7} entries={len(entries):3} skills_with_SKILL.md={skills_seen:3}")
    bad = sum(len(v) for v in problems.values())
    print(f"total problems: {bad}, warnings: {len(warnings)}")
    return 1 if bad else 0


# --------------------------------------------------------------------------
# sync
# --------------------------------------------------------------------------

def claimed_paths(registry):
    """Every scan-dir path the registry explicitly maps a skill onto."""
    out = set()
    for skill in registry["skills"]:
        for provider in registry["providers"]:
            for loc in expected_locations(skill, provider):
                out.add(norm(loc))
    return out


def build_plan(registry, archive_strays=False):
    """Deterministic reconciliation plan. Identical inputs -> identical plan.

    archive_strays: also archive unregistered but otherwise valid skills.
    Off by default - a valid skill that is merely absent from the registry is
    reported as 'review' so `sync --apply` can never silently remove working
    skills; use `register` to adopt them.
    """
    scan = scan_provider_dirs(registry)
    claimed = claimed_paths(registry)
    actions = []

    # strays & duplicates from scan
    archived = {}  # norm(path) -> action, so a path scanned by N providers is archived once
    def add_archive(path, provider, reason):
        key = norm(path)
        if key in archived:
            archived[key]["provider"] += f",{provider}"
            return
        a = {"op": "archive", "path": path, "provider": provider, "reason": reason}
        archived[key] = a
        actions.append(a)

    reviewed = {}  # norm(path) -> action, reported once per path

    def add_review(path, provider, reason):
        key = norm(path)
        if key in reviewed:
            reviewed[key]["provider"] += f",{provider}"
            return
        a = {"op": "review", "path": path, "provider": provider, "reason": reason}
        reviewed[key] = a
        actions.append(a)

    for provider, entries in scan.items():
        by_fm = {}
        for e in entries:
            skill = match_skill(registry, e, provider)
            if e["dangling"]:
                # Broken link. If the registry claims this path, the repair
                # pass below relinks it - archiving here would delete the link
                # out from under that repair and leave the skill invisible.
                if skill is not None or norm(e["path"]) in claimed:
                    continue
                add_archive(e["path"], provider,
                            f"dead link with no registry owner "
                            f"(-> {os.path.realpath(e['path'])})")
                continue
            if not e["is_dir"]:
                add_archive(e["path"], provider, "stray non-skill file in scan dir")
                continue
            if e["fm"] is None:
                if skill and skill.get("bundle"):
                    continue
                add_archive(e["path"], provider,
                            "stray directory without SKILL.md, not in registry")
                continue
            if skill is None:
                reason = f"stray skill '{e['fm']['name']}' not in registry"
                if archive_strays:
                    add_archive(e["path"], provider, reason)
                else:
                    add_review(e["path"], provider,
                               reason + " - run `register` to adopt it, or "
                               "`sync --archive-strays` to remove it")
            else:
                by_fm.setdefault(e["fm"]["name"] or e["name"], []).append(e)
        for _fm, es in sorted(by_fm.items()):
            reals = {e["real"] for e in es}
            if len(es) > 1 and len(reals) > 1:
                for e in es[1:]:  # keep first by scan order, archive the rest
                    add_archive(e["path"], provider,
                                "duplicate skill with conflicting target")

    # registry-side repairs
    linked = {}  # norm(link path) -> action, so a shared scan dir is repaired once
    def add_link_action(op, link, target, provider, reason):
        key = (op, norm(link))
        if key in linked:
            linked[key]["provider"] += f",{provider}"
            return
        a = {"op": op, "link": link, "target": target, "provider": provider, "reason": reason}
        linked[key] = a
        actions.append(a)

    unfixable = {}  # (skill, canonical) -> action: one line however many providers

    def add_unfixable(skill, canon, provider):
        key = (skill["name"], norm(canon))
        if key in unfixable:
            unfixable[key]["provider"] += f",{provider}"
            return
        a = {"op": "unfixable", "provider": provider,
             "reason": f"'{skill['name']}' canonical missing at {canon}"}
        unfixable[key] = a
        actions.append(a)

    for skill in registry["skills"]:
        canon = canonical_path(skill)
        for provider in registry["providers"]:
            inst = skill["install"].get(provider, "none")
            if inst in BASE_INSTALLS:
                loc = expected_locations(skill, provider)[0]
                if not os.path.isfile(os.path.join(loc, "SKILL.md")):
                    if norm(canon) != norm(loc) and os.path.isdir(canon):
                        add_link_action("junction", loc, canon, provider,
                                        f"create missing link for '{skill['name']}' ({inst})")
                    else:
                        add_unfixable(skill, canon, provider)
            elif inst.startswith("junction:"):
                loc = expected_locations(skill, provider)[0]
                if not os.path.isdir(canon):
                    # Linking to a canonical that is not there only
                    # manufactures a dead junction for audit to report.
                    add_unfixable(skill, canon, provider)
                elif not os.path.isdir(loc) and not is_link(loc):
                    add_link_action("junction", loc, canon, provider,
                                    f"create missing junction for '{skill['name']}'")
                elif not is_link(loc):
                    add_archive(loc, provider,
                                f"real directory occupies junction path for '{skill['name']}'")
                    add_link_action("junction", loc, canon, provider,
                                    f"recreate junction for '{skill['name']}'")
                elif link_target(loc) != canonical_target(skill):
                    add_link_action("relink", loc, canon, provider,
                                    f"wrong-target junction for '{skill['name']}' "
                                    f"(now -> {os.path.realpath(loc)})")
    # An archive must never target a path that a link repair is about to
    # rebuild: archiving first makes the repair fail and the skill vanish.
    repaired = {norm(a["link"]) for a in actions if a["op"] in ("junction", "relink")}
    conflicts = [a for a in actions
                 if a["op"] == "archive" and norm(a["path"]) in repaired]
    for a in conflicts:
        actions.remove(a)

    # deterministic order; repairs before archives so a plan is safe to replay
    op_rank = {"junction": 0, "relink": 1, "archive": 2, "review": 3, "unfixable": 4}
    actions.sort(key=lambda a: (op_rank.get(a["op"], 9), a["op"],
                                a.get("path") or a.get("link") or "", a["reason"],
                                a["provider"]))
    return actions


def cmd_sync(args):
    registry = load_registry()
    apply = args.apply
    actions = build_plan(registry, archive_strays=getattr(args, "archive_strays", False))
    if getattr(args, "only", None):
        reg_by_name = {s["name"]: s for s in registry["skills"]}
        sel_paths = set()
        for token in args.only:
            if token in reg_by_name:
                s = reg_by_name[token]
                sel_paths.add(norm(canonical_path(s)))
                for prov in registry["providers"]:
                    for loc in expected_locations(s, prov):
                        sel_paths.add(norm(loc))
            else:
                sel_paths.add(norm(os.path.abspath(expand_home(token))))

        def selected(a):
            where = a.get("path") or a.get("link")
            if where and norm(where) in sel_paths:
                return True
            # match registry skill names AND stray names (quoted in reasons)
            return any(f"'{t}'" in a.get("reason", "") for t in args.only)

        skipped = [a for a in actions if not selected(a)]
        actions = [a for a in actions if selected(a)]
        for a in skipped:
            where = a.get("path") or a.get("link") or ""
            print(f"  skipped (not selected): {a['op']} [{a['provider']}] {where}")
        if not actions:
            print(f"skillctl sync --only: no plan actions matched {list(args.only)}")
            return 1
    mode = "APPLY" if apply else "PLAN"
    print(f"skillctl sync ({mode}) - {len(actions)} action(s)")
    rc = 0
    for a in actions:
        where = a.get("path") or a.get("link") or ""
        print(f"  [{mode}] {a['op']:9} [{a['provider']}] {where} :: {a['reason']}")
        if not apply:
            continue
        try:
            if a["op"] == "archive":
                dest = archive_move(a["path"], a["reason"],
                                    dest_name=f"{a['provider']}-{os.path.basename(a['path'])}",
                                    apply=True)
                print(f"         archived -> {dest}")
            elif a["op"] == "junction":
                make_junction(a["link"], a["target"], apply=True)
                print(f"         junction {a['link']} -> {a['target']}")
            elif a["op"] == "relink":
                remove_link(a["link"], apply=True)
                make_junction(a["link"], a["target"], apply=True)
                print(f"         relinked {a['link']} -> {a['target']}")
            elif a["op"] == "review":
                pass  # reported only; never mutates the filesystem
            elif a["op"] == "unfixable":
                rc = 1
        except Exception as exc:  # noqa: BLE001 - report and continue
            rc = 1
            print(f"         ERROR: {exc}")
    if not actions:
        print("  nothing to do - already in sync")
    if not apply and actions:
        print("re-run with --apply to execute these actions")
    return rc


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

def cmd_verify_ci():
    """CI-safe verify: repo-local invariants only, no provider/home scan."""
    failures = []
    try:
        registry = load_registry()
    except (OSError, json.JSONDecodeError) as exc:
        print("skillctl verify --ci (repo-local checks only)")
        print(f"  FAIL: registry does not parse: {exc}")
        return 1

    names = {}
    for i, s in enumerate(registry.get("skills", [])):
        for field in ("name", "canonical", "install"):
            if field not in s:
                failures.append(f"skill #{i}: missing required field '{field}'")
        name = s.get("name")
        if not name:
            continue
        names[name] = names.get(name, 0) + 1
        canon = s.get("canonical") or {}
        if canon.get("type") == "repo":
            p = os.path.normpath(str(REPO_ROOT / canon.get("path", "")))
            sk = os.path.join(p, "SKILL.md")
            if not os.path.isfile(sk):
                failures.append(f"'{name}': repo-canonical skill missing SKILL.md at {p}")
            else:
                fm = parse_frontmatter(sk)
                if fm["error"]:
                    failures.append(f"'{name}': {sk}: {fm['error']}")
        install = s.get("install") or {}
        if any(v in BASE_INSTALLS for v in install.values()):
            cpath = canonical_path(s)
            if not os.path.isdir(cpath):
                failures.append(f"'{name}': agents-family install but canonical "
                                f"path does not exist: {cpath}")
    for n, c in sorted(names.items()):
        if c > 1:
            failures.append(f"duplicate registry name: '{n}' ({c}x)")
    origin_failures, _ = check_origin_invariants(registry)
    failures.extend(origin_failures)

    print("skillctl verify --ci (repo-local checks only)")
    for f_ in failures:
        print(f"  FAIL: {f_}")
    print(f"checked {len(registry.get('skills', []))} registry entrie(s): {len(failures)} failure(s)")
    return 1 if failures else 0


def cmd_verify(args):
    if getattr(args, "ci", False):
        return cmd_verify_ci()
    registry = load_registry()
    scan = scan_provider_dirs(registry)
    failures = []
    notes = []
    checked = 0

    for skill in registry["skills"]:
        canon = canonical_path(skill)
        bundle = bool(skill.get("bundle"))
        for provider in registry["providers"]:
            inst = skill["install"].get(provider, "none")
            if inst == "none":
                continue
            if inst.startswith("plugin:"):
                plugin_id = inst.split(":", 1)[1]
                found = False
                try:
                    with open(CLAUDE_PLUGINS_JSON, encoding="utf-8") as f:
                        found = plugin_id in f.read()
                except OSError:
                    pass
                notes.append(f"[{provider}] '{skill['name']}' plugin '{plugin_id}': "
                             + ("installed" if found else "NOT found in installed_plugins.json (verify-only)"))
                continue
            locs = expected_locations(skill, provider)
            if inst == "inherit":
                visible = any(match_skill(registry, e, provider) is skill
                              for e in scan.get(provider, []) if e["is_dir"])
                checked += 1
                if not visible:
                    failures.append(f"[{provider}] '{skill['name']}' (inherit) not visible")
                continue
            for loc in locs:
                checked += 1
                if inst.startswith("junction:"):
                    if not is_link(loc):
                        failures.append(f"[{provider}] '{skill['name']}': no junction at {loc}")
                        continue
                    if link_target(loc) != canonical_target(skill):
                        failures.append(f"[{provider}] '{skill['name']}': junction {loc} "
                                        f"targets {os.path.realpath(loc)} != {canon}")
                        continue
                    if not os.path.exists(loc):
                        failures.append(f"[{provider}] '{skill['name']}': junction {loc} "
                                        f"is dead - target {canon} does not exist")
                        continue
                if bundle:
                    if not os.path.isdir(loc):
                        failures.append(f"[{provider}] '{skill['name']}': bundle {loc} does not resolve")
                    continue
                sk = os.path.join(loc, "SKILL.md")
                if not os.path.isfile(sk):
                    failures.append(f"[{provider}] '{skill['name']}': no SKILL.md at {loc}")
                    continue
                fm = parse_frontmatter(sk)
                if fm["error"]:
                    failures.append(f"[{provider}] '{skill['name']}': {sk}: {fm['error']}")
                elif fm["name"] != skill["name"]:
                    failures.append(f"[{provider}] '{skill['name']}': frontmatter name "
                                    f"'{fm['name']}' at {loc}")

    print("skillctl verify")
    print("=" * 60)
    for n in notes:
        print(f"  note: {n}")
    for f_ in failures:
        print(f"  FAIL: {f_}")
    print(f"checked {checked} mapping(s): {len(failures)} failure(s)")
    return 1 if failures else 0


# --------------------------------------------------------------------------
# update
# --------------------------------------------------------------------------

def load_upstream_cache():
    if UPSTREAM_CACHE_PATH.exists():
        with open(UPSTREAM_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_upstream_cache(cache):
    with open(UPSTREAM_CACHE_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cache, f, indent=2, sort_keys=True)
        f.write("\n")


def cmd_update(args):
    registry = load_registry()
    apply = args.apply
    cache = load_upstream_cache()
    new_cache = dict(cache)
    mode = "APPLY" if apply else "PLAN"
    rc = 0

    targets = [s for s in registry["skills"]
               if (s.get("upstream") or {}).get("type") == "github"]
    if args.skill:
        targets = [s for s in targets if s["name"] == args.skill]
        if not targets:
            print(f"no github-upstream skill named '{args.skill}'")
            return 1

    print(f"skillctl update ({mode}) - {len(targets)} github-upstream skill(s)")
    if apply:
        snap = make_snapshot("pre-update")
        print(f"  snapshot: {snap}")
    for skill in targets:
        up = skill["upstream"]
        repo, subpath, ref = up["repo"], up["subpath"], up.get("ref", "main")
        url = f"https://github.com/{repo}"
        canon = canonical_path(skill)
        try:
            r = subprocess.run(["git", "ls-remote", url, ref],
                               capture_output=True, text=True, check=True, timeout=60)
            commit = r.stdout.split()[0]
        except Exception as exc:  # noqa: BLE001
            rc = 1
            print(f"  ERROR '{skill['name']}': ls-remote failed: {exc}")
            continue
        cached = cache.get(skill["name"], {})
        if cached.get("commit") == commit:
            print(f"  skip  '{skill['name']}': upstream unchanged at {commit[:12]}")
            continue
        with tempfile.TemporaryDirectory(prefix="skillctl-") as tmp:
            try:
                subprocess.run(["git", "clone", "--depth", "1", "--branch", ref, url, tmp],
                               capture_output=True, text=True, check=True, timeout=300)
            except Exception as exc:  # noqa: BLE001
                rc = 1
                print(f"  ERROR '{skill['name']}': clone failed: {exc}")
                continue
            src = os.path.join(tmp, subpath)
            if not os.path.isdir(src):
                rc = 1
                print(f"  ERROR '{skill['name']}': subpath '{subpath}' not in upstream clone")
                continue
            up_hash = dir_hash(src)
            cur_hash = dir_hash(canon) if os.path.isdir(canon) else None
            if up_hash == cur_hash:
                print(f"  same  '{skill['name']}': content identical, recording commit {commit[:12]}")
                new_cache[skill["name"]] = {"commit": commit, "hash": up_hash,
                                            "repo": repo, "subpath": subpath, "ref": ref}
                continue
            print(f"  [{mode}] update '{skill['name']}': {repo}/{subpath}@{ref} "
                  f"commit {cached.get('commit', '<none>')[:12] if cached else '<none>'} -> {commit[:12]}")
            print(f"         canonical: {canon}")
            if apply:
                dest = archive_move(canon, f"upstream refresh of '{skill['name']}' from {repo}@{commit[:12]}",
                                    dest_name=f"upstream-{skill_dir_name(skill)}", apply=True)
                print(f"         archived old canonical -> {dest}")
                os.makedirs(canon, exist_ok=True)
                shutil.copytree(src, canon, dirs_exist_ok=True)
                new_cache[skill["name"]] = {"commit": commit, "hash": up_hash,
                                            "repo": repo, "subpath": subpath, "ref": ref}
                print(f"         replaced canonical with upstream content")
    if apply:
        save_upstream_cache(new_cache)
        print("upstream cache updated")
    else:
        print("re-run with --apply to execute these actions")
    return rc


# --------------------------------------------------------------------------
# archive
# --------------------------------------------------------------------------

def cmd_archive(args):
    src = os.path.abspath(expand_home(args.path))
    if not os.path.exists(src) and not is_link(src):
        # is_link catches dangling junctions/symlinks whose target is gone
        print(f"path does not exist: {src}")
        return 1
    reason = args.reason or "manual archive via skillctl"
    dest = archive_move(src, reason, apply=True)
    print(f"archived {src} -> {dest}")
    print(f"reason: {reason}")
    return 0


# --------------------------------------------------------------------------
# register
# --------------------------------------------------------------------------

def save_registry(registry):
    """Atomic registry write (tmp file + replace), stable formatting."""
    tmp = REGISTRY_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, REGISTRY_PATH)


LOCK_PATH = REGISTRY_PATH.with_suffix(".json.lock")


@contextlib.contextmanager
def registry_lock(timeout=15):
    """Serialise registry load-modify-write across parallel processes.

    A second writer waits instead of clobbering the first one's read —
    prevents the lost-update race when register/unregister run concurrently.
    """
    fd = None
    waited = 0.0
    while fd is None:
        try:
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if waited >= timeout:
                raise TimeoutError(f"registry lock still held after {timeout}s: {LOCK_PATH}")
            time.sleep(0.1)
            waited += 0.1
    try:
        yield
    finally:
        os.close(fd)
        try:
            os.unlink(LOCK_PATH)
        except OSError:
            pass


def home_rel(path):
    """Collapse the user's home prefix to ~ for portable registry entries.

    Matches the home in its plain and its resolved spelling: callers pass
    resolved link targets, which differ from home_dir() when the home is
    reached through a link or an 8.3 name.
    """
    p = os.path.normpath(os.path.abspath(path))
    for home in (home_dir(), os.path.realpath(home_dir())):
        if norm(p).startswith(norm(home) + os.sep):
            p = "~" + p[len(home):]
            break
    return p.replace(os.sep, "/")


def find_unregistered(registry):
    """Stray skill dirs (valid SKILL.md, no registry match) across providers.

    Returns list of {'name', 'path', 'real', 'providers': [...]}, one row per
    distinct real target, providers in scan order. Read-only.
    """
    scan = scan_provider_dirs(registry)
    found = {}
    for provider, entries in scan.items():
        for e in entries:
            if not e["is_dir"] or e["fm"] is None or e["fm"].get("error"):
                continue
            if match_skill(registry, e, provider) is not None:
                continue
            key = norm(e["real"])
            row = found.setdefault(key, {
                "name": e["fm"]["name"] or e["name"],
                "dir": e["name"],
                "path": e["path"],
                "real": e["real"],
                "providers": [],
            })
            if provider not in row["providers"]:
                row["providers"].append(provider)
    return [found[k] for k in sorted(found, key=lambda k: found[k]["name"])]


def infer_install(real_path):
    """Default per-provider install values from where the skill lives.

    real_path is resolved, so it is compared with resolved scan dirs.
    """
    rp = norm(real_path)
    agents = resolved(AGENTS_DIR)
    agents_sub = resolved(os.path.join(AGENTS_DIR, "skills"))
    kimi = resolved(KIMI_DIR)
    claude = resolved(expand_home("~/.claude/skills"))
    install = {"codex": "none", "kimi": "none", "claude": "none", "vscode": "none"}
    if rp.startswith(agents_sub + os.sep):
        install.update({"codex": "agents/skills", "kimi": "agents/skills",
                        "vscode": "agents/skills"})
    elif rp.startswith(agents + os.sep):
        install.update({"codex": "agents", "kimi": "agents", "vscode": "agents"})
    elif rp.startswith(kimi + os.sep):
        install["kimi"] = "kimi"
    elif rp.startswith(claude + os.sep):
        install["claude"] = "path:" + home_rel(real_path)
    if install["claude"] == "none":
        # already exposed to Claude Code by an existing junction?
        cand = os.path.join(expand_home("~/.claude/skills"),
                            os.path.basename(real_path.rstrip(os.sep)))
        if is_link(cand) and link_target(cand) == rp:
            install["claude"] = "junction:" + home_rel(cand)
    return install


def build_path_entry(path, upstream, origin="unknown"):
    """Registry entry for a skill directory (used by register/discover --fetch).

    Always a path canonical, never a repo canonical: adopting an existing skill
    records where it already lives, it never copies it into this repo.
    """
    sk = os.path.join(path, "SKILL.md")
    fm = parse_frontmatter(sk)
    real = link_target(path)
    name = fm["name"] or os.path.basename(path)
    entry = {"name": name,
             "origin": origin,
             "canonical": {"type": "path", "path": home_rel(real)},
             "upstream": upstream,
             "install": infer_install(real)}
    dirname = os.path.basename(real.rstrip(os.sep))
    if dirname != name:
        entry["dir"] = dirname
    return entry


def _cmd_register_impl(args):
    registry = load_registry()
    if args.scan:
        rows = find_unregistered(registry)
        print(f"skillctl register --scan - {len(rows)} unregistered skill(s)")
        for r in rows:
            print(f"  {r['name']}  [{','.join(r['providers'])}]")
            print(f"    path: {r['path']}")
        return 0

    apply = args.apply and not args.dry_run
    mode = "APPLY" if apply else "PLAN"
    upstream = None
    if args.upstream:
        repo, _, subpath = args.upstream.partition(":")
        upstream = {"type": "github", "repo": repo,
                    "subpath": subpath or "skills/<name>", "ref": "main"}

    rows = []
    for raw in args.paths:
        p = os.path.normpath(os.path.abspath(expand_home(raw)))
        sk = os.path.join(p, "SKILL.md")
        if not (os.path.isdir(p) and os.path.isfile(sk)):
            print(f"  ERROR not a skill directory (no SKILL.md): {p}")
            return 1
        fm = parse_frontmatter(sk)
        if fm.get("error"):
            print(f"  ERROR {p}: {fm['error']}")
            return 1
        real = link_target(p)
        name = fm["name"] or os.path.basename(p)
        existing = [s for s in registry["skills"]
                    if s["name"] == name or canonical_target(s) == norm(real)]
        if existing:
            print(f"  skip  '{name}': already registered "
                  f"(canonical: {canonical_path(existing[0])})")
            continue
        rows.append(build_path_entry(p, upstream, getattr(args, "origin", "unknown")))

    print(f"skillctl register ({mode}) - {len(rows)} skill(s) to add")
    for e in rows:
        vis = sorted({v for v in e["install"].values() if v != "none"})
        print(f"  add '{e['name']}'  origin={e['origin']}  "
              f"canonical={e['canonical']['path']}  install={vis}")
        if e["upstream"]:
            print(f"       upstream: github {e['upstream']['repo']}:{e['upstream']['subpath']}")
    if not rows:
        return 0
    if apply:
        registry["skills"].extend(rows)
        save_registry(registry)
        print(f"registered {len(rows)} skill(s); registry saved")
    else:
        print("re-run with --apply to write the registry")
    return 0


# --------------------------------------------------------------------------
# snapshot
# --------------------------------------------------------------------------

def make_snapshot(label=None):
    """Write _archive/snapshots/<YYYYMMDD-HHMMSS>[-label]/ with registry copy,
    link-map.json and skills-listing.txt. Writes only inside _archive."""
    registry = load_registry()
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = ""
    if label:
        slug = "-" + re.sub(r"[^A-Za-z0-9_-]+", "-", label).strip("-")
    dest = ARCHIVE_ROOT / "snapshots" / f"{ts}{slug}"
    dest.mkdir(parents=True, exist_ok=False)
    shutil.copy2(REGISTRY_PATH, dest / "skills.json")

    link_map = {}
    for skill in registry["skills"]:
        canon = canonical_path(skill)
        for provider in registry["providers"]:
            inst = skill["install"].get(provider, "none")
            for loc in expected_locations(skill, provider):
                if inst.startswith("junction:"):
                    resolves = bool(is_link(loc) and link_target(loc) == canonical_target(skill))
                elif inst.startswith("path:"):
                    resolves = os.path.isdir(loc)
                else:
                    resolves = os.path.isfile(os.path.join(loc, "SKILL.md"))
                link_map.setdefault(provider, []).append(
                    {"skill": skill["name"], "install": inst,
                     "location": loc, "resolves": resolves})
    with open(dest / "link-map.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(link_map, f, indent=2, sort_keys=True)
        f.write("\n")

    lines = []
    for provider, entries in scan_provider_dirs(registry).items():
        lines.append(f"[{provider}]")
        lines.extend(f"  {e['path']}" for e in entries)
    (dest / "skills-listing.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(dest)


def cmd_snapshot(args):
    dest = make_snapshot(getattr(args, "label", None))
    print(f"snapshot written: {dest}")
    return 0


# --------------------------------------------------------------------------
# discover
# --------------------------------------------------------------------------

def distinct_upstreams(registry):
    """Sorted [(repo, ref)] of distinct github upstreams in the registry."""
    repos = {}
    for s in registry["skills"]:
        up = s.get("upstream") or {}
        if up.get("type") == "github":
            repos.setdefault(up["repo"], up.get("ref", "main"))
    return sorted(repos.items())


def scan_upstream_catalog(registry):
    """Clone each distinct upstream repo (depth 1) and enumerate skills/*.

    Returns (catalog, errors, tmpdirs); catalog maps frontmatter name ->
    {repo, ref, subpath, dirname, src}. Caller must clean tmpdirs.
    """
    catalog = {}
    errors = []
    tmps = []
    for repo, ref in distinct_upstreams(registry):
        tmp = tempfile.mkdtemp(prefix="skillctl-discover-")
        tmps.append(tmp)
        url = f"https://github.com/{repo}"
        try:
            subprocess.run(["git", "clone", "--depth", "1", "--branch", ref, url, tmp],
                           capture_output=True, text=True, check=True, timeout=300)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{repo}@{ref}: clone failed: {exc}")
            continue
        root = os.path.join(tmp, "skills")
        if not os.path.isdir(root):
            errors.append(f"{repo}@{ref}: no skills/ directory in clone")
            continue
        for d in sorted(os.listdir(root)):
            sd = os.path.join(root, d)
            sk = os.path.join(sd, "SKILL.md")
            if not (os.path.isdir(sd) and os.path.isfile(sk)):
                continue
            fm = parse_frontmatter(sk)
            name = fm.get("name") or d
            catalog[name] = {"repo": repo, "ref": ref,
                             "subpath": f"skills/{d}", "dirname": d, "src": sd}
    return catalog, errors, tmps


def cmd_discover(args):
    registry = load_registry()
    apply = args.apply
    mode = "APPLY" if apply else "PLAN"
    catalog, errors, tmps = scan_upstream_catalog(registry)
    rc = 1 if errors else 0
    try:
        for e in errors:
            print(f"  ERROR {e}")
        known = {s["name"] for s in registry["skills"]}
        if not args.fetch:
            new = {n: c for n, c in sorted(catalog.items()) if n not in known}
            print(f"skillctl discover - {len(catalog)} upstream skill(s), "
                  f"{len(new)} not in registry")
            for n, c in new.items():
                print(f"  {n}  ({c['repo']}:{c['subpath']}@{c['ref']})")
            if new:
                print("fetch one with: skillctl discover --fetch <name> --apply")
            return rc

        rows = []
        for name in args.fetch:
            if name in known:
                print(f"  skip  '{name}': already in registry")
                continue
            c = catalog.get(name)
            if c is None:  # also allow matching by upstream directory name
                c = next((v for v in catalog.values() if v["dirname"] == name), None)
            if c is None:
                print(f"  ERROR '{name}': not found in any upstream catalog")
                rc = 1
                continue
            dest = os.path.join(AGENTS_DIR, c["dirname"])
            print(f"  [{mode}] fetch '{name}': {c['repo']}:{c['subpath']}@{c['ref']} -> {dest}")
            if os.path.exists(dest):
                print(f"         ERROR destination already exists: {dest}")
                rc = 1
                continue
            if apply:
                shutil.copytree(c["src"], dest)
                entry = build_path_entry(dest, {"type": "github", "repo": c["repo"],
                                                "subpath": c["subpath"], "ref": c["ref"]})
                rows.append(entry)
                vis = sorted({v for v in entry["install"].values() if v != "none"})
                print(f"         copied and registered (canonical={entry['canonical']['path']}, install={vis})")
            else:
                print(f"         would copy and register with inferred install map")
        if apply and rows:
            registry["skills"].extend(rows)
            save_registry(registry)
            print(f"registry saved (+{len(rows)} skill(s))")
        elif not apply:
            print("re-run with --apply to execute")
        return rc
    finally:
        for t in tmps:
            shutil.rmtree(t, ignore_errors=True)


# --------------------------------------------------------------------------
# unregister
# --------------------------------------------------------------------------

def _cmd_unregister_impl(args):
    registry = load_registry()
    apply = args.apply
    mode = "APPLY" if apply else "PLAN"
    rc = 0
    remaining = list(registry["skills"])
    repo_root_norm = norm(str(REPO_ROOT)) + os.sep

    print(f"skillctl unregister ({mode})")
    for name in args.names:
        matches = [s for s in remaining if s["name"] == name]
        if not matches:
            print(f"  '{name}': not in registry - nothing to do")
            continue
        for s in matches:
            canon = s["canonical"]
            cpath = canonical_path(s)
            if args.archive_canonical:
                if canon["type"] not in ("path", "repo"):
                    print(f"  ERROR '{name}': canonical type '{canon['type']}' cannot be archived")
                    rc = 1
                    continue
                if canon["type"] == "repo" or norm(cpath).startswith(repo_root_norm):
                    print(f"  ERROR '{name}': canonical is repo-managed content ({cpath}); "
                          f"refusing to archive it. Re-run without --archive-canonical "
                          f"for entry-only removal.")
                    rc = 1
                    continue
                dest = archive_move(cpath, f"unregister --archive-canonical of '{name}'",
                                    apply=apply)
                print(f"  [{mode}] remove '{name}' from registry; archive canonical {cpath} -> {dest}")
            else:
                print(f"  [{mode}] remove '{name}' from registry (files left in place at {cpath})")
            remaining = [r for r in remaining if r is not s]
    removed = len(registry["skills"]) - len(remaining)
    if apply:
        if removed:
            registry["skills"] = remaining
            save_registry(registry)
        print(f"registry saved ({removed} entrie(s) removed)")
    else:
        print("re-run with --apply to execute")
    return rc


# --------------------------------------------------------------------------
# plugins (read-only, no network)
# --------------------------------------------------------------------------

def list_plugin_skills(skills_dir):
    """Frontmatter names of skill dirs directly under a plugin's skills/ dir."""
    out = []
    if os.path.isdir(skills_dir):
        for d in sorted(os.listdir(skills_dir)):
            sk = os.path.join(skills_dir, d, "SKILL.md")
            if os.path.isfile(sk):
                fm = parse_frontmatter(sk)
                out.append(fm.get("name") or d)
    return out


def cmd_plugins(_args):
    registry = load_registry()
    reg_names = {s["name"] for s in registry["skills"]}
    overlaps = []
    total = 0

    def print_skills(pid, skills):
        for sn in skills:
            mark = ""
            if sn in reg_names:
                mark = "  <-- OVERLAP with registry skill"
                overlaps.append(f"{pid} provides '{sn}'")
            print(f"    skill: {sn}{mark}")
        if not skills:
            print("    (no skills provided)")

    print("skillctl plugins (read-only, local state only)")
    print("=" * 60)
    print("claude (~/.claude/plugins/installed_plugins.json):")
    try:
        with open(CLAUDE_PLUGINS_JSON, encoding="utf-8") as f:
            claude_plugins = json.load(f).get("plugins", {})
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  none found ({exc})")
        claude_plugins = {}
    for pid in sorted(claude_plugins):
        for inst in claude_plugins[pid]:
            total += 1
            print(f"  {pid} v{inst.get('version', '?')} scope={inst.get('scope', '?')}")
            print_skills(pid, list_plugin_skills(
                os.path.join(inst.get("installPath", ""), "skills")))

    print("kimi (~/.kimi-code/plugins/managed/*/kimi.plugin.json):")
    managed = expand_home("~/.kimi-code/plugins/managed")
    found_any = False
    if os.path.isdir(managed):
        for d in sorted(os.listdir(managed)):
            manifest = os.path.join(managed, d, "kimi.plugin.json")
            if not os.path.isfile(manifest):
                continue
            found_any = True
            try:
                with open(manifest, encoding="utf-8") as f:
                    m = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                print(f"  {d}: unreadable manifest ({exc})")
                continue
            total += 1
            name = m.get("name", d)
            print(f"  {name} v{m.get('version', '?')} scope=kimi-managed")
            print_skills(name, list_plugin_skills(os.path.join(managed, d, "skills")))
    if not found_any:
        print("  none found")

    print("-" * 60)
    print(f"plugins installed: {total}, plugin-skill names overlapping registry: {len(overlaps)}")
    for o in overlaps:
        print(f"  OVERLAP: {o} (potential duplicate surface)")
    return 0


def cmd_register(args):
    with registry_lock():
        return _cmd_register_impl(args)


def cmd_unregister(args):
    with registry_lock():
        return _cmd_unregister_impl(args)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(prog="skillctl",
                                 description="Deterministic cross-provider skill management.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("audit", help="scan provider dirs and report drift vs registry")

    sp = sub.add_parser("sync", help="reconcile scan dirs to registry (plan by default)")
    sp.add_argument("--plan", action="store_true", help="print actions only (default)")
    sp.add_argument("--dry-run", action="store_true",
                    help="explicit no-change mode; same as default plan mode, errors if combined with --apply")
    sp.add_argument("--apply", action="store_true", help="execute the plan")
    sp.add_argument("--only", nargs="+", metavar="PATH-OR-NAME",
                    help="restrict the plan to actions matching these paths or skill names")
    sp.add_argument("--archive-strays", action="store_true",
                    help="also archive valid skills that are missing from the registry "
                         "(default: report them as 'review' and leave them in place)")

    vp = sub.add_parser("verify", help="every registry skill resolves at every mapped location")
    vp.add_argument("--ci", action="store_true",
                    help="CI-safe mode: repo-local invariants only, no home/provider-dir access")

    up = sub.add_parser("update", help="refresh github-upstream skills (plan by default)")
    up.add_argument("--skill", help="only this skill")
    up.add_argument("--dry-run", action="store_true",
                    help="explicit no-change mode; same as default plan mode, errors if combined with --apply")
    up.add_argument("--apply", action="store_true", help="execute updates")

    rg = sub.add_parser("register", help="add newly installed skills to the registry")
    rg.add_argument("paths", nargs="*", help="skill directories to register")
    rg.add_argument("--scan", action="store_true",
                    help="list unregistered skills found in provider scan dirs (read-only)")
    rg.add_argument("--upstream", metavar="OWNER/REPO[:SUBPATH]",
                    help="record a github upstream for the registered skill(s)")
    rg.add_argument("--origin", choices=ORIGINS, default="unknown",
                    help="who wrote these skills: 'mine', 'vendored' (someone else, "
                         "tracked but never stored in this repo), or 'unknown' (default)")
    rg.add_argument("--dry-run", action="store_true",
                    help="show what would be registered without writing (default when no --apply)")
    rg.add_argument("--apply", action="store_true", help="write the registry")

    dc = sub.add_parser("discover", help="list upstream skills not yet in the registry")
    dc.add_argument("--fetch", action="append", metavar="NAME",
                    help="fetch this upstream skill into ~/.agents/skills and register it (repeatable)")
    dc.add_argument("--dry-run", action="store_true",
                    help="plan mode (default); errors if combined with --apply")
    dc.add_argument("--apply", action="store_true", help="execute --fetch downloads and registry writes")

    ur = sub.add_parser("unregister", help="remove skills from the registry")
    ur.add_argument("names", nargs="+", help="registry skill names to remove")
    ur.add_argument("--archive-canonical", action="store_true",
                    help="also move the canonical directory into _archive (refused for repo-managed content)")
    ur.add_argument("--dry-run", action="store_true",
                    help="plan mode (default); errors if combined with --apply")
    ur.add_argument("--apply", action="store_true", help="execute removals")

    sn = sub.add_parser("snapshot", help="write a state snapshot into _archive/snapshots/")
    sn.add_argument("--label", help="optional label appended to the snapshot directory name")

    sub.add_parser("plugins", help="read-only report of installed claude/kimi plugins and their skills")

    ar = sub.add_parser("archive", help="move a skill directory into _archive/")
    ar.add_argument("path")
    ar.add_argument("--reason", default=None)

    args = ap.parse_args(argv)
    if getattr(args, "dry_run", False) and getattr(args, "apply", False):
        ap.error("--dry-run and --apply are mutually exclusive")
    if args.cmd == "register" and not args.scan and not args.paths:
        ap.error("register: give at least one path, or use --scan")
    return {"audit": cmd_audit, "sync": cmd_sync, "verify": cmd_verify,
            "update": cmd_update, "archive": cmd_archive,
            "register": cmd_register, "discover": cmd_discover,
            "unregister": cmd_unregister, "snapshot": cmd_snapshot,
            "plugins": cmd_plugins}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
