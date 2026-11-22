"""Shared importer/retrieval defaults; set identity is independent of model name."""
import os

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "snowflake-arctic-embed2")
EMBEDDING_SET_ID = os.getenv("EMBEDDING_SET_ID", "snowflake-arctic-embed2-v2")

ANSWER_MODEL = os.getenv("ANSWER_MODEL", "gemma4:e4b")
