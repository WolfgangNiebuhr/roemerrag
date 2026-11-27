"""Build API images from explicit inputs without traversing the workspace."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    'vectorapi': ('Vector/Dockerfile.api', 'Vector/app.py', 'Vector/requirements.txt',
                  'rag_common/vector_contract.py'),
    'rag-api': ('rag/Dockerfile', 'rag/app.py', 'rag/embedding_config.py', 'rag/ollama_endpoint.py',
                'rag_common/vector_contract.py'),
    'reranker': ('reranker/Dockerfile', 'reranker/app.py'),
}
COMMON = ('rag_common/__init__.py', 'rag_common/http_errors.py', 'rag_common/rag_results.py',
          'rag_common/health.py')


def build_image(service, image):
    """Copy only declared source files; never enumerate tests or historical trees."""
    inputs = INPUTS[service]
    with tempfile.TemporaryDirectory(prefix='rag-build-') as staging:
        for relative in (*inputs, *COMMON):
            destination = Path(staging) / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        built_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
        subprocess.run(['podman', 'build', '-t', image, '-f', inputs[0],
                        '--build-arg', f'RAG_BUILD_TIME={built_at}', staging],
                       cwd=ROOT, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('service', choices=INPUTS)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    build_image(args.service, args.tag)
