# NLQ-to-SQL MCP Server Template

A template for building MCP servers that enable natural language queries against structured data. Clone this repo, point it at your data, and start querying.

## Quick Start

1. **Clone this template**
   ```bash
   git clone <this-repo> my-data-mcp
   cd my-data-mcp
   ```

2. **Install dependencies**
   ```bash
   pip install duckdb litellm mcp
   ```

3. **Choose and configure your LLM**

   This template uses [LiteLLM](https://docs.litellm.ai/docs/providers) for provider-agnostic LLM calls. Pick one:

   <details>
   <summary><strong>Anthropic (Claude)</strong></summary>

   Update `config.json`:
   ```json
   "llm": {
     "model": "anthropic/claude-sonnet-4-5-20250929",
     "endpoint": "",
     "api_key": ""
   }
   ```
   
   Set your API key via environment variable:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```
   Or put it directly in the `api_key` field.
   </details>

   <details>
   <summary><strong>OpenAI (GPT-4)</strong></summary>

   Update `config.json`:
   ```json
   "llm": {
     "model": "gpt-4",
     "endpoint": "",
     "api_key": ""
   }
   ```
   
   Set your API key via environment variable:
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```
   Or put it directly in the `api_key` field.
   </details>

   <details>
   <summary><strong>Ollama (Local)</strong></summary>

   Install and start Ollama:
   ```bash
   ollama pull qwen2.5-coder:7b
   ollama serve
   ```

   Update `config.json`:
   ```json
   "llm": {
     "model": "ollama/qwen2.5-coder:7b",
     "endpoint": "http://localhost:11434",
     "api_key": ""
   }
   ```
   </details>

   <details>
   <summary><strong>Other providers</strong></summary>

   See [LiteLLM supported providers](https://docs.litellm.ai/docs/providers) for the full list (100+ providers supported).
   </details>

4. **Configure your data source**

   Update `config.json` with your database settings:
   
   - Set `db_path` to a DuckDB database file, OR `parquet_path` to a Parquet file
   - Set `table_name` (optional — auto-discovered if database has exactly one table)
   - Set `log_path` for query logging (e.g., `./query_logs.duckdb`)

5. **Test the semantic layer**
   ```bash
   python semantic_layer.py
   ```
   Review the auto-introspected schema and sample data.

6. **Test SQL generation**
   ```bash
   python llm_client.py
   ```

7. **Run the MCP server**
   ```bash
   python server.py
   ```

8. **Configure Claude Desktop** to connect to your server

## Customization

### Essential: Update `config.json`

- **`static_context`**: Add domain-specific mappings and hints
  - Natural language → database value mappings
  - Aggregation rules (which columns to SUM vs AVG)
  - Common query patterns that work well

### Optional: Customize server.py

- Change the server name: `FastMCP("your-domain")`
- Update the tool docstring to describe your data
- Rename `query_data` to something domain-specific

### Optional: Add auto_queries

If you have categorical columns or special data structures, add queries to `auto_queries` that extract useful context at startup.

## Data Sources

The template supports two data source types:

### DuckDB Database File
```json
"database": {
  "db_path": "~/path/to/data.duckdb",
  "table_name": "",
  ...
}
```
- Leave `table_name` empty to auto-discover (works if database has exactly one table)
- Connects read-only to the database file

### Parquet File
```json
"database": {
  "parquet_path": "/path/to/data.parquet",
  "table_name": "data",
  ...
}
```
- Creates an in-memory DuckDB connection with a view to the Parquet file
- `table_name` is used as the view name (defaults to "data")

## Files

| File | Purpose |
|------|---------|
| `config.json` | All configuration (LLM, database, semantic layer) |
| `server.py` | MCP server entry point |
| `semantic_layer.py` | Auto-introspects schema, builds prompt context |
| `llm_client.py` | LLM communication via LiteLLM |
| `query_executor.py` | SQL execution, retry logic |
| `query_logger.py` | Audit logging |
| `PROJECT_SPEC.md` | Full architecture documentation |

## Query Logging

All queries are logged to a DuckDB file (configured via `log_path`) with:
- Request ID (groups retries)
- Natural language question
- Generated SQL
- Success/failure + error messages
- Token counts per attempt
- Execution time

Review logs periodically to identify failure patterns and refine your semantic layer hints.

## License

[Your license here]
