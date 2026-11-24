"""Create a reusable chunk artifact without accessing services."""

import argparse
from pathlib import Path

from .pipeline import make_chunks, read_json, resolve_config, write_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        config = resolve_config(read_json(args.config), chunk_only=True)
        if args.output.resolve() in (args.file.resolve(), args.config.resolve()):
            raise ValueError("Output must differ from source and configuration")
        write_json(args.output, make_chunks(args.file, config))
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
