#!/usr/bin/env python3

"""
This script list commits in the LLTC4J dataset[1] that have tangled lines.
A line is tangled when the LLTC4J authors labelled it with more than one type of change.
Commits with tangled lines are outputted on the standard output.

References:
1. Herbold, Steffen, et al. "A fine-grained data set and analysis of tangling in bug fixing commits." Empirical Software Engineering 27.6 (2022): 125.
"""

from defaultlist import defaultlist
import argparse
import os
import pandas as pd
import sys
from typing import List

from mongoengine import connect
from pycoshark.mongomodels import (
    Project,
    VCSSystem,
    Commit,
    FileAction,
    Hunk,
    File,
)

from export_lltc4j import connect_to_db
from export_lltc4j import PROJECTS


def has_tangled_lines(hunks: List[Hunk], commit_hash: str) -> bool:
    for hunk in hunks:
        hunk_content_by_line = hunk.content.splitlines()
        line_labels = defaultlist()

        for label, offset_line_numbers in hunk.lines_verified.items():
            for i in offset_line_numbers:
                print(f"Line {i} has label {label}, content: {line_labels[i]}")
                if line_labels[i]:
                    print(f"Tangled line in {commit_hash}: {hunk_content_by_line[i]}")
                    print(f"Found label {line_labels[i]} and {label}")
                    return True
                else:
                    line_labels[i] = label  
        print()
    return False


def is_tangled(commit) -> bool:
    """
    Returns True if the given commit is tangled.
    """
    if (
        commit.labels is not None
        and "validated_bugfix" in commit.labels
        and commit.labels["validated_bugfix"]
        and len(commit.parents) == 1
    ):
        for fa in FileAction.objects(commit_id=commit.id):
            file = None

            if fa.old_file_id:
                file = File.objects(id=fa.old_file_id).get()

            if not file or fa.mode == "R":
                # If the file was renamed, prefer the new file instead of the old file.
                # This behaviour is consistent with the unidiff library we use
                # in our evaluation framework.
                file = File.objects(id=fa.file_id).get()

            if (
                not file.path.endswith(".java")
                or file.path.endswith("Test.java")
                or "src/test" in file.path
            ):
                continue

            return has_tangled_lines(Hunk.objects(file_action_id=fa.id), commit.revision_hash)
    else:
        return False
    

def find_tangled_commits():
    """
    Finds commits with tangled lines in the LLTC4J dataset.
    """

    tangled_commits = []

    for project in Project.objects(name__in=PROJECTS):
        print(f"Processing project {project.name}", file=sys.stderr)
        vcs_system = VCSSystem.objects(project_id=project.id).get()
        for commit in Commit.objects(vcs_system_id=vcs_system.id):
            if is_tangled(commit):
                tangled_commits.append((project.name, commit.revision_hash))

    return tangled_commits


def main():
    """
    Implement the logic of the script. See the module docstring.
    """

    connect_to_db()
    tangled_commits = find_tangled_commits()

    for project, commit_hash in tangled_commits:
        print(f"{project} {commit_hash}")


if __name__ == "__main__":
    main()
