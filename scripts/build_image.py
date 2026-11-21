"""Build API images from explicit inputs without traversing the workspace."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    'vectorapi': ('Vector/Dockerfile.api', 'Vector/app.py', 'Vector/requirements.txt'),
    'rag-api': ('rag/Dockerfile', 'rag/app.py', 'rag/embedding_config.py', 'rag/ollama_endpoint.py'),
    'reranker': ('reranker/Dockerfile', 'reranker/app.py'),
}
COMMON = ('rag_common/__init__.py', 'rag_common/http_errors.py')


def build_image(service, image):
    """Copy only declared source files; never enumerate tests or historical trees."""
    inputs = INPUTS[service]
    with tempfile.TemporaryDirectory(prefix='rag-build-') as staging:
        for relative in (*inputs, *COMMON):
            destination = Path(staging) / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        subprocess.run(['podman', 'build', '-t', image, '-f', inputs[0], staging],
                       cwd=ROOT, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('service', choices=INPUTS)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    build_image(args.service, args.tag)
