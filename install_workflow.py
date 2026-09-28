"""One-time setup: materialize the GitHub-required dot-directory after ZIP extraction."""
from pathlib import Path
from shutil import copyfile
root = Path(__file__).resolve().parent
source = root / 'workflow-template/update-and-deploy.yml'
target = root / '.github/workflows/update-and-deploy.yml'
target.parent.mkdir(parents=True, exist_ok=True)
copyfile(source, target)
print(f'Installed {target.relative_to(root)}')
