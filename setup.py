"""Ship the same static UI in wheels; the frontend directory remains the source."""
from pathlib import Path
from shutil import copytree
from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithUI(build_py):
    def run(self):
        super().run()
        source = Path(__file__).parent / 'frontend' / 'public'
        if not (source / 'index.html').is_file():
            raise RuntimeError('Yu+ frontend/public missing from build sources')
        copytree(source, Path(self.build_lib) / 'yuplus' / 'web', dirs_exist_ok=True,
                 ignore=lambda directory, names: [n for n in names if n in {'demo.js','design-fixtures.js','source.html','source.js'}])

setup(cmdclass={'build_py':BuildWithUI})
