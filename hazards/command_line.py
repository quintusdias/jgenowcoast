import argparse
import os

from .hazards import HazardsFile, UGCParsingError


class DirectoryNotFoundException(Exception):
    pass


def hzparse():
    """
    Parse the contents of a directory of bulletins
    """
    description = 'Command line tool for parsing a directory of bulletins.'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('--d', dest='directory', type=str)

    args = parser.parse_args()

    if not os.path.exists(args.directory):
        raise DirectoryNotFoundException

    for file in os.listdir(args.directory):

        # Skip any files with names like ".scour*"
        if file.startswith('.'):
            continue

        try:
            hzf = HazardsFile(os.path.join(args.directory, file))
        except UGCParsingError as e:
            print('File:  {}'.format(file))
            print(e.message)
            continue
        print('File:  {} ({} bulletins)'.format(file, len(hzf)))
