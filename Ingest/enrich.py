"""Enrich a chunk artifact and save the results without importing vectors."""

import argparse
import sys
from pathlib import Path

from .pipeline import (
    enrich_chunk, enrichment_connection, read_json, resolve_config, validate_artifact, write_json,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output.resolve() in (args.input.resolve(), args.config.resolve()):
            raise ValueError("Output must differ from input and configuration")
        config = resolve_config(read_json(args.config), enrichment_only=True)
        artifact = read_json(args.input)
        validate_artifact(artifact, "chunks", config)
        ollama, timeout = enrichment_connection()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    strategy = config["enrichment"]
    chunk_id = None
    try:
        rows = []
        for source in artifact["chunks"]:
            chunk_id = source["chunk_id"]
            rows.append(enrich_chunk(source, strategy, ollama, timeout))
        chunk_id = None
        write_json(args.output, {**artifact, "stage": "enriched", "enrichment": strategy, "chunks": rows})
    except (OSError, ValueError) as error:
        location = f" for {chunk_id}" if chunk_id else " while writing the artifact"
        print(f"Enrichment failed{location} ({type(error).__name__})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
