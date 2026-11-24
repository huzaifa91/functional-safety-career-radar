import sqlite3


DB_PATH = "data/jobs.db"


def get_jobs_needing_enrichment():

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            title,
            company,
            url,
            description
        FROM jobs
        """
    )

    rows = cursor.fetchall()

    connection.close()

    jobs = []

    for row in rows:

        job_id, title, company, url, description = row

        description = description or ""

        description_length = len(
            description.strip()
        )

        is_short = (
            description_length < 1000
        )

        is_truncated = (
            description.strip().endswith("...")
            or
            description.strip().endswith("…")
        )

        if is_short or is_truncated:

            jobs.append(
                {
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "url": url,
                    "description": description,
                    "description_length":
                        description_length,
                }
            )

    return jobs


def update_full_description(
    job_id,
    full_description
):

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE jobs
        SET description = ?
        WHERE id = ?
        """,
        (
            full_description,
            job_id
        )
    )

    connection.commit()

    connection.close()


def main():

    print()
    print("FuSa Job Enrichment")
    print("===================")

    jobs = get_jobs_needing_enrichment()

    print()
    print(
        "Jobs requiring enrichment:",
        len(jobs)
    )

    for job in jobs:

        print()
        print("--------------------------------")

        print(
            "Database ID:",
            job["id"]
        )

        print(
            "Job:",
            job["title"]
        )

        print(
            "Company:",
            job["company"]
        )

        print(
            "Description length:",
            job["description_length"]
        )

        print(
            "Status: NEEDS ENRICHMENT"
        )


if __name__ == "__main__":
    main()