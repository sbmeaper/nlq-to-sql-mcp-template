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
   pip install duckdb requests mcp
   ```

3. **Ensure Ollama is running** (or configure a cloud LLM)
   ```bash
   ollama pull qwen2.5-coder:7b
   ollama serve
   ```

4. **Update `config.json`**
   - Set `parquet_path` to your data file
   - Set `table_name` to what you want the LLM to call it
   - Set `log_path` for query logging

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

## Files

| File | Purpose |
|------|---------|
| `config.json` | All configuration (LLM, database, semantic layer) |
| `server.py` | MCP server entry point |
| `semantic_layer.py` | Auto-introspects schema, builds prompt context |
| `llm_client.py` | LLM communication, prompt assembly |
| `query_executor.py` | SQL execution, retry logic |
| `query_logger.py` | Audit logging |
| `PROJECT_SPEC.md` | Full architecture documentation |

## Query Logging

All queries are logged to `query_logs.duckdb` with:
- Request ID (groups retries)
- Natural language question
- Generated SQL
- Success/failure + error messages
- Token counts per attempt
- Execution time

Review logs periodically to identify failure patterns and refine your semantic layer hints.

## Switching LLMs

Edit `config.json`:

**Local (Ollama):**
```json
"llm": {
  "provider": "ollama",
  "model": "qwen2.5-coder:7b",
  "endpoint": "http://localhost:11434/api/generate"
}
```

**OpenAI:**
```json
"llm": {
  "provider": "openai",
  "model": "gpt-4",
  "endpoint": "https://api.openai.com/v1/chat/completions",
  "api_key": "sk-..."
}
```

## License

[Your license here]
