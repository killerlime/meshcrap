"""Build a standalone, synthetic-only preview without operational app files."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1];out=root/'dist/demo';out.mkdir(parents=True,exist_ok=True)
for p in (root/'demo').iterdir():
    if p.is_file():shutil.copy2(p,out/p.name)
shutil.copytree(root/'source/dashboard/static/vendor',out/'vendor',dirs_exist_ok=True)
(out/'.nojekyll').touch()
print('Standalone demo:',out)
