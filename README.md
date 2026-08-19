# rei-memory-mcp

Read-only MCP server that lets Rei / Claude query the Rei-AIOS `SEED_KERNEL` (1,677+ theories as of 2026-08-19) by full-text search, ID, or STEP.

**Phase 1 — read only.** No write path is exposed as an MCP tool. Ingestion is a one-shot script; theory additions and promotions belong to Phase 2 (`seed_propose` staging table).

## Design principle

The three-tier taxonomy (`proven` / `hypothesis` / `speculative`) is a **required** schema field. A theory without a tier cannot be ingested. The epidemic-hygiene discipline is enforced by the schema, not by human attention.

## Tools

| Tool | Purpose |
|---|---|
| `seed_search(query, tier?, step_min?, step_max?, limit?)` | FTS5 full-text over title+body. Trigram tokenizer for Japanese. |
| `seed_get(theory_id, include_links?)` | Full body + fan-out links (`depends` / `contradicts` / `generalizes` / `related`). Missing ID → `{"error": "not_found", ...}`. |
| `seed_list_steps(step_min?, step_max?)` | Per-STEP count + tier distribution. Only ~3% of current SEED_KERNEL rows carry a STEP marker; the rest fall under the `step: null` bucket. |

## Setup

Python **3.11+** and SQLite **3.34+** (for FTS5 trigram tokenizer — bundled with Python 3.11+).

```bash
# from repo root
python -m venv .venv
.venv/Scripts/activate            # Windows
source .venv/bin/activate         # Unix
pip install -e '.[dev]'
```

## Building the database

The SEED_KERNEL lives as TypeScript source in `rei-aios/src/axiom-os/seed-kernel*.ts`. Dump it to JSONL, then ingest:

```bash
# 1. dump (run inside the rei-aios repo; script is bundled there)
cd path/to/rei-aios
npx tsx scripts/dump-seed-kernel-json.ts > /path/to/rei-memory-mcp/data/seed-kernel-dump.jsonl

# 2. ingest into SQLite
cd path/to/rei-memory-mcp
python scripts/ingest.py \
    --input data/seed-kernel-dump.jsonl \
    --db    data/seed_kernel.db
```

Both `data/*.jsonl` and `data/*.db` are gitignored — regenerate as needed.

## Running the MCP server

```bash
# stdio transport (default)
python -m rei_memory_mcp.server
# or via console script:
rei-memory-mcp
```

The DB path is picked from `REI_MEMORY_DB` (default: `./data/seed_kernel.db`).

### Claude Desktop configuration

Add to your Claude Desktop MCP settings (adjust paths):

```json
{
  "mcpServers": {
    "rei-memory": {
      "command": "python",
      "args": ["-m", "rei_memory_mcp.server"],
      "cwd": "C:/Users/user/rei-memory-mcp",
      "env": {
        "REI_MEMORY_DB": "C:/Users/user/rei-memory-mcp/data/seed_kernel.db"
      }
    }
  }
}
```

## Tests

```bash
pytest
```

The test on Japanese queries (`test_search.py::test_japanese_query_hits`) is the load-bearing signal — if that fails, the trigram tokenizer is broken and search is silently useless.

## Honest scope

- **Read-only.** No write MCP tool exists on purpose. Wrong memories should not have a fast path to form.
- **Trigram Japanese.** Queries of 2 characters or shorter will not match Japanese text (that is how the trigram tokenizer works). Use 3+ character queries.
- **STEP coverage.** Only ~3% of current SEED_KERNEL entries embed a `STEP N` marker in their body text. `seed_list_steps` faithfully reports this.
- **id shape.** The current SEED_KERNEL mixes three ID patterns (`T-\d+`, `invented-*`, kebab-case slug). All three are accepted; no reshaping.
- **No vector search.** FTS5 trigram is the whole retrieval story in Phase 1. If it turns out to be insufficient, Phase 2 can add embeddings alongside — not replace.

## Roadmap (not implemented)

- **Phase 2** — `seed_propose` staging table + human approval → promotion into `theories`. Direct writes to `theories` will not be exposed as a tool.
- **Phase 3** — promotion history table so the arc of a theory (hypothesis → proven) is itself an artifact.
- **Phase 4** — access-count decay for ranking. `immutable: true` rows are exempt; nothing is ever deleted.

## License

AGPL-3.0 (with commercial dual-license terms — see [LICENSE](LICENSE)). Matches the `rei-aios` main repository.

---

*急がず、ゆっくりと。種は育ちます。*
