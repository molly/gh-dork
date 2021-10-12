#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import argparse
import os
from dorker import Dorker


def parse_args():
    parser = argparse.ArgumentParser(description="Github dorker")

    parser.add_argument(
        "-d",
        "--dork",
        required=True,
        dest="dorks_filename",
        action="store",
        help="Text file containing dorks, separated by newline",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        action="store",
        help="Directory name for storing results. This will overwrite any directory contents!",
    )
    parser.add_argument(
        "-vif",
        "--valid-items-filename",
        dest="valid_items_filename",
        action="store",
        help="Passing a filename here will allow the script to filter out users or orgs that don't exist and not try to"
        " search against them after the first dork. This improves search performance considerably if you haven't "
        "already removed nonexistent users/orgs from your input lists, and the file can be reused as an user or orgs "
        "input file to prevent such queries later on. This filename will be overwritten if it already exists.",
    )

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "-u",
        "--user",
        dest="user",
        action="store",
        help="Github user to search",
    )
    group.add_argument(
        "-uf",
        "--users-filename",
        dest="users_filename",
        action="store",
        help="Text file containing usernames to search, separated by newline",
    )
    group.add_argument(
        "-org",
        "--org",
        dest="org",
        action="store",
        help="Github organization to search",
    )
    group.add_argument(
        "-of",
        "--orgs-filename",
        dest="orgs_filename",
        action="store",
        help="Text file containing orgs to search, separated by newline",
    )
    group.add_argument(
        "-r",
        "--repo",
        dest="repo",
        action="store",
        help="Github repo to search. For example molly/projectname",
    )

    args = parser.parse_args()

    if not os.path.isfile(args.dorks_filename):
        raise Exception("Dorks file does not exist: " + args.dorks_filename)

    if args.output_dir:
        if not os.path.exists(args.output_dir):
            # Create the output directory if it doesn't exist
            os.mkdir(args.output_dir)
        else:
            # Clear the directory if it does
            files = os.listdir(args.output_dir)
            if len(files) != 0:
                [os.remove(os.path.join(args.output_dir, f)) for f in files]

    if args.valid_items_filename:
        if os.path.exists(args.valid_items_filename):
            os.remove(args.valid_items_filename)

    return {
        "dorks_filename": args.dorks_filename,
        "output_dir": args.output_dir,
        "user": args.user,
        "users_filename": args.users_filename,
        "org": args.org,
        "orgs_filename": args.orgs_filename,
        "repo": args.repo,
        "valid_items_filename": args.valid_items_filename,
    }


if __name__ == "__main__":
    args = parse_args()
    dorker = Dorker(args)
    dorker.run()
