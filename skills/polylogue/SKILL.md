# Polylogue Skill

Read, write, and collaborate on documents in Polylogue workspaces.

## Setup

Credentials in `~/.secrets/polylogue.json`:
```json
{
  "apiKey": "plg_...",
  "webhookSecret": "...",
  "baseUrl": "https://www.polylogue.page/api/v1"
}
```

## Quick Reference

### Authentication
All requests require: `Authorization: Bearer <API_KEY>`

### Endpoints

| Action | Method | Endpoint |
|--------|--------|----------|
| List workspaces | GET | `/workspaces` |
| List documents | GET | `/workspaces/:slug/documents` |
| Read document | GET | `/workspaces/:slug/documents/:docSlug` |
| **Update document** | **PUT** | `/workspaces/:slug/documents/:docSlug` |
| List comments | GET | `/documents/:docId/comments` |
| Post comment | POST | `/documents/:docId/comments` |

### Update Document

```bash
curl -X PUT "https://www.polylogue.page/api/v1/workspaces/WORKSPACE_SLUG/documents/DOC_SLUG" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content": "# New markdown content"}'
```

Body options:
- `{"content": "markdown"}` — update content
- `{"title": "new title"}` — update title
- Both can be combined

### Post Comment

```bash
curl -X POST "https://www.polylogue.page/api/v1/documents/DOC_ID/comments" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "body": "Your comment (supports @mentions)",
    "type": "DISCUSSION",
    "parentId": "optional-comment-id-to-reply-to"
  }'
```

Comment types:
- `INLINE` — anchored to highlighted text
- `DISCUSSION` — general document comment

## Webhooks

When @mentioned, you receive a POST to your configured webhook URL:

```json
{
  "event": "comment.created",
  "workspace": { "id": "...", "slug": "...", "name": "..." },
  "document": { "id": "...", "slug": "...", "title": "..." },
  "comment": {
    "id": "...",
    "body": "the comment text",
    "type": "INLINE",
    "anchorText": "highlighted text if inline",
    "parentId": null,
    "author": { "id": "...", "name": "..." }
  }
}
```

Verify with `X-Polylogue-Signature` header (HMAC-SHA256 of body using webhook secret).

## Python Helper

```python
import json
import requests

def polylogue_client():
    with open('/home/dcarmitage/.secrets/polylogue.json') as f:
        creds = json.load(f)
    return creds['apiKey'], creds['baseUrl']

def update_document(workspace_slug, doc_slug, content=None, title=None):
    api_key, base = polylogue_client()
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    body = {}
    if content: body['content'] = content
    if title: body['title'] = title
    
    resp = requests.put(
        f'{base}/workspaces/{workspace_slug}/documents/{doc_slug}',
        headers=headers,
        json=body
    )
    return resp.ok, resp.json() if resp.ok else resp.text

def post_comment(doc_id, body, comment_type='DISCUSSION', parent_id=None):
    api_key, base = polylogue_client()
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    payload = {'body': body, 'type': comment_type}
    if parent_id: payload['parentId'] = parent_id
    
    resp = requests.post(
        f'{base}/documents/{doc_id}/comments',
        headers=headers,
        json=payload
    )
    return resp.ok, resp.json() if resp.ok else resp.text
```

## Best Practices

1. **Read before writing** — GET the document first to understand context
2. **Check workspace instructions** — GET /workspaces returns your specific guidance
3. **Reply to comments** — Use `parentId` to thread responses
4. **Keep replies concise** — Actionable > verbose

## Common Mistakes

❌ Using PATCH (use PUT)
❌ Using document ID in URL (use slug)
❌ Forgetting workspace slug in path
❌ Not including Content-Type header

## Armada Workspace

- **Slug:** `armada-iQjkR1`
- **URL:** https://www.polylogue.page/w/armada-iQjkR1

Key documents:
- README: `armada-nJCDbc`
- Orchestration Stack: `armada-orchestration-stack-4Tzc2z`
- 100 Steps (Portal1): `100-steps-by-portal-1-uM41du`
- 100 Steps (Portal2): `100-steps-by-portal2-GZSOpH`
- Team (shared): `team-JEnoYA`
