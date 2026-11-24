import sqlite3


DB_PATH = "data/jobs.db"


def column_exists(cursor, table, column):

    cursor.execute(
        f"PRAGMA table_info({table})"
    )

    columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    return column in columns


def migrate():

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    columns = {
        "match_score": "INTEGER",
        "recommendation": "TEXT",
        "confidence": "TEXT",
        "matched_standards": "TEXT",
        "matched_skills": "TEXT",
    }

    for column_name, column_type in columns.items():

        if not column_exists(
            cursor,
            "jobs",
            column_name
        ):

            cursor.execute(
                f"""
                ALTER TABLE jobs
                ADD COLUMN {column_name} {column_type}
                """
            )

            print(
                f"Added column: {column_name}"
            )

        else:

            print(
                f"Column already exists: {column_name}"
            )

    connection.commit()
    connection.close()

    print()
    print(
        "Matching database migration completed."
    )


if __name__ == "__main__":
    migrate()