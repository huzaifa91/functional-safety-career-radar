import sqlite3
from datetime import datetime
from pathlib import Path


# ==========================================================
# Database path
# ==========================================================

DB_PATH = Path("data/jobs.db")


# ==========================================================
# Complete current database schema
#
# init_database() checks these columns every time the
# application starts.
#
# Missing columns are added automatically.
# ==========================================================

JOB_COLUMNS = {

    # ------------------------------------------------------
    # Core job fields
    # ------------------------------------------------------

    "title":
        "TEXT NOT NULL DEFAULT ''",

    "company":
        "TEXT NOT NULL DEFAULT ''",

    "location":
        "TEXT DEFAULT ''",

    "country":
        "TEXT DEFAULT ''",

    "url":
        "TEXT DEFAULT ''",

    "description":
        "TEXT DEFAULT ''",

    "source":
        "TEXT DEFAULT ''",

    "original_url":
        "TEXT",

    "description_complete":
        "INTEGER DEFAULT 0",

    # ------------------------------------------------------
    # Rule matcher
    # ------------------------------------------------------

    "match_score":
        "INTEGER DEFAULT 0",

    "recommendation":
        "TEXT",

    "confidence":
        "TEXT",

    "matched_standards":
        "TEXT",

    "matched_skills":
        "TEXT",

    # ------------------------------------------------------
    # AI semantic matcher
    # ------------------------------------------------------

    "ai_match_score":
        "INTEGER",

    "ai_recommendation":
        "TEXT",

    "ai_strengths":
        "TEXT",

    "ai_missing_requirements":
        "TEXT",

    "ai_concerns":
        "TEXT",

    "ai_career_growth":
        "TEXT",

    "ai_why_fit":
        "TEXT",

    "ai_analyzed":
        "INTEGER DEFAULT 0",

    # ------------------------------------------------------
    # Original URL discovery
    # ------------------------------------------------------

    "url_discovery_attempted":
        "INTEGER DEFAULT 0",

    "url_discovery_found":
        "INTEGER DEFAULT 0",

    "url_discovery_confidence":
        "INTEGER",

    "url_discovery_reason":
        "TEXT",

    # ------------------------------------------------------
    # Description enrichment
    # ------------------------------------------------------

    "enrichment_attempts":
        "INTEGER DEFAULT 0",

    "enrichment_failed":
        "INTEGER DEFAULT 0",

    "enrichment_last_error":
        "TEXT",

    "enrichment_method":
        "TEXT",

    "enrichment_source_url":
        "TEXT",

    # ------------------------------------------------------
    # Timestamps
    # ------------------------------------------------------

    "created_at":
        "TEXT",

    "updated_at":
        "TEXT",
}


# ==========================================================
# Database connection
# ==========================================================

def get_connection():

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(
        str(DB_PATH)
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    return connection


# ==========================================================
# Get existing table columns
# ==========================================================

def get_table_columns(
    cursor,
    table_name
):

    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )

    columns = {
        row[1]
        for row in cursor.fetchall()
    }

    return columns


# ==========================================================
# Create base jobs table
#
# Start with only the primary key.
# migrate_jobs_table() adds all required columns.
# ==========================================================

def create_jobs_table(cursor):

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (

            id INTEGER PRIMARY KEY AUTOINCREMENT

        )
        """
    )


# ==========================================================
# Automatic schema migration
# ==========================================================

def migrate_jobs_table(cursor):

    existing_columns = get_table_columns(
        cursor,
        "jobs"
    )

    added_columns = []

    for (
        column_name,
        column_definition
    ) in JOB_COLUMNS.items():

        if column_name in existing_columns:
            continue

        cursor.execute(
            f"""
            ALTER TABLE jobs
            ADD COLUMN {column_name}
            {column_definition}
            """
        )

        added_columns.append(
            column_name
        )

    return added_columns


# ==========================================================
# Normalize existing rows
# ==========================================================

def normalize_existing_rows(cursor):

    cursor.execute(
        """
        UPDATE jobs
        SET description_complete = 0
        WHERE description_complete IS NULL
        """
    )

    cursor.execute(
        """
        UPDATE jobs
        SET match_score = 0
        WHERE match_score IS NULL
        """
    )

    cursor.execute(
        """
        UPDATE jobs
        SET ai_analyzed = 0
        WHERE ai_analyzed IS NULL
        """
    )

    cursor.execute(
        """
        UPDATE jobs
        SET url_discovery_attempted = 0
        WHERE url_discovery_attempted IS NULL
        """
    )

    cursor.execute(
        """
        UPDATE jobs
        SET url_discovery_found = 0
        WHERE url_discovery_found IS NULL
        """
    )

    cursor.execute(
        """
        UPDATE jobs
        SET enrichment_attempts = 0
        WHERE enrichment_attempts IS NULL
        """
    )

    cursor.execute(
        """
        UPDATE jobs
        SET enrichment_failed = 0
        WHERE enrichment_failed IS NULL
        """
    )

    now = datetime.utcnow().isoformat(
        timespec="seconds"
    )

    cursor.execute(
        """
        UPDATE jobs
        SET created_at = ?
        WHERE created_at IS NULL
           OR TRIM(created_at) = ''
        """,
        (
            now,
        )
    )

    cursor.execute(
        """
        UPDATE jobs
        SET updated_at = created_at
        WHERE updated_at IS NULL
           OR TRIM(updated_at) = ''
        """
    )


# ==========================================================
# Database indexes
# ==========================================================

def create_indexes(cursor):

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_jobs_company_title
        ON jobs (
            company,
            title
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_jobs_source_url
        ON jobs (
            source,
            url
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_jobs_url_discovery
        ON jobs (
            url_discovery_attempted,
            match_score
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_jobs_enrichment
        ON jobs (
            description_complete,
            enrichment_failed,
            enrichment_attempts
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_jobs_ai_priority
        ON jobs (
            description_complete,
            ai_analyzed,
            match_score
        )
        """
    )


# ==========================================================
# Initialize database
#
# This function is intentionally safe to call repeatedly.
#
# Behavior:
#
# Fresh database:
#   create table
#   add complete schema
#   create indexes
#
# Existing database:
#   preserve existing data
#   detect missing columns
#   add missing columns automatically
# ==========================================================

def init_database():

    connection = get_connection()

    cursor = connection.cursor()

    create_jobs_table(
        cursor
    )

    added_columns = migrate_jobs_table(
        cursor
    )

    normalize_existing_rows(
        cursor
    )

    create_indexes(
        cursor
    )

    connection.commit()

    connection.close()

    if added_columns:

        print()
        print(
            "Database schema updated automatically."
        )

        print(
            "Columns added:"
        )

        for column in added_columns:

            print(
                " +",
                column
            )


# ==========================================================
# Safe attribute reader
# ==========================================================

def get_job_value(
    job,
    attribute,
    default=None
):

    value = getattr(
        job,
        attribute,
        default
    )

    if value is None:
        return default

    return value


# ==========================================================
# Check whether job already exists
# ==========================================================

def job_exists(job):

    init_database()

    title = get_job_value(
        job,
        "title",
        ""
    )

    company = get_job_value(
        job,
        "company",
        ""
    )

    url = get_job_value(
        job,
        "url",
        ""
    )

    source = get_job_value(
        job,
        "source",
        ""
    )

    connection = get_connection()

    cursor = connection.cursor()

    # ------------------------------------------------------
    # First duplicate check:
    # source + URL
    # ------------------------------------------------------

    if url:

        cursor.execute(
            """
            SELECT 1

            FROM jobs

            WHERE LOWER(
                TRIM(
                    COALESCE(
                        source,
                        ''
                    )
                )
            )
            =
            LOWER(
                TRIM(?)
            )

            AND TRIM(
                COALESCE(
                    url,
                    ''
                )
            )
            =
            TRIM(?)

            LIMIT 1
            """,
            (
                source,
                url,
            )
        )

        if cursor.fetchone():

            connection.close()

            return True

    # ------------------------------------------------------
    # Fallback duplicate check:
    # title + company
    # ------------------------------------------------------

    cursor.execute(
        """
        SELECT 1

        FROM jobs

        WHERE LOWER(
            TRIM(
                COALESCE(
                    title,
                    ''
                )
            )
        )
        =
        LOWER(
            TRIM(?)
        )

        AND LOWER(
            TRIM(
                COALESCE(
                    company,
                    ''
                )
            )
        )
        =
        LOWER(
            TRIM(?)
        )

        LIMIT 1
        """,
        (
            title,
            company,
        )
    )

    exists = (
        cursor.fetchone()
        is not None
    )

    connection.close()

    return exists


# ==========================================================
# Save new job
# ==========================================================

def save_job(job):

    init_database()

    now = datetime.utcnow().isoformat(
        timespec="seconds"
    )

    title = get_job_value(
        job,
        "title",
        ""
    )

    company = get_job_value(
        job,
        "company",
        ""
    )

    location = get_job_value(
        job,
        "location",
        ""
    )

    country = get_job_value(
        job,
        "country",
        ""
    )

    url = get_job_value(
        job,
        "url",
        ""
    )

    description = get_job_value(
        job,
        "description",
        ""
    )

    source = get_job_value(
        job,
        "source",
        ""
    )

    original_url = get_job_value(
        job,
        "original_url",
        None
    )

    description_complete = int(
        bool(
            get_job_value(
                job,
                "description_complete",
                False
            )
        )
    )

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO jobs (

            title,
            company,
            location,
            country,
            url,
            description,
            source,
            original_url,
            description_complete,

            match_score,
            ai_analyzed,

            url_discovery_attempted,
            url_discovery_found,

            enrichment_attempts,
            enrichment_failed,

            created_at,
            updated_at

        )

        VALUES (

            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,

            0,
            0,

            0,
            0,

            0,
            0,

            ?,
            ?

        )
        """,
        (
            title,
            company,
            location,
            country,
            url,
            description,
            source,
            original_url,
            description_complete,
            now,
            now,
        )
    )

    connection.commit()

    connection.close()


# ==========================================================
# Database diagnostics
# ==========================================================

def print_database_status():

    init_database()

    connection = get_connection()

    cursor = connection.cursor()

    columns = get_table_columns(
        cursor,
        "jobs"
    )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        """
    )

    job_count = cursor.fetchone()[0]

    connection.close()

    print()
    print(
        "FuSa Database Status"
    )

    print(
        "===================="
    )

    print()

    print(
        "Database:",
        DB_PATH
    )

    print(
        "Jobs:",
        job_count
    )

    print(
        "Columns:",
        len(columns)
    )

    print(
        "Schema status:",
        "READY"
    )

    print()

    important_columns = [
        "original_url",
        "description_complete",
        "match_score",
        "url_discovery_attempted",
        "enrichment_attempts",
        "ai_analyzed",
        "ai_match_score",
    ]

    print(
        "Critical columns:"
    )

    for column in important_columns:

        status = (
            "OK"
            if column in columns
            else "MISSING"
        )

        print(
            f" {column}: {status}"
        )


# ==========================================================
# Direct execution
# ==========================================================

if __name__ == "__main__":

    print_database_status()