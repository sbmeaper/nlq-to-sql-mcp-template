# NLQ-to-SQL MCP Server — Project Specification Template

## Overview

An MCP server that enables natural language queries against structured data. Users ask questions in plain English via an MCP client (e.g., Claude Desktop); the server translates these to SQL using a local or cloud LLM, executes against a database, and returns results with diagnostic metrics.

This pattern is applicable to any domain with structured, queryable data: health metrics, sales data, IoT telemetry, financial records, operational logs, etc.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   MCP Client    │────▶│   MCP Server    │────▶│   SQL Builder   │
│ (Claude Desktop)│◀────│    (Python)     │◀────│   LLM (LiteLLM) │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                        ┌────────┴────────┐
                        ▼                 ▼
               ┌─────────────────┐ ┌─────────────────┐
               │    Database     │ │   Query Log     │
               │  (DuckDB/etc)   │ │    (DuckDB)     │
               └─────────────────┘ └─────────────────┘
```

**Components:**

| Component | Role |
|-----------|------|
| MCP Client | User interface; sends natural language questions, displays results |
| MCP Server | Orchestrates flow; manages semantic context, retry logic, logging |
| SQL Builder LLM | Translates NLQ to SQL; uses LiteLLM for provider-agnostic access |
| Database | Executes SQL; returns results |
| Query Log | Audit trail; captures all attempts for analysis and semantic layer refinement |

## Core Flow

1. User asks a natural language question in the MCP client
2. MCP server receives the question
3. Server builds prompt: semantic context + question + prompt structure (per LLM config)
4. Server sends prompt to SQL Builder LLM via LiteLLM
5. LLM returns a SQL SELECT statement
6. Server sanitizes SQL (fixes common LLM generation errors)
7. Server executes SQL against the database
8. If SQL fails, error is sent back to LLM for revision (up to N retries per config)
9. Server logs the attempt (success or failure) with full diagnostics
10. Server returns query results + diagnostic metrics to MCP client
11. MCP client (Claude) formulates the final answer for the user

## Technical Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| Language | Python | |
| MCP Framework | FastMCP | Simplifies MCP server implementation |
| Database | DuckDB | Supports .duckdb files or Parquet/CSV |
| LLM Integration | LiteLLM | Provider-agnostic; supports 100+ LLMs |
| LLM Runtime | Ollama / OpenAI / Anthropic / etc. | Configurable via model string |
| MCP Client | Claude Desktop | Standard MCP protocol; swappable |

## Data Sources

The template supports two data source types:

### DuckDB Database File
```json
"database": {
  "db_path": "~/path/to/data.duckdb",
  "table_name": ""
}
```
- Connects read-only to an existing DuckDB database
- `table_name` auto-discovered if database has exactly one table
- Best for: Data already in DuckDB, or logging databases

### Parquet File
```json
"database": {
  "parquet_path": "/path/to/data.parquet",
  "table_name": "data"
}
```
- Creates in-memory DuckDB connection with a view to the file
- `table_name` becomes the view name (required, defaults to "data")
- Best for: Single-file data exports, columnar analytics data

## Data Schema

[Document the schema for your specific domain]

```sql
CREATE TABLE [table_name] (
    [column_name] [TYPE],    -- [description]
    [column_name] [TYPE],    -- [description]
    ...
);
```

**Key columns:**

| Column | Type | Description |
|--------|------|-------------|
| | | |

## Configuration

JSON configuration file stored in the project root. Structure:

```json
{
  "llm": {
    "model": "ollama/qwen2.5-coder:7b",
    "endpoint": "http://localhost:11434",
    "api_key": "",
    "prompt_format": {
      "structure": "ddl-samples-hints-question",
      "include_sample_rows": true,
      "sample_row_count": 8,
      "hint_style": "sql_comment",
      "response_prefix": "SELECT"
    }
  },
  "database": {
    "db_path": "",
    "parquet_path": "",
    "table_name": "",
    "log_path": "~/path/to/query_logs.duckdb",
    "max_retries": 3
  },
  "semantic_layer": {
    "auto_queries": [],
    "static_context": [
      "=== DATABASE ENGINE ===",
      "DuckDB syntax only.",
      
      "=== QUERY RULES ===",
      "Do not filter on columns unless the question explicitly mentions them.",
      
      "=== TYPE/CATEGORY MAPPINGS ===",
      "[Natural language term] → [database value]",
      
      "=== AGGREGATION RULES ===",
      "[Which columns to SUM vs AVG, special handling notes]"
    ]
  }
}
```

### LLM Configuration

Uses [LiteLLM](https://github.com/BerriAI/litellm) for provider-agnostic LLM calls.

| Setting | Description |
|---------|-------------|
| `model` | LiteLLM model string (e.g., `ollama/qwen2.5-coder:7b`, `anthropic/claude-sonnet-4-5-20250929`, `gpt-4`) |
| `endpoint` | API base URL (required for Ollama, ignored for cloud providers) |
| `api_key` | API key (or set via environment: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.) |

**Example configurations:**

```json
// Local (Ollama)
"model": "ollama/qwen2.5-coder:7b",
"endpoint": "http://localhost:11434"

// Anthropic
"model": "anthropic/claude-sonnet-4-5-20250929",
"api_key": "sk-ant-..."

// OpenAI
"model": "gpt-4",
"api_key": "sk-..."
```

### LLM Prompt Format Options

The `prompt_format` section controls how the semantic context is assembled for the SQL Builder LLM:

| Setting | Options | Description |
|---------|---------|-------------|
| `structure` | `ddl-samples-hints-question` | Order of prompt components |
| `include_sample_rows` | `true`/`false` | Whether to include example data rows |
| `sample_row_count` | integer | Number of sample rows to include |
| `hint_style` | `sql_comment`, `prose`, `json` | How hints are formatted |
| `response_prefix` | string (e.g., `"SELECT"`) | Text to prime the LLM's response |

Different LLMs perform better with different prompt structures. For example:
- **Qwen2.5-Coder**: Trained on DDL → samples → hints → question format
- **GPT-4**: More flexible; prose hints often work well
- **Claude**: Structured context with clear section headers; less prone to sample data confusion

## Semantic Layer

A hybrid approach provides the LLM with data context:

### Auto-Generated (SQL-driven, built at startup)

- Schema introspection (column names, types)
- Distinct values for categorical columns
- Date range of data
- Sample data rows (formatted as CSV for clarity)

### Manually Curated (config-driven)

- Database engine syntax notes
- Natural language → database value mappings
- Aggregation rules (SUM vs AVG)
- Common query patterns
- Domain-specific disambiguation
- Query rules (e.g., "Don't filter unless explicitly mentioned")

The semantic layer is built once at startup and cached in memory. If underlying data changes, restart the MCP server to rebuild.

**Refinement process:** Review query logs periodically to identify failure patterns. Add hints to address recurring misunderstandings.

## MCP Response Structure

Each response includes:

```python
{
    "success": bool,
    "columns": ["col1", "col2", ...],
    "rows": [[val1, val2, ...], ...],
    "row_count": int,
    "diagnostics": {
        "sql": "SELECT ...",
        "retry_count": int,
        "errors": [{"sql": "...", "error": "..."}],
        "input_tokens": int,
        "output_tokens": int
    }
}
```

**Notes:**
- Limit rows returned to prevent overwhelming the MCP client (e.g., max 100)
- Include the generated SQL for transparency and debugging
- Token counts enable cost tracking for cloud LLMs

## Query Logging

All query attempts are logged to a separate database for analysis:

| Column | Type | Description |
|--------|------|-------------|
| request_id | VARCHAR | Groups retry attempts for a single question |
| attempt_number | INTEGER | 1 for initial, 2+ for retries |
| timestamp | TIMESTAMP | When the attempt occurred |
| client | VARCHAR | MCP client name (for multi-client scenarios) |
| nlq | VARCHAR | Original natural language question |
| sql | VARCHAR | Generated SQL |
| success | BOOLEAN | Whether SQL executed without error |
| error_message | VARCHAR | Database error if failed |
| row_count | INTEGER | Rows returned if successful |
| execution_time_ms | INTEGER | Query execution time |
| input_tokens | INTEGER | Tokens sent to LLM for this attempt |
| output_tokens | INTEGER | Tokens received from LLM for this attempt |

**Uses:**
- Identify common failure patterns → refine semantic layer
- Track success rate over time
- Analyze which question types need better hints
- Audit trail for debugging
- Build another NLQ-to-SQL MCP to query your logs!

## SQL Sanitization

Common LLM generation errors to catch before execution:

| Error Pattern | Fix |
|---------------|-----|
| `SELECT WITH cte AS` | Remove leading `SELECT` |
| Multiple trailing semicolons | Reduce to single or none |
| Markdown code fences | Strip ``` wrappers |
| Trailing explanations | Truncate at explanation markers |

Implement these as a sanitization pass before query execution.

## Key Design Decisions

1. **LiteLLM for provider flexibility**: Single interface to 100+ LLM providers; swap via config
2. **Local-first option**: Support local LLM (Ollama) to manage costs and enable offline operation
3. **Multiple data sources**: Support both DuckDB files and Parquet for flexibility
4. **Single table preferred**: Simpler schema = better LLM accuracy; denormalize if needed
5. **Retry with error context**: Pass failed SQL + error back to LLM for self-correction
6. **Semantic layer as prompt engineering**: Most "tuning" happens in config, not code
7. **CSV sample format**: Clearer than Python tuples; reduces LLM confusion with sample values
8. **Protocol-based client**: MCP standard allows swapping frontends without server changes
9. **Logging for learning**: Query logs drive iterative semantic layer improvement

## Implementation Checklist

- [ ] Define data schema and prepare data file/database
- [ ] Create initial config.json with LLM and database settings
- [ ] Implement semantic layer builder (auto-queries + static context)
- [ ] Implement LLM client with prompt assembly per `prompt_format` config
- [ ] Implement query executor with retry logic
- [ ] Implement query logger
- [ ] Implement SQL sanitization
- [ ] Wire up MCP server with tool definition
- [ ] Test with representative questions; refine semantic layer
- [ ] Review query logs; add hints for failure patterns

## File Structure

```
project-root/
├── config.json           # All configuration
├── server.py             # MCP server entry point
├── semantic_layer.py     # Context builder
├── llm_client.py         # LLM communication via LiteLLM
├── query_executor.py     # SQL execution + retry logic
├── query_logger.py       # Audit logging
└── [data files]          # DuckDB, Parquet, or CSV files
```

## Appendix: Sample Static Context Categories

Adapt these categories for your domain:

```
=== DATABASE ENGINE ===
[Syntax notes, function names specific to your DB]

=== SCHEMA ===
[Table and column descriptions]

=== DATE HANDLING ===
[Date formats, casting requirements, common date patterns]

=== QUERY RULES ===
Do not filter on columns unless the question explicitly mentions them.
[Other behavioral guidance for the LLM]

=== TYPE/CATEGORY MAPPINGS ===
[Natural language synonyms → actual database values]

=== AGGREGATION RULES ===
[Which metrics to SUM vs AVG, special calculations]

=== COMMON QUERY PATTERNS ===
[Proven SQL patterns for frequent question types]

=== OUTPUT GUIDELINES ===
[Column aliasing, rounding, ordering conventions]
```