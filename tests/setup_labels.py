"""User-provided labels must remain text, including template syntax."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import meshcrap
from setup_wizard import configure

with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / 'config.json'
    defaults = json.loads((ROOT / 'config.example.json').read_text())
    answers = iter(['<img src=x onerror=alert(1)> {{7*7}}', '', '', 'y', 'pi',
                    'bridge.example', '4403', '!12345678', 'n', 'n', 'n', 'n', 'y'])
    assert configure(path, defaults, meshcrap.load_config, lambda _: next(answers))
    config, data = meshcrap.load_config(path)
    assert config['radio_host'] == 'bridge.example'
    runtime = meshcrap.initialize(config, data)
    template = (runtime / 'dashboard/templates/index.html').read_text(encoding='utf-8')
    assert '<img src=x' not in template
    assert '{{7*7}}' not in template
    assert '&lt;img src=x onerror=alert(1)&gt; &#123;&#123;7*7&#125;&#125;' in template
    assert not config['enable_radio_controls'] and not config['enable_potato']
print('PASS: Pi wizard configuration and HTML/template injection prevention')
