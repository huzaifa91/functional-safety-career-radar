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
        "enrichment_method": "TEXT",
        "enrichment_source_url": "TEXT",
    }

    for column_name, column_type in columns.items():

        if column_exists(
            cursor,
            "jobs",
            column_name
        ):

            print(
                f"Column already exists: {column_name}"
            )

            continue

        cursor.execute(
            f"""
            ALTER TABLE jobs
            ADD COLUMN {column_name} {column_type}
            """
        )

        print(
            f"Added column: {column_name}"
        )

    connection.commit()
    connection.close()

    print()
    print(
        "Enrichment-source migration completed."
    )


if __name__ == "__main__":
    migrate()