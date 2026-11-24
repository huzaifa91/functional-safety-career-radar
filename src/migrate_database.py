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


def migrate_database():

    connection = sqlite3.connect(DB_PATH)

    cursor = connection.cursor()

    if not column_exists(
        cursor,
        "jobs",
        "original_url"
    ):

        cursor.execute(
            """
            ALTER TABLE jobs
            ADD COLUMN original_url TEXT
            """
        )

        print(
            "Added column: original_url"
        )

    else:

        print(
            "Column already exists: original_url"
        )


    if not column_exists(
        cursor,
        "jobs",
        "description_complete"
    ):

        cursor.execute(
            """
            ALTER TABLE jobs
            ADD COLUMN description_complete
            INTEGER DEFAULT 0
            """
        )

        print(
            "Added column: description_complete"
        )

    else:

        print(
            "Column already exists: description_complete"
        )


    connection.commit()

    connection.close()


    print()
    print(
        "Database migration completed successfully."
    )


if __name__ == "__main__":

    migrate_database()