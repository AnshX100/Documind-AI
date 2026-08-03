import json

with open('chat_data.json', encoding='utf-8') as f:
    data = json.load(f)

title = data.get('title', 'Untitled')
print(f'=== CHAT TITLE: {title} ===\n')

mapping = data.get('mapping', {})
messages = []

# Traversal of mapping nodes
for node_id, node in mapping.items():
    msg = node.get('message')
    if not msg:
        continue
    role = msg.get('author', {}).get('role')
    create_time = msg.get('create_time') or 0
    content = msg.get('content', {})
    parts = content.get('parts', [])
    text_parts = []
    for p in parts:
        if isinstance(p, str):
            text_parts.append(p)
        elif isinstance(p, dict) and 'text' in p:
            text_parts.append(p['text'])
    full_text = '\n'.join(text_parts).strip()
    if full_text and role in ['user', 'assistant']:
        messages.append({
            'time': create_time,
            'role': role,
            'text': full_text
        })

# Sort by create_time
messages.sort(key=lambda x: x['time'])

print(f'Total messages extracted: {len(messages)}')

with open('chat_summary.txt', 'w', encoding='utf-8') as out:
    out.write(f'Title: {title}\nTotal Messages: {len(messages)}\n\n')
    for i, m in enumerate(messages, 1):
        out.write(f'=== MESSAGE {i} [{m["role"].upper()}] ===\n{m["text"]}\n\n' + '='*50 + '\n\n')

print('Successfully written chat_summary.txt!')
