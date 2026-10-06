from pathlib import Path
import re
import runpy


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".claude" / "skills"
NAME = re.compile(r"^[a-z0-9-]{1,64}$")


def validate(path: Path) -> list[str]:
    errors = []
    entry = path / "SKILL.md"
    if not entry.is_file():
        return [f"{path.name}: missing SKILL.md"]
    text = entry.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return [f"{path.name}: invalid YAML frontmatter delimiters"]
    frontmatter = text.split("---", 2)[1]
    match = re.search(r"^name:\s*([^\n]+)$", frontmatter, re.MULTILINE)
    if not match:
        errors.append(f"{path.name}: missing name")
    else:
        name = match.group(1).strip().strip("\"'")
        if name != path.name or not NAME.fullmatch(name):
            errors.append(f"{path.name}: invalid or mismatched name {name!r}")
    if not re.search(r"^description:\s*\S", frontmatter, re.MULTILINE):
        errors.append(f"{path.name}: missing description")
    return errors


def main() -> None:
    paths = sorted(path for path in SKILLS.iterdir() if path.is_dir())
    errors = [error for path in paths for error in validate(path)]
    if errors:
        raise SystemExit("\n".join(errors))
    audit = runpy.run_path(str(SKILLS / 'skill-library-audit/scripts/audit_library.py'))['audit']
    report = audit(SKILLS)
    if report['exitCode']:
        raise SystemExit(str(report))
    reference = SKILLS / 'aoe3de-reference'
    if reference.exists():
        errors = runpy.run_path(str(reference / 'scripts/check_reference_bundle.py'))['check'](reference)
        if errors:
            raise SystemExit('\n'.join(errors))
    print(f"Validated {len(paths)} canonical skills, complete resource closure and reference integrity where present.")


if __name__ == "__main__":
    main()
