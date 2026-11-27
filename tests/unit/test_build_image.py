"""Build inputs stay independent of inaccessible workspace directories."""
from pathlib import Path
from unittest.mock import Mock

import pytest
from scripts import build_image


@pytest.mark.parametrize('service', build_image.INPUTS)
def test_build_uses_only_declared_files(service, monkeypatch):
    seen = []
    def run(command, **kwargs):
        context = Path(command[-1])
        seen.append(context)
        assert context != build_image.ROOT
        files = {p.relative_to(context).as_posix() for p in context.rglob('*') if p.is_file()}
        assert files == set(build_image.INPUTS[service]) | set(build_image.COMMON)
        assert command[command.index('-f') + 1] == build_image.INPUTS[service][0]
        assert command[command.index('--build-arg') + 1].startswith('RAG_BUILD_TIME=')
        assert kwargs['check'] is True
    monkeypatch.setattr(build_image.subprocess, 'run', run)
    build_image.build_image(service, 'localhost/unit-test:local')
    assert len(seen) == 1
    assert not seen[0].exists()

def test_failed_build_removes_temporary_context(monkeypatch):
    import subprocess
    seen = []
    def fail(command, **kwargs):
        seen.append(Path(command[-1]))
        raise subprocess.CalledProcessError(125, command)
    monkeypatch.setattr(build_image.subprocess, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        build_image.build_image('vectorapi', 'localhost/unit-test:local')
    assert not seen[0].exists()
