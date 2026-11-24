import sqlite3


DB_PATH = "data/jobs.db"


def load_incomplete_jobs():

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

    jobs = cursor.fetchall()

    connection.close()

    incomplete_jobs = []

    for job in jobs:

        job_id, title, company, url, description = job

        description = description or ""

        is_short = len(description.strip()) < 1000

        is_truncated = (
            description.strip().endswith("...")
            or
            description.strip().endswith("…")
        )

        if is_short or is_truncated:

            incomplete_jobs.append(
                {
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "url": url,
                    "description_length": len(description.strip())
                }
            )

    return incomplete_jobs


def main():

    print()
    print("FuSa Job Details Checker")
    print("========================")

    jobs = load_incomplete_jobs()

    print()
    print(
        f"Jobs needing full description: {len(jobs)}"
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
            "Current description length:",
            job["description_length"],
            "characters"
        )

        print(
            "URL:",
            job["url"]
        )

        print(
            "Status: NEEDS FULL DESCRIPTION"
        )


if __name__ == "__main__":
    main()