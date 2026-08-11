with open('docs/REKANVAULT_GOLDEN_SET.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print('Total lines in golden set file:', len(lines))

q_count = 0
cat_counts = {}
for line in lines:
    if line.startswith('| `Q-'):
        q_count += 1
        parts = [p.strip() for p in line.split('|')]
        if len(parts) > 2:
            cat = parts[2]
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

print('Total question rows:', q_count)
print('Category distribution:')
for k, v in sorted(cat_counts.items()):
    print('  -', k, ':', v)
