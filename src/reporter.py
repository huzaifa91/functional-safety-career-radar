import sqlite3
from datetime import datetime


DB_PATH = "data/jobs.db"


def load_ranked_jobs():

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            title,
            company,
            location,
            country,
            original_url,
            match_score,
            recommendation,
            confidence,
            matched_standards,
            matched_skills
        FROM jobs
        WHERE match_score IS NOT NULL
        ORDER BY match_score DESC
        """
    )

    jobs = cursor.fetchall()

    connection.close()

    return jobs


def print_job(
    number,
    title,
    company,
    location,
    country,
    original_url,
    match_score,
    recommendation,
    confidence,
    matched_standards,
    matched_skills
):

    print()
    print("--------------------------------------------------")

    print(
        f"#{number} | {match_score}% | {recommendation}"
    )

    print()
    print("Job:", title)
    print("Company:", company)
    print("Location:", location)
    print("Country:", country)
    print("Confidence:", confidence)

    print()
    print("Matched standards:")

    if matched_standards:
        print(
            " +",
            matched_standards
        )
    else:
        print(
            " None"
        )

    print()
    print("Matched skills:")

    if matched_skills:
        print(
            " +",
            matched_skills
        )
    else:
        print(
            " None"
        )

    print()
    print("Job URL:")

    if original_url:
        print(original_url)
    else:
        print("No original URL available")


def main():

    jobs = load_ranked_jobs()

    print()
    print("==================================================")
    print("        FuSa Weekly Job Report")
    print("==================================================")

    print()
    print(
        "Generated:",
        datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )
    )

    print(
        "Jobs analyzed:",
        len(jobs)
    )

    strong_apply = 0
    apply = 0
    consider = 0
    low_match = 0

    for index, job in enumerate(
        jobs,
        start=1
    ):

        (
            title,
            company,
            location,
            country,
            original_url,
            match_score,
            recommendation,
            confidence,
            matched_standards,
            matched_skills
        ) = job


        if recommendation == "STRONG APPLY":
            strong_apply += 1

        elif recommendation == "APPLY":
            apply += 1

        elif recommendation == "CONSIDER":
            consider += 1

        else:
            low_match += 1


        print_job(
            index,
            title,
            company,
            location,
            country,
            original_url,
            match_score,
            recommendation,
            confidence,
            matched_standards,
            matched_skills
        )


    print()
    print("==================================================")
    print("SUMMARY")
    print("==================================================")

    print(
        "STRONG APPLY:",
        strong_apply
    )

    print(
        "APPLY:",
        apply
    )

    print(
        "CONSIDER:",
        consider
    )

    print(
        "LOW MATCH:",
        low_match
    )

    print()
    print(
        "Total:",
        len(jobs)
    )

    print()
    print(
        "Weekly report generated successfully."
    )


if __name__ == "__main__":
    main()