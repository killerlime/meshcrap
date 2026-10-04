"""Build a standalone, synthetic-only preview without operational app files."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1];out=root/'dist/demo';out.mkdir(parents=True,exist_ok=True)
for p in (root/'demo').iterdir():
    if p.is_file():shutil.copy2(p,out/p.name)
shutil.copytree(root/'source/dashboard/static/vendor',out/'vendor',dirs_exist_ok=True)
import html
notices=(root/'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8')
(out/'licenses.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Sources and licenses</title><body><h1>Sources and licenses</h1><p><a href="index.html">Back to demo</a></p><ul>'+''.join('<li><a href="vendor/'+name+'">'+name+'</a></li>' for name in ['Chart-LICENSE.md','Leaflet-LICENSE','Inter-OFL.txt','JetBrainsMono-OFL.txt','manifest.json'])+'</ul><pre style="white-space:pre-wrap">'+html.escape(notices)+'</pre></body></html>',encoding='utf-8')
shutil.copy2(root/'LICENSE',out/'LICENSE')
shutil.copy2(root/'THIRD_PARTY_NOTICES.md',out/'THIRD_PARTY_NOTICES.md')
(out/'.nojekyll').touch()
print('Standalone demo:',out)
