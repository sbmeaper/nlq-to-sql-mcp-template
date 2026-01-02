import json
import duckdb
from pathlib import Path


def load_config(config_path: str = None) -> dict:
    if config_path is None:
        # Get the directory where this script lives
        script_dir = Path(__file__).parent
        config_path = script_dir / "config.json"

    with open(config_path, "r") as f:
        return json.load(f)


def build_semantic_context(config: dict) -> dict:
    """
    Build semantic context with automatic schema introspection.

    Returns a dict with separate components that llm_client can assemble
    into the optimal prompt structure for the configured LLM.
    """

    parquet_path = config["database"]["parquet_path"]
    table_name = config["database"].get("table_name", "data")
    prompt_format = config["llm"].get("prompt_format", {})
    
    con = duckdb.connect()

    context = {
        "schema_ddl": "",
        "sample_data": "",
        "column_info": [],
        "categorical_values": {},
        "date_range": {},
        "hints": []
    }

    # 1. Auto-introspect schema and generate DDL
    try:
        schema_query = f"DESCRIBE SELECT * FROM '{parquet_path}'"
        columns = con.execute(schema_query).fetchall()
        
        ddl_lines = [f"CREATE TABLE {table_name} ("]
        context["column_info"] = []
        
        for i, col in enumerate(columns):
            col_name = col[0]
            col_type = col[1]
            context["column_info"].append({"name": col_name, "type": col_type})
            
            comma = "," if i < len(columns) - 1 else ""
            ddl_lines.append(f"    {col_name} {col_type}{comma}")
        
        ddl_lines.append(");")
        ddl_lines.append(f"-- Query this table as: SELECT ... FROM {table_name} WHERE ...")
        context["schema_ddl"] = "\n".join(ddl_lines)
    except Exception as e:
        context["schema_ddl"] = f"-- Schema introspection failed: {e}"

    # 2. Get sample data rows
    if prompt_format.get("include_sample_rows", True):
        sample_count = prompt_format.get("sample_row_count", 8)
        try:
            sample_query = f"SELECT * FROM '{parquet_path}' ORDER BY RANDOM() LIMIT {sample_count}"
            rows = con.execute(sample_query).fetchall()
            sample_lines = []
            for row in rows:
                sample_lines.append(f"  {row}")
            context["sample_data"] = "\n".join(sample_lines)
        except Exception as e:
            context["sample_data"] = f"  (sample query failed: {e})"

    # 3. Auto-detect categorical columns and get distinct values
    # (string columns with relatively few distinct values)
    try:
        for col_info in context["column_info"]:
            col_name = col_info["name"]
            col_type = col_info["type"]
            
            if col_type == "VARCHAR":
                # Check cardinality
                count_query = f"SELECT COUNT(DISTINCT {col_name}) FROM '{parquet_path}'"
                distinct_count = con.execute(count_query).fetchone()[0]
                
                # Only include if reasonable number of distinct values
                if distinct_count and distinct_count <= 100:
                    values_query = f"SELECT DISTINCT {col_name} FROM '{parquet_path}' WHERE {col_name} IS NOT NULL ORDER BY {col_name} LIMIT 100"
                    values = con.execute(values_query).fetchall()
                    context["categorical_values"][col_name] = [v[0] for v in values]
    except Exception as e:
        pass  # Categorical detection is best-effort

    # 4. Auto-detect date range for timestamp/date columns
    try:
        for col_info in context["column_info"]:
            col_name = col_info["name"]
            col_type = col_info["type"].upper()
            
            if "DATE" in col_type or "TIMESTAMP" in col_type or col_name.endswith("_date"):
                range_query = f"SELECT MIN({col_name}), MAX({col_name}) FROM '{parquet_path}'"
                min_val, max_val = con.execute(range_query).fetchone()
                if min_val and max_val:
                    context["date_range"][col_name] = {"min": str(min_val), "max": str(max_val)}
    except Exception as e:
        pass  # Date range detection is best-effort

    # 5. Run any custom auto-queries from config
    auto_queries = config["semantic_layer"].get("auto_queries", [])
    context["auto_query_results"] = []
    for query_template in auto_queries:
        try:
            query = query_template.replace("{parquet_path}", parquet_path).replace("{table_name}", table_name)
            result = con.execute(query).fetchall()
            context["auto_query_results"].append({
                "query": query_template,
                "result": result
            })
        except Exception as e:
            context["auto_query_results"].append({
                "query": query_template,
                "error": str(e)
            })

    # 6. Add static hints from config
    context["hints"] = config["semantic_layer"].get("static_context", [])

    con.close()
    return context


def format_context_for_prompt(context: dict, config: dict = None) -> str:
    """
    Format the semantic context based on LLM prompt format configuration.
    
    Default format follows Qwen2.5-Coder's text-to-SQL training structure:
    DDL -> Samples -> Hints -> Question
    """
    
    prompt_format = {}
    if config:
        prompt_format = config["llm"].get("prompt_format", {})
    
    hint_style = prompt_format.get("hint_style", "sql_comment")
    
    parts = []

    # Schema as DDL
    parts.append("/* Table Schema */")
    parts.append(context["schema_ddl"])

    # Sample data
    if context.get("sample_data"):
        parts.append("\n/* Sample Data */")
        parts.append(context["sample_data"])

    # Categorical values
    if context.get("categorical_values"):
        parts.append("\n/* Categorical Column Values */")
        for col_name, values in context["categorical_values"].items():
            if len(values) <= 20:
                values_str = ", ".join([f"'{v}'" for v in values])
            else:
                values_str = ", ".join([f"'{v}'" for v in values[:20]]) + f" ... ({len(values)} total)"
            
            if hint_style == "sql_comment":
                parts.append(f"-- {col_name}: {values_str}")
            else:
                parts.append(f"{col_name}: {values_str}")

    # Date ranges
    if context.get("date_range"):
        parts.append("\n/* Date Ranges */")
        for col_name, range_info in context["date_range"].items():
            if hint_style == "sql_comment":
                parts.append(f"-- {col_name}: {range_info['min']} to {range_info['max']}")
            else:
                parts.append(f"{col_name}: {range_info['min']} to {range_info['max']}")

    # Domain hints
    if context.get("hints"):
        parts.append("\n/* Important Notes */")
        for hint in context["hints"]:
            if hint_style == "sql_comment":
                parts.append(f"-- {hint}")
            else:
                parts.append(hint)

    return "\n".join(parts)


if __name__ == "__main__":
    # Test the semantic layer
    config = load_config()
    context = build_semantic_context(config)
    formatted = format_context_for_prompt(context, config)
    print(formatted)
