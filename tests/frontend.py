"""Compile rendered inline and standalone JavaScript without a browser or radio."""
import importlib.util,json,subprocess,tempfile
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('packaging_cli',ROOT/'meshcrap.py')
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
class Scripts(HTMLParser):
    def __init__(self):super().__init__();self.scripts=[];self.current=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='script' and not attrs.get('src') and attrs.get('type','text/javascript') in ('text/javascript','module'):self.current=''
    def handle_data(self,text):
        if self.current is not None:self.current+=text
    def handle_endtag(self,tag):
        if tag=='script' and self.current is not None:self.scripts.append(self.current);self.current=None
with tempfile.TemporaryDirectory(prefix='meshcrap-js-') as directory:
    base=Path(directory);config=json.loads((ROOT/'config.example.json').read_text());config['data_dir']=str(base/'data')
    path=base/'config.json';path.write_text(json.dumps(config));settings,data=cli.load_config(path);runtime=cli.initialize(settings,data)
    count=0
    for path in runtime.rglob('*'):
        if path.suffix=='.js':subprocess.run(['node','--check',str(path)],check=True);count+=1
        elif path.suffix=='.html':
            parser=Scripts();parser.feed(path.read_text(encoding='utf-8'))
            for script in parser.scripts:
                target=base/'inline.js';target.write_text(script,encoding='utf-8')
                subprocess.run(['node','--check',str(target)],check=True);count+=1
    print('PASS:',count,'rendered JavaScript programs parse')
