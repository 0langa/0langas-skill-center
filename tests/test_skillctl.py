"""Sandboxed tests for tools/skillctl.py.

Every test copies skillctl.py into a throwaway repo and points SKILLCTL_HOME
at a throwaway home. USERPROFILE and HOME point at a separate decoy directory,
so a code path that ignored SKILLCTL_HOME would show up as a write to the
decoy - never to the real ~/.agents, ~/.claude or ~/.kimi-code installs.

Run from the repo root:  python -m unittest discover -s tests -v
"""

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLCTL = REPO_ROOT / "tools" / "skillctl.py"

PROVIDERS = {
    "codex": {"scan": ["~/.agents/skills"], "dedupe": "none", "link": "junction-ok"},
    "kimi": {"scan": ["~/.kimi-code/skills", "~/.agents/skills"],
             "dedupe": "by-name-first-wins", "link": "junction-ok"},
    "claude": {"scan": ["~/.claude/skills"], "dedupe": "by-target", "link": "junction-ok"},
    "vscode": {"scan": ["~/.copilot/skills", "~/.claude/skills", "~/.agents/skills"],
               "dedupe": "none", "link": "junction-ok"},
}

PLAN_LINE = re.compile(r"^\s+\[(?:PLAN|APPLY)\] (\S+)\s+\[([^\]]*)\]\s*(.*?) :: (.*)$")


def is_link(path):
    """True for a junction or symlink itself, dangling or not."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return (stat.S_ISLNK(st.st_mode)
            or getattr(st, "st_reparse_tag", 0) == stat.IO_REPARSE_TAG_MOUNT_POINT)


def remove_tree(path):
    """rmtree that unlinks junctions instead of descending into them.

    Sandboxes link into skill directories - in one test, this repo's own - so
    cleanup must never be able to reach the content behind a link.
    """
    for root, dirs, _files in os.walk(path):
        for d in list(dirs):
            p = os.path.join(root, d)
            if is_link(p):
                try:
                    os.rmdir(p)
                except OSError:
                    os.unlink(p)
                dirs.remove(d)
    shutil.rmtree(path, ignore_errors=True)


def make_junction(link, target):
    os.makedirs(os.path.dirname(link), exist_ok=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                   check=True, capture_output=True)


def write_skill(directory, name, description="Test skill."):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8")
    return directory


def same_path(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


class Sandbox:
    """A throwaway repo (with a copy of skillctl.py) plus a throwaway home."""

    def __init__(self, testcase, skillctl=SKILLCTL):
        self.root = Path(tempfile.mkdtemp(prefix="skillctl-test-"))
        testcase.addCleanup(remove_tree, self.root)
        self.repo = self.root / "repo"
        self.home = self.root / "home"
        self.decoy = self.root / "decoy-home"
        for d in (self.repo / "tools", self.repo / "registry", self.home, self.decoy):
            d.mkdir(parents=True)
        shutil.copy2(skillctl, self.repo / "tools" / "skillctl.py")
        self.skills = []

    # -- registry building ------------------------------------------------
    def add_repo_skill(self, name):
        write_skill(self.repo / name, name)
        entry = {"name": name, "origin": "mine",
                 "canonical": {"type": "repo", "path": name}, "upstream": None,
                 "install": {"codex": f"junction:~/.agents/skills/{name}",
                             "kimi": f"junction:~/.agents/skills/{name}",
                             "claude": f"junction:~/.claude/skills/{name}",
                             "vscode": "inherit"}}
        self.skills.append(entry)
        return entry

    def add_path_skill(self, name, create=True):
        """A third-party skill that lives in ~/.agents/skills, never in the repo."""
        if create:
            write_skill(self.home / ".agents" / "skills" / name, name)
        entry = {"name": name, "origin": "vendored",
                 "canonical": {"type": "path", "path": f"~/.agents/skills/{name}"},
                 "upstream": None,
                 "install": {"codex": "agents", "kimi": "agents", "vscode": "agents",
                             "claude": f"junction:~/.claude/skills/{name}"}}
        self.skills.append(entry)
        return entry

    def write_registry(self, providers=None, **extra):
        data = {"version": 1, "providers": providers or PROVIDERS, "skills": self.skills}
        data.update(extra)
        (self.repo / "registry" / "skills.json").write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def registry(self):
        return json.loads((self.repo / "registry" / "skills.json").read_text(encoding="utf-8"))

    # -- running skillctl -------------------------------------------------
    def run(self, *args, home=None):
        env = dict(os.environ)
        env["SKILLCTL_HOME"] = str(home or self.home)
        env["USERPROFILE"] = str(self.decoy)
        env["HOME"] = str(self.decoy)
        return subprocess.run([sys.executable, str(self.repo / "tools" / "skillctl.py"), *args],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env, cwd=str(self.root))

    def plan(self, *extra, home=None):
        """[(op, providers, path, reason)] from `sync --plan`."""
        r = self.run("sync", "--plan", *extra, home=home)
        return [m.groups() for m in map(PLAN_LINE.match, r.stdout.splitlines()) if m]

    # -- filesystem helpers -----------------------------------------------
    def agents(self, name):
        return self.home / ".agents" / "skills" / name

    def claude(self, name):
        return self.home / ".claude" / "skills" / name

    def archived(self):
        """Every entry moved into the sandbox repo's _archive/<date>/."""
        root = self.repo / "_archive"
        if not root.is_dir():
            return []
        return sorted(p.name for day in root.iterdir() if day.is_dir()
                      and day.name != "snapshots" for p in day.iterdir())


@unittest.skipUnless(os.name == "nt", "skillctl links with mklink /J (Windows only)")
class InstallAndRepairTest(unittest.TestCase):

    def assertLinksTo(self, link, target):
        self.assertTrue(is_link(link), f"{link} is not a junction")
        self.assertTrue(os.path.exists(link), f"{link} is a dead link")
        self.assertTrue(same_path(link, target), f"{link} does not resolve to {target}")

    def assertNoPlan(self, sb, **kw):
        self.assertEqual(sb.plan(**kw), [], "a second sync must have nothing to do")

    def test_fresh_install_links_every_provider_location_and_is_idempotent(self):
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.add_path_skill("beta")
        sb.write_registry()

        r = sb.run("sync", "--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLinksTo(sb.agents("alpha"), sb.repo / "alpha")
        self.assertLinksTo(sb.claude("alpha"), sb.repo / "alpha")
        self.assertLinksTo(sb.claude("beta"), sb.agents("beta"))
        self.assertFalse(is_link(sb.agents("beta")), "a path canonical stays a real directory")

        self.assertNoPlan(sb)
        self.assertEqual(sb.run("verify").returncode, 0)
        audit = sb.run("audit")
        self.assertEqual(audit.returncode, 0, audit.stdout)

    def test_home_override_keeps_the_real_home_untouched(self):
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.write_registry()
        self.assertEqual(sb.run("sync", "--apply").returncode, 0)
        for cmd in (("audit",), ("verify",), ("plugins",), ("register", "--scan")):
            sb.run(*cmd)
        self.assertEqual(list(sb.decoy.iterdir()), [],
                         "skillctl wrote outside SKILLCTL_HOME")

    def test_relinks_dangling_junction_after_the_repo_moved(self):
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.write_registry()
        make_junction(sb.agents("alpha"), sb.root / "old-repo-location" / "alpha")
        self.assertFalse(os.path.exists(sb.agents("alpha")))

        plan = sb.plan()
        self.assertIn("relink", [op for op, *_ in plan])
        self.assertNotIn("archive", [op for op, *_ in plan],
                         "a dead link the registry owns is repaired, not archived")
        self.assertEqual(sb.run("sync", "--apply").returncode, 0)
        self.assertLinksTo(sb.agents("alpha"), sb.repo / "alpha")
        self.assertNoPlan(sb)

    def test_relinks_wrong_target_junction(self):
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.add_repo_skill("gamma")
        sb.write_registry()
        make_junction(sb.claude("alpha"), sb.repo / "gamma")

        self.assertEqual(sb.run("sync", "--apply").returncode, 0)
        self.assertLinksTo(sb.claude("alpha"), sb.repo / "alpha")
        self.assertTrue((sb.repo / "gamma" / "SKILL.md").is_file())
        self.assertNoPlan(sb)

    def test_unregistered_skill_is_reported_for_review_and_left_alone(self):
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.write_registry()
        write_skill(sb.agents("newcomer"), "newcomer")

        self.assertEqual(sb.run("sync", "--apply").returncode, 0)
        self.assertTrue((sb.agents("newcomer") / "SKILL.md").is_file())
        self.assertEqual(sb.archived(), [])
        self.assertIn("review", [op for op, *_ in sb.plan()])

    def test_archive_strays_moves_the_link_never_the_content_behind_it(self):
        sb = Sandbox(self)
        sb.write_registry()
        elsewhere = write_skill(sb.root / "elsewhere" / "stray", "stray")
        make_junction(sb.agents("stray"), elsewhere)

        r = sb.run("sync", "--apply", "--archive-strays")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.lexists(sb.agents("stray")))
        self.assertTrue((elsewhere / "SKILL.md").is_file(), "the link target was touched")
        self.assertEqual(sb.archived(), ["codex,kimi,vscode-stray"])
        log = (sb.repo / "_archive" / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("stray", log)

    def test_dead_link_without_an_owner_is_archived(self):
        sb = Sandbox(self)
        sb.write_registry()
        make_junction(sb.agents("ghost"), sb.root / "gone")

        self.assertEqual(sb.run("sync", "--apply").returncode, 0)
        self.assertFalse(os.path.lexists(sb.agents("ghost")))
        self.assertEqual(sb.archived(), ["codex,kimi,vscode-ghost"])

    def test_unregister_keeps_files_and_refuses_to_archive_repo_content(self):
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.add_path_skill("beta")
        sb.write_registry()

        r = sb.run("unregister", "alpha", "--archive-canonical", "--apply")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue((sb.repo / "alpha" / "SKILL.md").is_file())
        self.assertIn("alpha", [s["name"] for s in sb.registry()["skills"]])

        r = sb.run("unregister", "beta", "--apply")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual([s["name"] for s in sb.registry()["skills"]], ["alpha"])
        self.assertTrue((sb.agents("beta") / "SKILL.md").is_file(), "unregister must keep files")
        # running it again is a no-op
        self.assertEqual(sb.run("unregister", "beta", "--apply").returncode, 0)


if __name__ == "__main__":
    unittest.main()
