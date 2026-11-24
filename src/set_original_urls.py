import sqlite3


DB_PATH = "data/jobs.db"


ORIGINAL_URLS = {
    1: "https://jungheinrich.onlyfy.jobs/de/job/4x267rb21x7n5fg5uvdavqo2fphtlur",
    2: "https://jobs.neura-robotics.com/de/offer/functional-safety-engineer-mensch/1ecbffe5-b888-4c6d-b488-ea24754ff0c8",
}


def update_original_urls():

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    for job_id, original_url in ORIGINAL_URLS.items():

        cursor.execute(
            """
            UPDATE jobs
            SET original_url = ?
            WHERE id = ?
            """,
            (
                original_url,
                job_id
            )
        )

        print(
            f"Updated original URL for job ID {job_id}"
        )

    connection.commit()
    connection.close()

    print()
    print(
        "Original job URLs updated successfully."
    )


if __name__ == "__main__":
    update_original_urls()