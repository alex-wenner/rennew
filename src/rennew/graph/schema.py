SCHEMA_STATEMENTS = (
    """
    CREATE NODE TABLE IF NOT EXISTS Session(
        id STRING PRIMARY KEY,
        title STRING,
        status STRING,
        provider STRING,
        model STRING,
        mode STRING,
        total_input_tokens INT64,
        total_output_tokens INT64,
        total_reasoning_tokens INT64,
        total_cost_usd DOUBLE,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Message(
        id STRING PRIMARY KEY,
        session_id STRING,
        role STRING,
        content STRING,
        reasoning STRING,
        tool_calls_json STRING,
        input_tokens INT64,
        output_tokens INT64,
        reasoning_tokens INT64,
        cost_usd DOUBLE,
        created_at TIMESTAMP
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Handoff(
        id STRING PRIMARY KEY,
        kind STRING,
        status STRING,
        summary STRING,
        created_at TIMESTAMP
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Memory(
        id STRING PRIMARY KEY,
        scope STRING,
        content STRING,
        source STRING,
        confidence DOUBLE,
        created_at TIMESTAMP
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Task(
        id STRING PRIMARY KEY,
        title STRING,
        status STRING,
        created_at TIMESTAMP
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Artifact(
        id STRING PRIMARY KEY,
        kind STRING,
        uri STRING,
        created_at TIMESTAMP
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Compaction(
        id STRING PRIMARY KEY,
        session_id STRING,
        objective STRING,
        completed STRING,
        active STRING,
        blocked STRING,
        next_move STRING,
        relevant_files STRING,
        tokens_saved INT64,
        created_at TIMESTAMP
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS FileChange(
        id STRING PRIMARY KEY,
        session_id STRING,
        message_id STRING,
        tool_call_id STRING,
        path STRING,
        kind STRING,
        before_hash STRING,
        after_hash STRING,
        additions INT64,
        deletions INT64,
        diff STRING,
        created_at TIMESTAMP
    )
    """,
    "CREATE REL TABLE IF NOT EXISTS HAS_MESSAGE(FROM Session TO Message)",
    "CREATE REL TABLE IF NOT EXISTS CHANGED(FROM Session TO FileChange)",
    "CREATE REL TABLE IF NOT EXISTS APPLIED(FROM Message TO FileChange)",
    "CREATE REL TABLE IF NOT EXISTS SENT(FROM Session TO Handoff)",
    "CREATE REL TABLE IF NOT EXISTS RECEIVED_BY(FROM Handoff TO Session)",
    "CREATE REL TABLE IF NOT EXISTS COMPACTED_TO(FROM Session TO Compaction)",
    """
    CREATE REL TABLE IF NOT EXISTS OVERLAPS_WITH(
        FROM Session TO Session,
        kind STRING,
        score DOUBLE,
        evidence STRING,
        inferred BOOL
    )
    """,
    "CREATE REL TABLE IF NOT EXISTS REMEMBERED(FROM Session TO Memory)",
    "CREATE REL TABLE IF NOT EXISTS WORKS_ON(FROM Session TO Task)",
    "CREATE REL TABLE IF NOT EXISTS PRODUCED(FROM Session TO Artifact)",
)

# Ladybug cannot add columns via CREATE TABLE IF NOT EXISTS on existing tables,
# so schema evolution runs as best-effort ALTERs.
MIGRATION_STATEMENTS = (
    "ALTER TABLE Session ADD workspace STRING",
)
