import sqlite3
import sys

from pathlib import Path


SRC_DIR = Path(__file__).resolve().parent

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from deduplicator import (
    normalize_text,
    title_similarity,
)


DB_PATH = "data/jobs.db"


def load_jobs():

    connection = sqlite3.connect(DB_PATH)

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            title,
            company,
            description,
            description_complete,
            ai_analyzed,
            ai_match_score
        FROM jobs
        ORDER BY id
        """
    )

    jobs = cursor.fetchall()

    connection.close()

    return jobs


def quality_score(job):

    (
        job_id,
        title,
        company,
        description,
        description_complete,
        ai_analyzed,
        ai_match_score
    ) = job

    score = 0

    if description_complete:
        score += 100

    if ai_analyzed:
        score += 100

    if ai_match_score is not None:
        score += 50

    if description:
        score += min(
            len(description),
            10000
        ) / 1000

    return score


def same_company(company1, company2):

    return (
        normalize_text(company1)
        ==
        normalize_text(company2)
    )


def find_duplicate_groups(jobs):

    groups = []

    processed_ids = set()

    for job in jobs:

        job_id = job[0]

        if job_id in processed_ids:
            continue

        group = [job]

        processed_ids.add(job_id)

        for candidate in jobs:

            candidate_id = candidate[0]

            if candidate_id in processed_ids:
                continue

            if not same_company(
                job[2],
                candidate[2]
            ):
                continue

            similarity = title_similarity(
                job[1],
                candidate[1]
            )

            if similarity >= 0.88:

                group.append(candidate)

                processed_ids.add(
                    candidate_id
                )

        if len(group) > 1:
            groups.append(group)

    return groups


def print_duplicate_groups(groups):

    if not groups:

        print()
        print(
            "No duplicate groups found."
        )

        return


    print()
    print(
        f"Duplicate groups found: {len(groups)}"
    )


    for group_number, group in enumerate(
        groups,
        start=1
    ):

        print()
        print(
            "================================"
        )

        print(
            f"Duplicate Group #{group_number}"
        )

        print(
            "================================"
        )


        sorted_group = sorted(
            group,
            key=quality_score,
            reverse=True
        )


        keep_job = sorted_group[0]


        for job in sorted_group:

            (
                job_id,
                title,
                company,
                description,
                description_complete,
                ai_analyzed,
                ai_match_score
            ) = job


            status = (
                "KEEP"
                if job_id == keep_job[0]
                else "DELETE"
            )


            print()
            print(
                f"[{status}] ID: {job_id}"
            )

            print(
                "Title:",
                title
            )

            print(
                "Company:",
                company
            )

            print(
                "Description complete:",
                description_complete
            )

            print(
                "AI analyzed:",
                ai_analyzed
            )

            print(
                "AI score:",
                ai_match_score
            )

            print(
                "Description length:",
                len(description or "")
            )


def delete_duplicates(groups):

    connection = sqlite3.connect(DB_PATH)

    cursor = connection.cursor()

    deleted = 0


    for group in groups:

        sorted_group = sorted(
            group,
            key=quality_score,
            reverse=True
        )


        keep_job = sorted_group[0]


        duplicates = sorted_group[1:]


        print()
        print(
            "Keeping:",
            keep_job[0],
            "-",
            keep_job[1]
        )


        for duplicate in duplicates:

            duplicate_id = duplicate[0]


            cursor.execute(
                """
                DELETE FROM jobs
                WHERE id = ?
                """,
                (
                    duplicate_id,
                )
            )


            deleted += 1


            print(
                "Deleted duplicate:",
                duplicate_id,
                "-",
                duplicate[1]
            )


    connection.commit()

    connection.close()

    return deleted


def main():

    print()
    print(
        "FuSa Database Duplicate Cleaner"
    )

    print(
        "================================"
    )


    jobs = load_jobs()


    print()
    print(
        "Jobs currently in database:",
        len(jobs)
    )


    groups = find_duplicate_groups(
        jobs
    )


    print_duplicate_groups(
        groups
    )


    if not groups:

        return


    print()
    print(
        "Cleaning duplicate records..."
    )


    deleted = delete_duplicates(
        groups
    )


    print()
    print(
        "Duplicate cleanup completed."
    )

    print(
        "Records deleted:",
        deleted
    )


    remaining_jobs = load_jobs()


    print(
        "Jobs remaining:",
        len(remaining_jobs)
    )


if __name__ == "__main__":

    main()