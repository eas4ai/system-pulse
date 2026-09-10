"""Validate portable archives locally or retained artifacts from hosted CI."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile
import zipfile

from package_binary import TARGETS, check_binary_header
from package_linux import ROOT, capture, digest

REPOSITORY = "eas4ai/system-pulse"
INPUTS = [".github/workflows/ci.yml", "Cargo.toml", "Cargo.lock", ".cargo/config.toml",
          "src", "tests", "crates", "vendor", "assets", "package", "scripts/system-pulse"]
REQUIRED = {"COPYING", "LICENSES.html", "dependency-licenses.json", "SOURCE.txt", "source.tar.gz",
            "README.md", "build.json", "notices/LICENSE-APACHE", "notices/Intel-UAPI-NOTICE",
            "notices/Apple-NOTICE.md"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def archive_files(archive):
    """Read regular members without extracting paths or following links."""
    files = {}
    total = 0

    def add(name, size, read):
        nonlocal total
        path = PurePosixPath(name)
        require(not path.is_absolute() and ".." not in path.parts and "\\" not in name,
                "Unsafe archive path: " + name)
        require(name not in files, "Duplicate archive member: " + name)
        total += size
        require(total <= 2_000_000_000, "Archive exceeds the validation size limit")
        files[name] = read()

    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                require((member.external_attr >> 16) & 0o170000 != 0o120000, "Archive contains a symlink")
                if not member.is_dir():
                    add(member.filename, member.file_size, lambda: bundle.read(member))
    else:
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle:
                require(member.isfile() or member.isdir(), "Archive contains a nonregular member")
                if member.isfile():
                    add(member.name, member.size, lambda: bundle.extractfile(member).read())
    roots = {PurePosixPath(name).parts[0] for name in files}
    require(len(roots) == 1, "Archive must contain one package directory")
    require(all(len(PurePosixPath(name).parts) > 1 for name in files), "Loose archive file")
    return {name.split("/", 1)[1]: data for name, data in files.items()}


def verify_source(data, revision):
    tree = subprocess.check_output(["git", "ls-tree", "-rz", revision], cwd=ROOT, timeout=30)
    expected = {}
    for record in tree.split(b"\0"):
        if record:
            metadata, path = record.split(b"\t", 1)
            mode, kind, oid = metadata.split()
            require(kind == b"blob", "Source archive contains an unsupported git object")
            expected[path.decode()] = oid.decode()
    observed = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as bundle:
        for member in bundle:
            if member.isdir():
                continue
            require(member.name.startswith("system-pulse-source/"), "Wrong source archive prefix")
            name = member.name.removeprefix("system-pulse-source/")
            require(name not in observed, "Duplicate source member")
            if member.issym():
                content = member.linkname.encode()
            else:
                require(member.isfile(), "Unexpected source member type")
                content = bundle.extractfile(member).read()
            observed[name] = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
    require(observed == expected, "Bundled source differs from its committed git tree")


def verify_archive(directory, target, revision, run_id=None):
    label, executable = TARGETS[target]
    archives = list(directory.glob("*.zip")) + list(directory.glob("*.tar.gz"))
    require(len(archives) == 1, "Expected exactly one release archive")
    archive = archives[0]
    require(archive.name.endswith(".zip" if "windows" in target else ".tar.gz"), "Wrong archive format")
    require((directory / "SHA256SUMS").read_text().strip() == f"{digest(archive)}  {archive.name}",
            "Release archive checksum mismatch")
    files = archive_files(archive)
    require(REQUIRED | {executable, "package-files.json"} <= files.keys(), "Archive lacks required files")
    manifest = json.loads(files["package-files.json"])
    actual = {name: hashlib.sha256(data).hexdigest() for name, data in files.items() if name != "package-files.json"}
    require(manifest == actual, "Archive member checksums or file inventory differ")
    build = json.loads(files["build.json"])
    require(build["source_commit"] == revision and build["target"] == target and build["platform"] == label,
            "Archive source revision or platform differs")
    if run_id is not None:
        require(str(build["github_run_id"]) == str(run_id), "Archive belongs to another hosted run")
    require(build["binary_sha256"] == actual[executable], "Executable checksum differs")
    require(build["source_archive_sha256"] == actual["source.tar.gz"], "Source checksum differs")
    require(build["runtime_libraries"], "Missing runtime library inventory")
    check_binary_header(files[executable][:4096], target)
    licenses = json.loads(files["dependency-licenses.json"])
    require(len(licenses["packages"]) == build["dependency_count"] > 0, "Missing dependency inventory")
    require(all(p["license"] and p["license"] != "Unknown" for p in licenses["packages"]), "Unresolved license")
    require(licenses["notices"] and all(n["text"].strip() for n in licenses["notices"]), "Missing license text")
    require(revision.encode() in files["SOURCE.txt"], "Missing source-access revision")
    verify_source(files["source.tar.gz"], revision)
    return {"target": target, "archive": archive.name, "sha256": digest(archive), "source_commit": revision}


def api(endpoint):
    return json.loads(capture(["gh", "api", f"repos/{REPOSITORY}/{endpoint}"]))


def verify_hosted(run_id):
    require(re.fullmatch(r"[0-9]+", run_id) is not None, "Invalid hosted run ID")
    run = api(f"actions/runs/{run_id}")
    require(run["path"] == ".github/workflows/ci.yml" and run["conclusion"] == "success",
            "Required hosted workflow has not passed")
    revision = run["head_sha"]
    require(not capture(["git", "diff", revision, "HEAD", "--", *INPUTS]),
            "Hosted artifacts do not cover the current declared source inputs")
    jobs = api(f"actions/runs/{run_id}/jobs?per_page=100")["jobs"]
    artifacts = api(f"actions/runs/{run_id}/artifacts?per_page=100")["artifacts"]
    reports = []
    required_steps = {"Check formatting", "Test application and bundled libraries",
                      "Lint application, collectors and model", "Build and package release binary",
                      "Verify release archive", "Upload release archive"}
    with tempfile.TemporaryDirectory(prefix="system-pulse-ci-") as temporary:
        for target, (label, _) in TARGETS.items():
            matches = [j for j in jobs if j["name"] == "Build " + label]
            require(len(matches) == 1 and matches[0]["conclusion"] == "success", "Missing successful job: " + label)
            steps = {s["name"] for s in matches[0]["steps"] if s["conclusion"] == "success"}
            tests = "Test verification and packaging tools" if label.startswith("linux") else "Test portable archive tools"
            require(required_steps | {tests} <= steps, "Required checks did not pass: " + label)
            name = "system-pulse-" + label
            matches = [a for a in artifacts if a["name"] == name and not a["expired"]]
            require(len(matches) == 1 and matches[0]["size_in_bytes"] > 0, "Missing retained artifact: " + name)
            directory = Path(temporary) / label
            subprocess.run(["gh", "run", "download", run_id, "--repo", REPOSITORY,
                            "--name", name, "--dir", str(directory)], cwd=ROOT, timeout=600, check=True)
            reports.append(verify_archive(directory, target, revision, run_id))
    print(json.dumps({"run_url": run["html_url"], "artifacts": reports}, indent=2))
    print("PASS REL-003")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-directory", type=Path)
    parser.add_argument("--target", choices=TARGETS)
    parser.add_argument("--run-id", default=os.environ.get("SYSTEM_PULSE_CI_RUN_ID"))
    args = parser.parse_args()
    if args.archive_directory:
        require(args.target is not None, "Archive validation requires --target")
        print(json.dumps(verify_archive(args.archive_directory, args.target, capture(["git", "rev-parse", "HEAD"]))))
    else:
        require(args.run_id is not None, "Set SYSTEM_PULSE_CI_RUN_ID to a successful hosted workflow run")
        verify_hosted(args.run_id)


if __name__ == "__main__":
    main()
