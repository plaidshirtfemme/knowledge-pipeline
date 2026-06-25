import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import re
from collections import defaultdict
from config import VAULT_PATH

vault = str(VAULT_PATH)
tag_counts = defaultdict(int)
tag_folders = defaultdict(lambda: defaultdict(int))

for root, dirs, files in os.walk(vault):
    for f in files:
        if not f.endswith('.md'):
            continue
        folder = os.path.basename(root)
        try:
            content = open(os.path.join(root, f), encoding='utf-8', errors='ignore').read(3000)
        except:
            continue
        fm_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not fm_match:
            continue
        fm = fm_match.group(1)
        tags_match = re.search(r'tags:\n((?:- .+\n?)+)', fm)
        if not tags_match:
            continue
        for line in tags_match.group(1).splitlines():
            tag = line.strip().lstrip('- ').strip().strip("'\"")
            if tag:
                tag_counts[tag] += 1
                tag_folders[tag][folder] += 1

print(f'Всего уникальных тегов: {len(tag_counts)}')
print()
print(f'{"Тег":<40} {"Кол":>5}  Папки (топ-3)')
print('-'*90)
for tag, cnt in sorted(tag_counts.items(), key=lambda x: -x[1]):
    folders = ', '.join(f'{k}({v})' for k,v in sorted(tag_folders[tag].items(), key=lambda x: -x[1])[:3])
    print(f'{tag:<40} {cnt:>5}  {folders}')
