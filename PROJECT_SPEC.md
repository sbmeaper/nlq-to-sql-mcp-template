# NLQ-to-SQL MCP Server — Project Specification Template

## Overview

An MCP server that enables natural language queries against structured data. Users ask questions in plain English via an MCP client (e.g., Claude Desktop); the server translates these to SQL using a local or cloud LLM, executes against a database, and returns results with diagnostic metrics.

This pattern is applicable to any domain with structured, queryable data: health metrics, sales data, IoT telemetry, financial records, operational logs, etc.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   MCP Client    │────▶│   MCP Server    │────▶│   SQL Builder   │
│ (Claude Desktop)│◀────│    (Python)     │◀────│      LLM        │
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
| SQL Builder LLM | Translates NLQ to SQL; can be local (Ollama) or cloud (OpenAI, Anthropic) |
| Database | Executes SQL; returns results |
| Query Log | Audit trail; captures all attempts for analysis and semantic layer refinement |

## Core Flow

1. User asks a natural language question in the MCP client
2. MCP server receives the question
3. Server builds prompt: semantic context + question + prompt structure (per LLM config)
4. Server sends prompt to SQL Builder LLM
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
| Database | DuckDB | Or PostgreSQL, SQLite, etc. |
| Data Format | [Parquet / CSV / Native] | [Size estimate, update frequency] |
| LLM Runtime | [Ollama / OpenAI / Anthropic] | See LLM configuration section |
| LLM Model | [Model name] | [Memory/compute requirements] |
| MCP Client | Claude Desktop | Standard MCP protocol; swappable |

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
    "provider": "[ollama|openai|anthropic]",
    "model": "[model-name]",
    "endpoint": "[API endpoint URL]",
    "api_key": "[optional, for cloud providers]",
    "prompt_format": {
      "structure": "[ddl-samples-hints-question]",
      "include_sample_rows": true,
      "sample_row_count": 8,
      "hint_style": "[sql_comment|prose|json]",
      "response_prefix": "SELECT"
    }
  },
  "database": {
    "type": "[duckdb|postgresql|sqlite]",
    "connection": "[path or connection string]",
    "log_path": "[path to query log database]",
    "max_retries": 3
  },
  "semantic_layer": {
    "auto_queries": [
      "SELECT DISTINCT [category_column] FROM [table] ORDER BY [category_column]",
      "SELECT MIN([date_column]), MAX([date_column]) FROM [table]",
      "SELECT [category_column], COUNT(*) FROM [table] GROUP BY [category_column]"
    ],
    "static_context": [
      "=== DATABASE ENGINE ===",
      "[Database name] syntax only.",
      
      "=== SCHEMA ===",
      "Table: [table_name]",
      "Columns: [column list with types]",
      
      "=== DATE HANDLING ===",
      "[Date format and query patterns for your database]",
      
      "=== TYPE/CATEGORY MAPPINGS ===",
      "[Natural language term] → [database value]",
      
      "=== AGGREGATION RULES ===",
      "[Which columns to SUM vs AVG, special handling notes]",
      
      "=== COMMON QUERY PATTERNS ===",
      "[Example patterns that work well for your data]"
    ]
  }
}
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
- **Claude**: Structured context with clear section headers

## Semantic Layer

A hybrid approach provides the LLM with data context:

### Auto-Generated (SQL-driven, built at startup)

- Schema introspection (column names, types)
- Distinct values for categorical columns
- Date range of data
- Row counts per category
- Sample data rows

### Manually Curated (config-driven)

- Database engine syntax notes
- Natural language → database value mappings
- Aggregation rules (SUM vs AVG)
- Common query patterns
- Domain-specific disambiguation

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

1. **Local-first option**: Support local LLM (Ollama) to manage costs and enable offline operation
2. **Single table preferred**: Simpler schema = better LLM accuracy; denormalize if needed
3. **Retry with error context**: Pass failed SQL + error back to LLM for self-correction
4. **Semantic layer as prompt engineering**: Most "tuning" happens in config, not code
5. **Protocol-based client**: MCP standard allows swapping frontends without server changes
6. **Logging for learning**: Query logs drive iterative semantic layer improvement

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
├── llm_client.py         # LLM communication + prompt assembly
├── query_executor.py     # SQL execution + retry logic
├── query_logger.py       # Audit logging
└── [data files]          # Parquet, CSV, or database files
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

=== TYPE/CATEGORY MAPPINGS ===
[Natural language synonyms → actual database values]

=== AGGREGATION RULES ===
[Which metrics to SUM vs AVG, special calculations]

=== COMMON QUERY PATTERNS ===
[Proven SQL patterns for frequent question types]

=== OUTPUT GUIDELINES ===
[Column aliasing, rounding, ordering conventions]
```
