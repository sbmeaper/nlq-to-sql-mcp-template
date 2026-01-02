import requests
from typing import Optional


def call_llm(prompt: str, config: dict) -> dict:
    """Send a prompt to the LLM and return the response with diagnostics."""

    provider = config["llm"]["provider"]
    endpoint = config["llm"]["endpoint"]
    model = config["llm"]["model"]

    if provider == "ollama":
        return _call_ollama(prompt, endpoint, model)
    elif provider == "openai":
        api_key = config["llm"].get("api_key", "")
        return _call_openai(prompt, endpoint, model, api_key)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def _call_ollama(prompt: str, endpoint: str, model: str) -> dict:
    """Call Ollama's generate endpoint."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(endpoint, json=payload)
    response.raise_for_status()

    result = response.json()

    return {
        "text": result.get("response", ""),
        "input_tokens": result.get("prompt_eval_count", 0),
        "output_tokens": result.get("eval_count", 0)
    }


def _call_openai(prompt: str, endpoint: str, model: str, api_key: str) -> dict:
    """Call OpenAI-compatible chat completions endpoint."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0
    }

    response = requests.post(endpoint, json=payload, headers=headers)
    response.raise_for_status()

    result = response.json()
    
    return {
        "text": result["choices"][0]["message"]["content"],
        "input_tokens": result.get("usage", {}).get("prompt_tokens", 0),
        "output_tokens": result.get("usage", {}).get("completion_tokens", 0)
    }


def generate_sql(
        question: str,
        semantic_context: str,
        config: dict,
        previous_sql: Optional[str] = None,
        previous_error: Optional[str] = None
) -> dict:
    """
    Generate SQL from a natural language question.

    Prompt structure adapts based on config["llm"]["prompt_format"].
    Default format aligns with Qwen2.5-Coder's text-to-SQL training.

    On retry, includes the failed SQL and error message with explicit fix instructions.
    """

    prompt_format = config["llm"].get("prompt_format", {})
    table_name = config["database"].get("table_name", "data")
    response_prefix = prompt_format.get("response_prefix", "SELECT")

    # Build the core prompt
    base_prompt = f"""Generate a DuckDB SQL query to answer the question based on the schema and data below.

{semantic_context}

/* Query Rules */
-- Return ONLY a valid DuckDB SQL SELECT statement
-- The table is named: {table_name}
-- Use single quotes for strings; escape apostrophes by doubling: 'O''Brien'
-- For date filtering with VARCHAR dates, cast to TIMESTAMP: CAST(date_col AS TIMESTAMP)

Question: {question}"""

    # Add retry context if this is a retry attempt
    if previous_sql and previous_error:
        prompt = f"""{base_prompt}

/* PREVIOUS ATTEMPT FAILED - FIX THE ERROR */
Failed SQL:
{previous_sql}

Error message:
{previous_error}

Analyze the error and generate corrected SQL. Do not repeat the same mistake.

{response_prefix}"""
    else:
        prompt = f"""{base_prompt}

{response_prefix}"""

    result = call_llm(prompt, config)

    # Extract SQL from response
    sql_text = result["text"].strip()

    # Clean markdown formatting FIRST (before prepending response_prefix)
    if "```" in sql_text:
        lines = sql_text.split("\n")
        clean_lines = []
        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            clean_lines.append(line)
        sql_text = "\n".join(clean_lines).strip()

    # The prompt ends with response_prefix so model should continue from there
    # But sometimes model includes it anyway - check before prepending
    if sql_text.upper().startswith(response_prefix.upper()):
        sql = sql_text
    else:
        sql = response_prefix + " " + sql_text

    # Remove any trailing explanation the model might add
    for terminator in ["\n\nThis query", "\n\nExplanation", "\n\nNote:", "\n\n--"]:
        if terminator in sql:
            sql = sql.split(terminator)[0]

    sql = sql.strip()

    # Remove trailing semicolon issues (multiple semicolons)
    while sql.endswith(";;"):
        sql = sql[:-1]

    return {
        "sql": sql,
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"]
    }


if __name__ == "__main__":
    from semantic_layer import load_config, build_semantic_context, format_context_for_prompt

    config = load_config()
    context = build_semantic_context(config)
    formatted_context = format_context_for_prompt(context, config)

    # Test with a simple question
    question = "How many rows are in the table?"
    print(f"Question: {question}\n")

    result = generate_sql(question, formatted_context, config)
    print(f"Generated SQL:\n{result['sql']}\n")
    print(f"Input tokens: {result['input_tokens']}")
    print(f"Output tokens: {result['output_tokens']}")
