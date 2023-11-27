#!/usr/bin/env python3

"""
This script list commits in the LLTC4J dataset[1] that have tangled lines.
A line is tangled when the LLTC4J authors labelled it with more than one type of change.
Commits with tangled lines are outputted on the standard output.

References:
1. Herbold, Steffen, et al. "A fine-grained data set and analysis of tangling in bug fixing commits." Empirical Software Engineering 27.6 (2022): 125.
"""

import argparse
from typing import List

from defaultlist import defaultlist
from pycoshark.mongomodels import (
    Project,
    VCSSystem,
    Commit,
    FileAction,
    Hunk,
    File,
)

from export_lltc4j import connect_to_db
from export_lltc4j import (
    PROJECTS,
    LINE_LABELS_CODE,
    LINE_LABELS_CODE_FIX,
    LINE_LABELS_CODE_NO_FIX,
)


def has_tangled_lines(hunks: List[Hunk], commit_hash: str) -> bool:
    """
    Returns true if the given hunks have at least one tangled line.

    :param hunks: The hunks to check in the commit.
    :param commit_hash: The hash of the commit.
    """
    for hunk in hunks:
        hunk_content_by_line = hunk.content.splitlines()
        line_labels = defaultlist()

        for label, offset_line_numbers in hunk.lines_verified.items():
            for i in offset_line_numbers:
                if line_labels[i]:
                    print(f"Tangled line in {commit_hash}: {hunk_content_by_line[i]}")
                    print(f"Found label {line_labels[i]} and {label}")
                    return True
                line_labels[i] = label
    return False


def has_tangled_hunks(hunks: List[Hunk], commit_hash: str) -> bool:
    """
    Returns true if the given hunks have at least one tangled hunk.

    :param hunks: The hunks to check in the commit.
    :param commit_hash: The hash of the commit.
    """
    for hunk in hunks:
        # If hunk contains only bug fixing changes and non bug fixing changes, return false.
        seen_labels = set()

        for label, _ in hunk.lines_verified.items():
            if label not in LINE_LABELS_CODE:
                continue

            if label in LINE_LABELS_CODE_FIX:
                seen_labels.add("fix")
            elif label in LINE_LABELS_CODE_NO_FIX:
                seen_labels.add("nofix")

            if len(seen_labels) == 2:
                return True
    return False


def is_java_file(file: File) -> bool:
    """
    Returns true if the given file is a Java file.
    """
    return file.path.endswith(".java")


def is_test_file(file: File) -> bool:
    """
    Returns true if the given file is a Java test file.
    """
    return (
        "test/" in file.path
        or "tests/" in file.path
        or file.path.endswith("Test.java")
        or file.path.endswith("Tests.java")
    )


def get_changed_file(fa: FileAction) -> File:
    """
    Returns the changed file from the given file action.
    If the file was renamed, the new file is returned. If the file was deleted,
    the old file is returned.
    """
    if fa.file_id:
        # If the file was renamed, prefer the new file instead of the old file.
        # This behaviour is consistent with the unidiff library we use
        # in our evaluation framework.
        file = File.objects(id=fa.file_id).get()
    else:
        # If there is no file_id, the file was deleted. We use the old_file_id.
        file = File.objects(id=fa.old_file_id).get()
    return file


def is_commit_tangled(commit, tangle_func) -> bool:
    """
    Returns True if the given commit is tangled acording to the given tangle function.
    """
    if (
        commit.labels is not None
        and "validated_bugfix" in commit.labels
        and commit.labels["validated_bugfix"]
        and len(commit.parents) == 1
    ):
        for fa in FileAction.objects(commit_id=commit.id):
            file = get_changed_file(fa)

            if not is_java_file(file) or is_test_file(file):
                continue

            return tangle_func(Hunk.objects(file_action_id=fa.id), commit.revision_hash)
    else:
        return False


def find_tangled_commits(tangle_granularity: str) -> List:
    """
    Finds commits with tangled commits in the LLTC4J dataset. Returns a list of tuples
    (project_name, commit_hash).

    :param tangle_granularity: The granularity of the tangled changes to look for.
    """
    tangle_func = None
    if tangle_granularity == "hunk":
        tangle_func = has_tangled_hunks
    elif tangle_granularity == "line":
        tangle_func = has_tangled_lines
    else:
        raise ValueError(f"Unknown tangle granularity: {tangle_granularity}")

    connect_to_db()

    tangled_commits = []
    for project in Project.objects(name__in=PROJECTS):
        vcs_system = VCSSystem.objects(project_id=project.id).get()
        for commit in Commit.objects(vcs_system_id=vcs_system.id):
            if is_commit_tangled(commit, tangle_func):
                tangled_commits.append((project.name, commit.revision_hash))

    return tangled_commits


def main():
    """
    Implement the logic of the script. See the module docstring.
    """

    main_parser = argparse.ArgumentParser(
        prog="list_tangled_commits.py",
        description="List all commits in the LLTC4J dataset that are tangled.",
    )

    main_parser.add_argument(
        "tangle_granularity",
        choices=["hunk", "line"],
        help="The untangling granularity.",
    )

    args = main_parser.parse_args()

    tangled_commits = find_tangled_commits(args.tangle_granularity)

    for project, commit_hash in tangled_commits:
        print(f"{project} {commit_hash}")


if __name__ == "__main__":
    main()