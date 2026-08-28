SCHEMA_STATEMENTS = (
    """
    CREATE NODE TABLE IF NOT EXISTS Session(
        id STRING PRIMARY KEY,
        title STRING,
        status STRING,
        provider STRING,
        model STRING,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
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
