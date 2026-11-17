"""Generate opt-in local Codex hooks for this checkout."""
import json
from pathlib import Path
import shlex

root = Path(__file__).resolve().parents[1]
template = json.loads((root / 'integrations/hooks.json').read_text())
command = shlex.join(['/usr/bin/python3', str(root / 'paper/hook.py')])
for groups in template['hooks'].values():
    for group in groups:
        for hook in group['hooks']:
            hook['command'] = command
target = root / '.codex/hooks.json'
target.parent.mkdir(exist_ok=True)
with target.open('x') as out:
    json.dump(template, out, indent=2)
    out.write('\n')
print('Local hooks created. Review and trust them in Codex before use.')
