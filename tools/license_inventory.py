"""Record the installed Python environment and retain available license texts."""
import argparse, hashlib, importlib.metadata as md, json, re
from pathlib import Path

def inventory(out):
    out.mkdir(parents=True, exist_ok=True)
    rows=[]
    for dist in sorted(md.distributions(), key=lambda d:d.metadata.get('Name','').lower()):
        name=dist.metadata.get('Name','unknown')
        folder=out/(re.sub(r'[^A-Za-z0-9_.-]','_',name)+'-'+dist.version)
        folder.mkdir(exist_ok=True)
        texts=[]
        for file in dist.files or []:
            if not re.match(r'^(license|licence|copying|notice|authors|copyright)([._-]|$)',Path(file).name,re.I):continue
            source=Path(dist.locate_file(file))
            if not source.is_file():continue
            content=source.read_bytes();target=folder/(str(len(texts))+'-'+source.name);target.write_bytes(content)
            texts.append({'path':str(target.relative_to(out)).replace('\\','/'),'sha256':hashlib.sha256(content).hexdigest()})
        (folder/'METADATA.txt').write_text(dist.read_text('METADATA') or dist.read_text('PKG-INFO') or '',encoding='utf-8')
        rows.append({'name':name,'version':dist.version,'license':dist.metadata.get('License-Expression') or dist.metadata.get('License') or 'UNKNOWN','sources':dist.metadata.get_all('Project-URL') or [dist.metadata.get('Home-page','UNKNOWN')],'notices':texts,'review_required':not texts or not (dist.metadata.get('License-Expression') or dist.metadata.get('License'))})
    (out/'inventory.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(f'Recorded {len(rows)} distributions; {sum(r["review_required"] for r in rows)} need notice/metadata review.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);inventory(p.parse_args().output)
