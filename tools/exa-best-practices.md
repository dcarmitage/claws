> ## Documentation Index
> Fetch the complete documentation index at: https://exa.ai/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Search Best Practices

> Best practices for using Exa's Search API

Exa's Search API returns a list of webpages and their contents based on a natural language search query. Results are optimized for LLM consumption, enabling higher-quality completions with clean, token efficent data.

## Key Benefits

* **Token efficient**: Use `highlights` to get key excerpts relevant to your query, reducing token usage by 10x compared to full text, without adding latency.
* **Specialized index coverage**: State of the art search performance on [people](https://exa.ai/blog/people-search-benchmark), [company](https://exa.ai/blog/company-search-benchmarks), and code using Exa's in-house search indexes.
* **Incredible speed**: Providing the fastest search available without compromising on quality, allowing for search to be added to real-time workflows.

## Request Fields

The `query` parameter is required for all search requests. The remaining fields are optional. See the [API Reference](/reference/search) for complete parameter details.

| Field              | Type      | Notes                                                                                                                                   | Example                                        |
| ------------------ | --------- | --------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| query              | string    | The search query. Supports long, semantically rich descriptions for finding niche content.                                              | "blog post about embeddings and vector search" |
| type               | string    | Search method: `auto` (highest quality search), `fast` (high quality and lower latency).                                                | "auto"                                         |
| numResults         | int       | Number of results to return (1-100). Defaults to 10.                                                                                    | 10                                             |
| text               | bool/obj  | Return full page text. Can specify `maxCharacters` and `includeHtmlTags`.                                                               | `true` or `{"maxCharacters": 5000}`            |
| highlights         | bool      | Return token-efficient excerpts most relevant to your query.                                                                            | `true`                                         |
| maxAgeHours        | int       | Maximum age of indexed content in hours. If older, fetches with livecrawl. `0` = always livecrawl, `-1` = never livecrawl (cache only). | 24                                             |
| includeDomains     | string\[] | Only return results from these domains.                                                                                                 | \["arxiv.org", "nature.com"]                   |
| excludeDomains     | string\[] | Exclude results from these domains.                                                                                                     | \["reddit.com", "quora.com"]                   |
| startPublishedDate | string    | Filter to content published after this date (ISO 8601).                                                                                 | "2024-01-01T00:00:00.000Z"                     |
| category           | string    | Target specific content types: `company`, `people`, `tweet`, `news`                                                                     | "company"                                      |
| summary            | bool/obj  | Return LLM-generated summaries. Can specify custom `query` and JSON `schema` for structured extraction.                                 | `{"query": "Key technical contributions"}`     |

## Search Type: Auto vs Fast

The `type` parameter selects the search method:

* **`auto`** (default): Exa's highest quality search.

* **`fast`**: Streamlined, low-latency search. Best for real-time applications where speed is critical.

## Token Efficiency

Choosing the right content mode can significantly reduce token usage while maintaining answer quality.

| Mode       | Best For                                                                 |
| ---------- | ------------------------------------------------------------------------ |
| text       | Deep analysis, when you need full context, comprehensive research        |
| highlights | Factual questions, specific lookups, multi-step agent workflows          |
| summary    | Quick overviews, structured extraction, when you control the output size |

**Use highlights for agentic workflows**: When building multi-step agents that make repeated search calls, highlights provide the most relevant excerpts without flooding context windows.

```json  theme={null}
{
  "query": "What is the current Fed interest rate?",
  "contents": {
    "highlights": true
  },
  // Real-time info requires livecrawl; this may increase latency
  "maxAgeHours": 0
}
```

**Use full text for deep research**: When the task requires comprehensive understanding or when you're unsure which parts of the page matter, request full text. Use `maxCharacters` to cap token usage.

```json  theme={null}
{
  "query": "detailed analysis of transformer architecture innovations",
  "contents": {
    "text": { "maxCharacters": 15000 }
  },
  "numResults": 5
}
```

**Combine modes strategically**: You can request both highlights and text together—use highlights for quick answers and fall back to full text only when needed.

### Verbosity Settings

When using `text`, control how much content is returned with the `verbosity` parameter:

| Content Type                           | Compact | Standard | Full |
| -------------------------------------- | :-----: | :------: | :--: |
| Main body text                         |    ✓    |     ✓    |   ✓  |
| Image placeholders (`![]`, `![alt]`)   |         |     ✓    |   ✓  |
| Infobox/metadata tables                |         |     ✓    |   ✓  |
| Navigation menus                       |         |     ✓    |   ✓  |
| Footer content                         |         |          |   ✓  |
| Legal/copyright notices                |         |          |   ✓  |
| Site-wide links (About, Privacy, etc.) |         |          |   ✓  |

## Content Freshness

Control whether results come from Exa's index or are freshly crawled using `maxAgeHours`:

* **`maxAgeHours: 24`**: Use cache if less than 24 hours old, otherwise livecrawl. Good for daily-fresh content.
* **`maxAgeHours: 1`**: Use cache if less than 1 hour old. Good for near real-time data.
* **`maxAgeHours: 0`**: Always livecrawl (ignore cache). Use when cached data is unacceptable.
* **`maxAgeHours: -1`**: Never livecrawl (cache only). Maximum speed, historical/static content.
* **Omit** *(recommended)*: Default behavior — livecrawl as fallback if no cache exists.

```json  theme={null}
{
  "query": "latest announcements from OpenAI",
  "includeDomains": ["openai.com"],
  "contents": {
    "maxAgeHours": 72,
    "text": true
  }
}
```

## Category Filters

Use `category` to target specific content types where Exa has specialized coverage:

| Category           | Best For                                       |
| ------------------ | ---------------------------------------------- |
| `company`          | Company pages, LinkedIn company profiles       |
| `people`           | Multi-source data on people, LinkedIn profiles |
| `research paper`   | Academic papers, arXiv, peer-reviewed research |
| `news`             | Current events, journalism                     |
| `tweet`            | Posts from X/Twitter                           |
| `personal site`    | Blogs, personal pages (Exa's unique strength)  |
| `financial report` | SEC filings, earnings reports                  |

```json  theme={null}
{
  "query": "agtech companies in the US that have raised series A",
  "type": "auto",
  "category": "company",
  "numResults": 10,
  "contents": {
    "text": true
  }
}
```
