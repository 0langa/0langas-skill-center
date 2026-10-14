"""Sandboxed tests for tools/skillctl.py.

Most tests copy skillctl.py into a throwaway repo and point SKILLCTL_HOME at
a throwaway home; RepoInstallTest runs this repo's own skillctl against an
empty one. USERPROFILE and HOME point at a separate decoy directory, so a
code path that ignored SKILLCTL_HOME would show up as a write to the decoy -
never to the real ~/.agents, ~/.claude or ~/.kimi-code installs.

Run from the repo root:  python -m unittest discover -s tests -v
"""

import contextlib
import importlib.util
import io
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
from unittest import mock

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
            or getattr(st, "st_reparse_tag", 0)
            == getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003))


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

    def clear_readonly(func, p, _exc):  # git object files are read-only on Windows
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=clear_readonly)


def make_junction(link, target):
    os.makedirs(os.path.dirname(link), exist_ok=True)
    # quoted by hand: cmd.exe splits an unquoted path at & | < > ^
    subprocess.run(f'cmd /c mklink /J "{link}" "{target}"', check=True, capture_output=True)


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
        env["PYTHONIOENCODING"] = "utf-8"  # the pipe would otherwise be cp1252
        return subprocess.run([sys.executable, str(self.repo / "tools" / "skillctl.py"), *args],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env, cwd=str(self.root))

    def plan(self, *extra, home=None):
        """[(op, providers, path, reason)] from `sync --plan`."""
        r = self.run("sync", "--plan", *extra, home=home)
        # a crashed plan must not read as an empty, converged one
        assert r.returncode == 0 and "Traceback" not in r.stderr, r.stdout + r.stderr
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

    def test_real_directory_on_a_junction_path_is_archived_then_linked(self):
        # e.g. an old copy installed by hand before the skill moved into the repo
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.write_registry()
        old = write_skill(sb.agents("alpha"), "alpha", "Old hand-installed copy.")
        (old / "notes.txt").write_text("keep me", encoding="utf-8")

        ops = [(op, path) for op, _prov, path, _why in sb.plan()]
        self.assertEqual(ops[0], ("archive", str(sb.agents("alpha"))),
                         "the occupant must be moved out before the junction is created")
        self.assertIn(("junction", str(sb.agents("alpha"))), ops)
        r = sb.run("sync", "--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLinksTo(sb.agents("alpha"), sb.repo / "alpha")
        (kept,) = [d for day in (sb.repo / "_archive").iterdir() if day.is_dir()
                   for d in day.iterdir()]
        self.assertEqual((kept / "notes.txt").read_text(encoding="utf-8"), "keep me")
        self.assertNoPlan(sb)

    def test_file_on_a_junction_path_is_archived_then_linked(self):
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.write_registry()
        sb.claude("alpha").parent.mkdir(parents=True)
        sb.claude("alpha").write_text("not a skill", encoding="utf-8")

        r = sb.run("sync", "--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLinksTo(sb.claude("alpha"), sb.repo / "alpha")
        self.assertEqual(len(sb.archived()), 1)
        self.assertNoPlan(sb)

    def test_agents_install_relinks_a_dead_link_to_a_canonical_elsewhere(self):
        sb = Sandbox(self)
        entry = sb.add_repo_skill("alpha")
        entry["install"].update({"codex": "agents", "kimi": "agents"})
        sb.write_registry()
        make_junction(sb.agents("alpha"), sb.root / "old-repo-location" / "alpha")

        self.assertEqual([op for op, *_ in sb.plan()], ["junction", "relink"])
        r = sb.run("sync", "--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLinksTo(sb.agents("alpha"), sb.repo / "alpha")
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

    def test_folder_of_nested_skills_is_reviewed_not_archived(self):
        # e.g. a clone of a skills repo, or the old ~/.agents/skills/skills
        # mirror: no SKILL.md of its own, but working skills inside
        sb = Sandbox(self)
        sb.write_registry()
        write_skill(sb.agents("skills") / "web-scraper-utils", "web-scraper-utils")
        (sb.agents("old-scripts")).mkdir(parents=True)

        self.assertEqual(sb.run("sync", "--apply").returncode, 0)
        self.assertTrue((sb.agents("skills") / "web-scraper-utils" / "SKILL.md").is_file())
        self.assertEqual(sb.archived(), ["codex,kimi,vscode-old-scripts"])
        (review,) = [p for op, _prov, p, _why in sb.plan() if op == "review"]
        self.assertEqual(review, str(sb.agents("skills")))

        self.assertEqual(sb.run("sync", "--apply", "--archive-strays").returncode, 0)
        self.assertFalse(sb.agents("skills").exists())

    def test_owned_directory_without_skill_md_is_never_archived(self):
        # a registered canonical that lost its SKILL.md (mid-rename, say)
        sb = Sandbox(self)
        sb.add_path_skill("beta")
        sb.write_registry()
        os.remove(sb.agents("beta") / "SKILL.md")
        (sb.agents("beta") / "notes.md").write_text("user notes", encoding="utf-8")
        write_skill(sb.agents("pack") / "inner", "inner")
        (sb.agents("pack") / "inner" / "SKILL.md").rename(sb.agents("pack") / "inner" / "skill.md")

        sb.run("sync", "--apply")
        self.assertTrue((sb.agents("beta") / "notes.md").is_file())
        self.assertTrue((sb.agents("pack") / "inner" / "skill.md").is_file(),
                        "a pack of lowercase skill.md skills was archived")
        self.assertEqual(sb.archived(), [])

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

    def test_missing_canonical_is_unfixable_and_creates_no_dead_link(self):
        # A fresh machine where a third-party skill is registered but not yet
        # restored: linking to it would only manufacture a broken junction.
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.add_path_skill("beta", create=False)
        sb.write_registry()

        r = sb.run("sync", "--apply")
        self.assertEqual(r.returncode, 1, "unfixable entries must fail the apply")
        self.assertFalse(os.path.lexists(sb.claude("beta")), "created a junction to nothing")
        self.assertLinksTo(sb.claude("alpha"), sb.repo / "alpha")
        plan = sb.plan()
        self.assertEqual([(op, prov) for op, prov, *_ in plan],
                         [("unfixable", "codex,kimi,claude,vscode")],
                         "one unfixable line per skill, naming every provider")

    def test_audit_sync_and_verify_agree_on_a_missing_path_install(self):
        # "path:" = the skill lives right at a provider location, e.g. a
        # Claude-only skill registered from ~/.claude/skills
        sb = Sandbox(self)
        sb.skills.append({"name": "claude-only", "origin": "vendored",
                          "canonical": {"type": "path", "path": "~/.claude/skills/claude-only"},
                          "upstream": None,
                          "install": {"codex": "none", "kimi": "none", "vscode": "inherit",
                                      "claude": "path:~/.claude/skills/claude-only"}})
        sb.write_registry()

        self.assertEqual(sb.run("verify").returncode, 1)
        audit = sb.run("audit")
        self.assertEqual(audit.returncode, 1)
        self.assertIn("'claude-only' required at", audit.stdout)
        self.assertEqual([(op, prov) for op, prov, *_ in sb.plan()], [("unfixable", "claude")])

        write_skill(sb.claude("claude-only"), "claude-only")
        self.assertEqual(sb.run("verify").returncode, 0)
        self.assertEqual(sb.run("audit").returncode, 0)
        self.assertNoPlan(sb)

    def test_canonical_seen_through_a_linked_scan_dir_is_left_alone(self):
        # ~/.claude/skills itself a junction to ~/.agents/skills: the claude
        # location of beta *is* its canonical. An earlier revision of this
        # branch archived it as "a real directory in the way".
        sb = Sandbox(self)
        sb.add_path_skill("beta")
        sb.write_registry()
        make_junction(sb.home / ".claude" / "skills", sb.home / ".agents" / "skills")

        self.assertEqual([op for op, *_ in sb.plan()], [])
        self.assertEqual(sb.run("sync", "--apply").returncode, 0)
        self.assertTrue((sb.agents("beta") / "SKILL.md").is_file())
        self.assertFalse(is_link(sb.agents("beta")))
        self.assertEqual(sb.archived(), [])

    def test_invalid_install_locations_never_archive_anything(self):
        # One-character registry typos that pointed a link at a scan root,
        # the home, or the current directory.
        for value in ("junction:~/.agents/skills", "junction:~", "junction:~/.agents"):
            with self.subTest(value=value):
                sb = Sandbox(self)
                sb.add_path_skill("beta")
                sb.add_repo_skill("alpha")["install"]["claude"] = value
                sb.write_registry()
                r = sb.run("sync", "--apply")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("is not directly inside a directory claude scans", r.stdout)
                self.assertEqual(sb.archived(), [])
                self.assertTrue((sb.agents("beta") / "SKILL.md").is_file())
        sb = Sandbox(self)
        sb.add_path_skill("beta")
        sb.add_repo_skill("alpha")
        sb.skills[-1].update({"dir": "", "install": {"codex": "agents", "kimi": "none",
                                                      "claude": "none", "vscode": "none"}})
        sb.write_registry()
        self.assertEqual(sb.run("sync", "--apply").returncode, 1)
        self.assertEqual(sb.archived(), [])
        self.assertTrue((sb.agents("beta") / "SKILL.md").is_file())
        ci = sb.run("verify", "--ci")
        self.assertEqual(ci.returncode, 1, "verify --ci must refuse dir '' too")

    def test_dir_values_never_reach_outside_the_skill_folder(self):
        # "dir" names the folder inside a base install; anything but a single
        # folder name pointed sync at the scan root or above it. Windows drops
        # trailing dots and spaces, so "..." and ". ." name the scan root too.
        for value in ("", ".", "..", "sub/x", "sub\\x", "C:/x", "...", ". .", "x "):
            with self.subTest(dir=value):
                sb = Sandbox(self)
                sb.add_path_skill("beta")
                sb.add_repo_skill("alpha")
                sb.skills[-1].update({"dir": value, "install": {
                    "codex": "agents", "kimi": "none", "claude": "none", "vscode": "none"}})
                sb.write_registry()
                r = sb.run("sync", "--apply")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertEqual(sb.archived(), [])
                self.assertTrue((sb.agents("beta") / "SKILL.md").is_file())
                ci = sb.run("verify", "--ci")
                self.assertIn("'alpha': 'dir' must be a single folder name", ci.stdout)

    def test_a_location_owned_by_another_skill_is_refused(self):
        # alpha's claude junction typed onto beta's agents folder: archiving
        # "the occupant" would have evicted beta's canonical
        sb = Sandbox(self)
        sb.add_path_skill("beta")
        sb.add_repo_skill("alpha")["install"]["kimi"] = "junction:~/.agents/skills/beta"
        sb.write_registry()
        r = sb.run("sync", "--apply")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("is claimed by both", r.stdout)
        self.assertEqual(sb.archived(), [])
        self.assertTrue((sb.agents("beta") / "SKILL.md").is_file())
        self.assertFalse(is_link(sb.agents("beta")))

    def test_a_scan_dir_or_container_is_never_a_location(self):
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")["install"]["codex"] = "junction:~/.agents/skills/skills"
        sb.write_registry(containers={"~/.agents/skills/skills": "nested mirror"})
        write_skill(sb.agents("skills") / "mirrored", "mirrored")
        r = sb.run("sync", "--apply")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("is a scan directory or a container", r.stdout)
        self.assertTrue((sb.agents("skills") / "mirrored" / "SKILL.md").is_file())
        self.assertEqual(sb.archived(), [])

    def test_a_location_windows_reads_as_the_scan_dir_is_refused(self):
        # normpath() keeps "...", " " and ". ." as names, but Windows drops
        # trailing dots and spaces: each of these is ~/.claude/skills itself,
        # and sync archived the whole folder - unregistered skills included -
        # to make room for one junction.
        for value in ("junction:~/.claude/skills/...", "junction:~/.claude/skills/ ",
                      "junction:~/.claude/skills/. ."):
            with self.subTest(value=value):
                sb = Sandbox(self)
                sb.add_repo_skill("alpha")
                sb.add_repo_skill("gamma")["install"]["claude"] = value
                sb.write_registry()
                make_junction(sb.claude("alpha"), sb.repo / "alpha")
                write_skill(sb.claude("my-own"), "my-own")
                r = sb.run("sync", "--apply")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("the folder name", r.stdout)
                self.assertEqual(sb.archived(), [])
                self.assertTrue((sb.claude("my-own") / "SKILL.md").is_file())
                self.assertLinksTo(sb.claude("alpha"), sb.repo / "alpha")
                ci = sb.run("verify", "--ci")
                self.assertEqual(ci.returncode, 1, ci.stdout)
                self.assertIn("'gamma': [claude]", ci.stdout)

    def test_a_duplicate_that_is_a_registered_canonical_is_never_archived(self):
        # kimi scans ~/.kimi-code/skills before ~/.agents/skills and sync kept
        # the first copy of a name, archiving the canonical seen second as a
        # "duplicate with conflicting target".
        sb = Sandbox(self)  # a stale copy at beta's kimi location
        sb.add_path_skill("beta")["install"]["kimi"] = "kimi"
        write_skill(sb.home / ".kimi-code" / "skills" / "beta", "beta", "Stale copy.")
        sb.write_registry()
        r = sb.run("sync", "--apply")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("the canonical of 'beta'", r.stdout)
        self.assertEqual(sb.archived(), [])
        self.assertIn("Test skill.", (sb.agents("beta") / "SKILL.md").read_text(encoding="utf-8"))

        sb = Sandbox(self)  # two registered skills whose SKILL.md share a name
        write_skill(sb.home / ".kimi-code" / "skills" / "foo", "foo")
        sb.skills.append({"name": "foo", "origin": "vendored",
                          "canonical": {"type": "path", "path": "~/.kimi-code/skills/foo"},
                          "upstream": None,
                          "install": {"codex": "none", "kimi": "kimi", "claude": "none",
                                      "vscode": "none"}})
        sb.add_path_skill("foo-two")["install"].update({"kimi": "none", "claude": "none"})
        write_skill(sb.agents("foo-two"), "foo")
        sb.write_registry()
        r = sb.run("sync", "--apply")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("the canonical of 'foo-two'", r.stdout)
        self.assertEqual(sb.archived(), [])
        self.assertTrue((sb.agents("foo-two") / "SKILL.md").is_file())

    def test_a_scan_dir_linked_to_the_repo_or_the_home_is_never_cleaned_out(self):
        # A scan dir that is a junction to the repo (to expose every repo
        # skill at once) made .git, tools/ and the README "strays"; one linked
        # to the home made every folder in it one.
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.write_registry()
        (sb.repo / ".git").mkdir()
        (sb.repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (sb.repo / "README.md").write_text("readme", encoding="utf-8")
        (sb.home / "Documents").mkdir()
        (sb.home / "Documents" / "notes.txt").write_text("keep me", encoding="utf-8")
        make_junction(sb.home / ".claude" / "skills", sb.repo)
        make_junction(sb.home / ".copilot" / "skills", sb.home)

        r = sb.run("sync", "--apply")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(sb.archived(), [])
        for kept in (sb.repo / ".git" / "HEAD", sb.repo / "README.md",
                     sb.repo / "tools" / "skillctl.py", sb.repo / "registry" / "skills.json",
                     sb.home / "Documents" / "notes.txt"):
            self.assertTrue(kept.is_file(), f"{kept} was moved")
        self.assertLinksTo(sb.agents("alpha"), sb.repo / "alpha")

    def test_home_relative_paths_cannot_escape_the_home(self):
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")["install"]["claude"] = "junction:~//.claude/skills/alpha"
        sb.write_registry()
        self.assertEqual(sb.run("sync", "--apply").returncode, 0)
        self.assertLinksTo(sb.claude("alpha"), sb.repo / "alpha")

    def test_home_reached_through_a_junction_is_idempotent(self):
        # Folder redirection, a moved profile, or an 8.3 spelling such as
        # C:\Users\RUNNER~1 on CI runners: the home path is not its own
        # realpath. Real directories under it are not links, and a link
        # target must be compared with the canonical's resolved path.
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.add_path_skill("delta")
        sb.write_registry()
        jhome = sb.root / "jhome"
        make_junction(jhome, sb.home)

        self.assertEqual({op for op, *_ in sb.plan(home=jhome)}, {"junction"})
        r = sb.run("sync", "--apply", home=jhome)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLinksTo(sb.claude("delta"), sb.agents("delta"))
        self.assertNoPlan(sb, home=jhome)
        verify = sb.run("verify", home=jhome)
        self.assertEqual(verify.returncode, 0, verify.stdout)
        audit = sb.run("audit", home=jhome)
        self.assertEqual(audit.returncode, 0, audit.stdout)

    def test_paths_with_cmd_metacharacters_link_and_relink(self):
        # cmd.exe treats & in an unquoted argument as a command separator
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.add_repo_skill("gamma")
        sb.write_registry()
        home = sb.root / "R&D"
        home.mkdir()
        make_junction(home / ".claude" / "skills" / "alpha", sb.repo / "gamma")

        r = sb.run("sync", "--apply", home=home)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLinksTo(home / ".agents" / "skills" / "alpha", sb.repo / "alpha")
        self.assertLinksTo(home / ".claude" / "skills" / "alpha", sb.repo / "alpha")
        self.assertNoPlan(sb, home=home)

    def test_non_ascii_paths_do_not_crash_piped_output(self):
        # Piped stdout uses the ANSI code page, which cannot encode every
        # character a Windows path can hold (here "Ł" and "ź" under cp1252).
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.write_registry()
        home = sb.root / "home-Łódź"
        home.mkdir()
        env = dict(os.environ, SKILLCTL_HOME=str(home),
                   USERPROFILE=str(sb.decoy), HOME=str(sb.decoy))
        for var in ("PYTHONIOENCODING", "PYTHONUTF8"):  # keep the default pipe encoding
            env.pop(var, None)
        r = subprocess.run([sys.executable, str(sb.repo / "tools" / "skillctl.py"),
                            "sync", "--apply"], capture_output=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(b"Traceback", r.stderr)
        self.assertLinksTo(home / ".claude" / "skills" / "alpha", sb.repo / "alpha")

    def test_register_through_a_linked_home_records_portable_paths(self):
        sb = Sandbox(self)
        sb.write_registry()
        jhome = sb.root / "jhome"
        make_junction(jhome, sb.home)
        write_skill(sb.agents("newbie"), "newbie")
        make_junction(sb.claude("newbie"), sb.agents("newbie"))

        r = sb.run("register", str(jhome / ".agents" / "skills" / "newbie"),
                   "--origin", "vendored", "--apply", home=jhome)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (entry,) = sb.registry()["skills"]
        self.assertEqual(entry["canonical"], {"type": "path", "path": "~/.agents/skills/newbie"})
        self.assertEqual(entry["install"], {"codex": "agents", "kimi": "agents", "vscode": "agents",
                                            "claude": "junction:~/.claude/skills/newbie"})
        # registering it again is a no-op
        sb.run("register", str(sb.agents("newbie")), "--apply", home=jhome)
        self.assertEqual(len(sb.registry()["skills"]), 1)

    def test_unregister_archives_only_canonicals_inside_a_provider_dir(self):
        sb = Sandbox(self)
        sb.add_path_skill("beta")
        sb.add_path_skill("gone", create=False)
        project = write_skill(sb.home / "source" / "repos" / "plugin-project", "plugin-project")
        sb.skills.append({"name": "plugin-project", "origin": "mine",
                          "canonical": {"type": "path", "path": "~/source/repos/plugin-project"},
                          "upstream": None,
                          "install": {"codex": "junction:~/.agents/skills/plugin-project",
                                      "kimi": "none", "claude": "none", "vscode": "inherit"}})
        sb.write_registry()

        r = sb.run("unregister", "plugin-project", "--archive-canonical", "--apply")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue((project / "SKILL.md").is_file(), "moved a project repo into _archive")
        self.assertIn("plugin-project", [s["name"] for s in sb.registry()["skills"]])

        r = sb.run("unregister", "beta", "--archive-canonical", "--apply")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertFalse(sb.agents("beta").exists())
        self.assertEqual(sb.archived(), ["beta"])

        # a canonical that is already gone used to crash the archive step
        r = sb.run("unregister", "gone", "--archive-canonical", "--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([s["name"] for s in sb.registry()["skills"]], ["plugin-project"])

        # a pack folder registered over skills registered inside it
        write_skill(sb.agents("pack") / "inner", "inner")
        sb.skills = [s for s in sb.registry()["skills"]]
        sb.skills.append({"name": "pack", "origin": "vendored", "bundle": True,
                          "canonical": {"type": "path", "path": "~/.agents/skills/pack"},
                          "upstream": None, "install": {"codex": "agents", "kimi": "none",
                                                        "claude": "none", "vscode": "none"}})
        sb.add_path_skill("inner", create=False)["canonical"]["path"] = "~/.agents/skills/pack/inner"
        sb.write_registry()
        r = sb.run("unregister", "pack", "--archive-canonical", "--apply")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("the canonical of 'inner'", r.stdout)
        self.assertTrue((sb.agents("pack") / "inner" / "SKILL.md").is_file())

    def test_register_upstream_without_subpath_records_the_skill_folder(self):
        sb = Sandbox(self)
        sb.write_registry()
        write_skill(sb.agents("upskill"), "upskill")
        r = sb.run("register", str(sb.agents("upskill")), "--upstream", "someone/skills",
                   "--origin", "vendored", "--apply")
        self.assertEqual(r.returncode, 0, r.stdout)
        (entry,) = sb.registry()["skills"]
        self.assertEqual(entry["upstream"]["subpath"], "skills/upskill")

    def test_plan_and_apply_are_mutually_exclusive(self):
        # --plan used to be ignored, so `sync --plan --apply` applied
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.write_registry()
        r = sb.run("sync", "--plan", "--apply")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertFalse(os.path.lexists(sb.claude("alpha")))

    def test_archiving_the_same_name_twice_in_a_day_does_not_collide(self):
        # the free-name check followed links, so an archived dead link
        # looked absent and the second move hit WinError 183
        sb = Sandbox(self)
        sb.write_registry()
        for _ in range(2):
            make_junction(sb.agents("ghost"), sb.root / "gone")
            r = sb.run("sync", "--apply")
            self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(sb.archived(), ["codex,kimi,vscode-ghost", "codex,kimi,vscode-ghost-2"])

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


@unittest.skipUnless(os.name == "nt" and shutil.which("git"), "needs git and mklink /J")
class WorktreeGuardTest(unittest.TestCase):
    """Real installs are never driven from a linked worktree."""

    def test_mutating_commands_refuse_to_run_from_a_linked_worktree(self):
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.write_registry()
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
               "-c", "core.autocrlf=false", "-C", str(sb.repo)]
        for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "x"],
                    ["worktree", "add", "-q", str(sb.root / "wt")]):
            subprocess.run(git + cmd, check=True, capture_output=True)
        # No SKILLCTL_HOME, so "the real home" is the decoy: a broken guard
        # could only ever touch the decoy.
        env = dict(os.environ, USERPROFILE=str(sb.decoy), HOME=str(sb.decoy),
                   PYTHONIOENCODING="utf-8")
        env.pop("SKILLCTL_HOME", None)

        def skillctl(checkout, *args, **extra):
            return subprocess.run([sys.executable, str(checkout / "tools" / "skillctl.py"), *args],
                                  capture_output=True, text=True, encoding="utf-8",
                                  env=dict(env, **extra))

        wt = sb.root / "wt"
        for args in (["sync", "--apply"], ["archive", str(sb.decoy / "anything")],
                     ["update", "--apply"], ["unregister", "alpha", "--archive-canonical", "--apply"]):
            r = skillctl(wt, *args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn("is a linked git worktree", r.stdout)
            self.assertIn("Run it from the main checkout instead", r.stdout)
        # the real home under another spelling is not a sandbox
        make_junction(sb.root / "jdecoy", sb.decoy)
        for home in (sb.root / "jdecoy", str(sb.decoy).upper() + os.sep):
            r = skillctl(wt, "sync", "--apply", SKILLCTL_HOME=str(home))
            self.assertEqual(r.returncode, 1, (home, r.stdout))
            self.assertIn("is a linked git worktree", r.stdout)
        self.assertEqual(list(sb.decoy.iterdir()), [])
        self.assertEqual(skillctl(wt, "sync", "--plan").returncode, 0, "plans stay allowed")
        sandbox = sb.root / "sandbox-home"
        self.assertEqual(skillctl(wt, "sync", "--apply", SKILLCTL_HOME=str(sandbox)).returncode, 0)
        # the main checkout, also when reached through a junction
        make_junction(sb.root / "jrepo", sb.repo)
        r = skillctl(sb.root / "jrepo", "sync", "--apply")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(skillctl(sb.repo, "sync", "--apply").returncode, 0, "main checkout")


class UpdateTest(unittest.TestCase):
    """update against a fake GitHub: git is stubbed, nothing leaves the machine."""

    def run_update(self, sb, upstream_tree, commit="c0ffee0000000000000000000000000000000001"):
        real_run = subprocess.run

        def fake_run(cmd, *args, **kwargs):
            if list(cmd[:2]) == ["git", "ls-remote"]:
                return subprocess.CompletedProcess(cmd, 0, f"{commit}\trefs/heads/main\n", "")
            if list(cmd[:2]) == ["git", "clone"]:
                shutil.copytree(upstream_tree, cmd[-1], dirs_exist_ok=True)
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return real_run(cmd, *args, **kwargs)

        env = {"SKILLCTL_HOME": str(sb.home), "USERPROFILE": str(sb.decoy), "HOME": str(sb.decoy)}
        with mock.patch.dict(os.environ, env):
            spec = importlib.util.spec_from_file_location(
                "skillctl_under_test", sb.repo / "tools" / "skillctl.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            out = io.StringIO()
            with mock.patch.object(module.subprocess, "run", fake_run), \
                    contextlib.redirect_stdout(out):
                rc = module.main(["update", "--apply"])
        return rc, out.getvalue()

    def upstream(self, sb, description):
        tree = sb.root / "upstream"
        write_skill(tree / "skills" / "beta", "beta", description)
        return tree

    def add_upstream_skill(self, sb, create):
        entry = sb.add_path_skill("beta", create=create)
        entry["upstream"] = {"type": "github", "repo": "someone/skills",
                             "subpath": "skills/beta", "ref": "main"}
        sb.write_registry()

    def test_update_installs_a_tracked_skill_missing_from_this_machine(self):
        # A fresh profile: the canonical was never restored. update used to
        # crash archiving the missing directory, before saving any progress.
        sb = Sandbox(self)
        self.add_upstream_skill(sb, create=False)
        rc, out = self.run_update(sb, self.upstream(sb, "Upstream v2."))
        self.assertEqual(rc, 0, out)
        self.assertIn("Upstream v2.", (sb.agents("beta") / "SKILL.md").read_text(encoding="utf-8"))
        cache = json.loads((sb.repo / "registry" / ".upstream-cache.json").read_text(encoding="utf-8"))
        self.assertEqual(cache["beta"]["commit"][:7], "c0ffee0")

    def test_update_archives_the_old_canonical_before_replacing_it(self):
        sb = Sandbox(self)
        self.add_upstream_skill(sb, create=True)
        rc, out = self.run_update(sb, self.upstream(sb, "Upstream v2."))
        self.assertEqual(rc, 0, out)
        self.assertIn("Upstream v2.", (sb.agents("beta") / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual(sb.archived(), ["upstream-beta"])
        old = next((sb.repo / "_archive").glob("2*/upstream-beta/SKILL.md"))
        self.assertIn("Test skill.", old.read_text(encoding="utf-8"))

    def test_update_never_replaces_a_scan_dir_the_home_or_another_skill(self):
        # update archives the canonical before copying upstream in: a typo
        # such as "~/.agents/skills/" moved every installed skill.
        for path in ("~/.agents/skills/", "~", "~/.agents/skills/beta/..", "~/.agents/skills/beta"):
            with self.subTest(canonical=path):
                sb = Sandbox(self)
                sb.add_path_skill("beta")
                entry = sb.add_path_skill("typo", create=False)
                entry["canonical"]["path"] = path
                entry["upstream"] = {"type": "github", "repo": "someone/skills",
                                     "subpath": "skills/beta", "ref": "main"}
                sb.write_registry()
                rc, out = self.run_update(sb, self.upstream(sb, "Upstream v2."))
                self.assertEqual(rc, 1, out)
                self.assertIn("refusing to replace the canonical", out)
                self.assertEqual(sb.archived(), [])
                self.assertIn("Test skill.", (sb.agents("beta") / "SKILL.md").read_text(encoding="utf-8"))
                if path != "~/.agents/skills/beta":  # verify --ci does not compare canonicals
                    ci = sb.run("verify", "--ci")
                    self.assertIn("'typo': canonical", ci.stdout)

    def test_unchanged_commit_still_restores_a_missing_canonical(self):
        sb = Sandbox(self)
        self.add_upstream_skill(sb, create=False)
        (sb.repo / "registry" / ".upstream-cache.json").write_text(json.dumps(
            {"beta": {"commit": "c0ffee0000000000000000000000000000000001"}}), encoding="utf-8")
        rc, out = self.run_update(sb, self.upstream(sb, "Upstream v2."))
        self.assertEqual(rc, 0, out)
        self.assertTrue((sb.agents("beta") / "SKILL.md").is_file(), out)


@unittest.skipUnless(os.name == "nt", "skillctl links with mklink /J (Windows only)")
class RepoInstallTest(unittest.TestCase):
    """This repo's real registry and skills, installed into an empty home."""

    def test_this_repos_skills_install_into_an_empty_home(self):
        root = Path(tempfile.mkdtemp(prefix="skillctl-repo-install-"))
        self.addCleanup(remove_tree, root)
        home, decoy = root / "home", root / "decoy-home"
        home.mkdir()
        decoy.mkdir()
        env = dict(os.environ, SKILLCTL_HOME=str(home), USERPROFILE=str(decoy), HOME=str(decoy))

        def skillctl(*args):
            return subprocess.run([sys.executable, str(SKILLCTL), *args], capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", env=env)

        def ops(result):
            return {m.group(1) for m in map(PLAN_LINE.match, result.stdout.splitlines()) if m}

        # This runs the real skillctl, whose _archive/ is the repo's own: make
        # sure an empty home needs nothing but new links before applying.
        self.assertTrue(ops(skillctl("sync", "--plan")) <= {"junction", "unfixable"})
        applied = skillctl("sync", "--apply")
        self.assertNotIn("ERROR", applied.stdout)

        registry = json.loads((REPO_ROOT / "registry" / "skills.json").read_text(encoding="utf-8"))
        linked = 0
        for skill in registry["skills"]:
            if skill["canonical"]["type"] != "repo":
                continue
            for value in skill["install"].values():
                if value.startswith("junction:~/"):
                    link = home / value[len("junction:~/"):]
                    self.assertTrue(is_link(link), f"no junction at {link}")
                    self.assertTrue(same_path(link, REPO_ROOT / skill["canonical"]["path"]))
                    linked += 1
        self.assertGreater(linked, 0)
        # Third-party skills cannot be installed from here; they stay unfixable.
        self.assertEqual(ops(skillctl("sync", "--plan")) - {"unfixable"}, set())
        self.assertEqual(list(decoy.iterdir()), [], "skillctl wrote outside SKILLCTL_HOME")

        pwsh = shutil.which("pwsh")
        if pwsh:  # the e2e harness's user-level junction checks agree
            e2e = subprocess.run([pwsh, "-NoProfile", "-File",
                                  str(REPO_ROOT / "tests" / "skill-center.e2e.ps1")],
                                 capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", env=dict(os.environ, SKILLCTL_HOME=str(home)))
            self.assertEqual(e2e.returncode, 0, e2e.stdout + e2e.stderr)


class VerifyCiTest(unittest.TestCase):
    """verify --ci checks what the repo guarantees, never the machine."""

    def run_ci(self, skillctl, home):
        env = dict(os.environ, SKILLCTL_HOME=str(home))
        return subprocess.run([sys.executable, str(skillctl), "verify", "--ci"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env)

    def test_this_repo_passes_on_a_machine_with_no_skills_installed(self):
        with tempfile.TemporaryDirectory() as empty:
            r = self.run_ci(SKILLCTL, Path(empty) / "no-such-home")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_machine_state_is_not_a_failure(self):
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.add_path_skill("beta", create=False)  # third-party, not installed here
        sb.write_registry()
        r = self.run_ci(sb.repo / "tools" / "skillctl.py", sb.root / "no-such-home")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_reports_registry_and_content_problems(self):
        sb = Sandbox(self)
        sb.add_repo_skill("alpha")
        sb.add_repo_skill("renamed")
        write_skill(sb.repo / "renamed", "old-name")
        write_skill(sb.repo / "orphan", "orphan")
        del sb.add_path_skill("no-origin")["origin"]
        sb.add_path_skill("bad-method")["install"]["kimi"] = "symlink"
        sb.add_path_skill("invisible")["install"]["claude"] = "agents"
        sb.add_path_skill("squatter")["install"]["claude"] = "junction:~/.claude/skills/alpha"
        sb.add_path_skill("escapes")["canonical"] = {"type": "repo", "path": "../outside"}
        sb.write_registry()

        r = self.run_ci(sb.repo / "tools" / "skillctl.py", sb.home)
        self.assertEqual(r.returncode, 1)
        failures = [line.strip() for line in r.stdout.splitlines() if "FAIL:" in line]
        for needle in (
            "'renamed': ",
            "orphan/: skill directory is not in the registry",
            "'no-origin': missing 'origin'",
            "'bad-method': [kimi] unknown install method 'symlink'",
            "'invisible': [claude] agents puts it in",
            "'squatter': [claude]",
            "'escapes': repo canonical '../outside' must be a path inside the repo",
        ):
            self.assertTrue(any(needle in f for f in failures), f"no failure for {needle!r}")
        self.assertFalse([f for f in failures if f.startswith("FAIL: 'alpha'")],
                         "the valid entry was flagged")


if __name__ == "__main__":
    unittest.main()
