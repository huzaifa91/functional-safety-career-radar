import json
import re
import sqlite3
import sys

from pathlib import Path

import yaml


# ==========================================================
# Project paths
# ==========================================================

SRC_DIR = Path(__file__).resolve().parents[1]

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR)
    )


from ai.openai_provider import OpenAIProvider


DB_PATH = "data/jobs.db"

CONFIG_FILE = "config.yaml"

AUTO_SAVE_CONFIDENCE = 80

DEFAULT_MINIMUM_PRELIMINARY_SCORE = 35


# ==========================================================
# Load configuration
# ==========================================================

def load_config():

    try:

        with open(
            CONFIG_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            config = yaml.safe_load(
                file
            )

        return config or {}

    except FileNotFoundError:

        return {}


# ==========================================================
# Load minimum preliminary score
# ==========================================================

def get_minimum_preliminary_score():

    config = load_config()

    priority_config = config.get(
        "enrichment_priority",
        {}
    )

    minimum_score = priority_config.get(
        "minimum_preliminary_score",
        DEFAULT_MINIMUM_PRELIMINARY_SCORE
    )

    return int(
        minimum_score
    )


# ==========================================================
# Clean job title
# ==========================================================

def clean_title(title):

    if not title:
        return ""

    title = title.strip()

    replacements = [
        "(m/w/d)",
        "(w/m/d)",
        "(m/f/d)",
        "(f/m/d)",
        "(Mensch)",
        "(human)",
    ]

    for value in replacements:

        title = title.replace(
            value,
            ""
        )

    title = re.sub(
        r"\s+",
        " ",
        title
    )

    return title.strip()


# ==========================================================
# Count eligible pending jobs
# ==========================================================

def count_eligible_pending_jobs(
    minimum_score
):

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM jobs

        WHERE
            (
                original_url IS NULL
                OR TRIM(original_url) = ''
            )

            AND COALESCE(
                description_complete,
                0
            ) = 0

            AND COALESCE(
                url_discovery_attempted,
                0
            ) = 0

            AND COALESCE(
                match_score,
                0
            ) >= ?
        """,
        (
            minimum_score,
        )
    )

    count = cursor.fetchone()[0]

    connection.close()

    return count


# ==========================================================
# Count low-priority pending jobs
# ==========================================================

def count_low_priority_jobs(
    minimum_score
):

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM jobs

        WHERE
            (
                original_url IS NULL
                OR TRIM(original_url) = ''
            )

            AND COALESCE(
                description_complete,
                0
            ) = 0

            AND COALESCE(
                url_discovery_attempted,
                0
            ) = 0

            AND COALESCE(
                match_score,
                0
            ) < ?
        """,
        (
            minimum_score,
        )
    )

    count = cursor.fetchone()[0]

    connection.close()

    return count


# ==========================================================
# Load ONE priority job
# ==========================================================

def load_one_priority_job(
    minimum_score
):

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()

    # ------------------------------------------------------
    # Priority strategy
    #
    # 1. Job must not have an original URL.
    # 2. Job must not have been searched before.
    # 3. Preliminary rule score must meet threshold.
    # 4. Prefer countries with fewer URL-discovery attempts.
    # 5. Within that, prefer highest preliminary score.
    # 6. Prefer newer records if scores are equal.
    # ------------------------------------------------------

    cursor.execute(
        """
        WITH country_activity AS (

            SELECT
                country,

                SUM(
                    CASE
                        WHEN COALESCE(
                            url_discovery_attempted,
                            0
                        ) = 1
                        THEN 1
                        ELSE 0
                    END
                ) AS discovery_attempts

            FROM jobs

            GROUP BY country
        )

        SELECT
            jobs.id,
            jobs.title,
            jobs.company,
            jobs.location,
            jobs.country,
            jobs.url,
            jobs.match_score,

            COALESCE(
                country_activity.discovery_attempts,
                0
            ) AS country_attempts

        FROM jobs

        LEFT JOIN country_activity
            ON country_activity.country
            =
            jobs.country

        WHERE
            (
                jobs.original_url IS NULL
                OR
                TRIM(
                    jobs.original_url
                ) = ''
            )

            AND COALESCE(
                jobs.description_complete,
                0
            ) = 0

            AND COALESCE(
                jobs.url_discovery_attempted,
                0
            ) = 0

            AND COALESCE(
                jobs.match_score,
                0
            ) >= ?

        ORDER BY

            country_attempts ASC,

            COALESCE(
                jobs.match_score,
                0
            ) DESC,

            jobs.id DESC

        LIMIT 1
        """,
        (
            minimum_score,
        )
    )

    job = cursor.fetchone()

    connection.close()

    return job


# ==========================================================
# Build OpenAI Web Search prompt
# ==========================================================

def build_search_prompt(job):

    (
        job_id,
        title,
        company,
        location,
        country,
        adzuna_url,
        match_score,
        country_attempts
    ) = job

    cleaned_title = clean_title(
        title
    )

    return f"""
Search the web for the ORIGINAL employer or company career
page for this specific job vacancy.

JOB TITLE:
{cleaned_title}

COMPANY:
{company}

LOCATION:
{location}

COUNTRY:
{country}


SEARCH RULES:

1. Prefer the official employer or company careers website.

2. The job title does not need to be character-for-character
   identical, but it must describe substantially the same position.

3. The company must match the employer or its verified current brand.

4. The location should reasonably match the supplied location.

5. Do NOT return job aggregator pages such as:
   Adzuna
   Indeed
   LinkedIn
   Glassdoor
   Jooble
   Joblift
   StepStone
   StudySmarter
   ZipRecruiter

6. Prefer an active individual job-detail page rather than
   a generic company careers homepage.

7. Do not invent, construct, or guess a URL.

8. If there is insufficient evidence that a page represents
   the same vacancy, return found=false.

9. If the employer changed branding or ownership,
   explain this in the reason.

10. If multiple official company pages exist,
    select the most specific individual vacancy page.

Return ONLY valid JSON.

Do not return Markdown.

Do not use code fences.

Use exactly this JSON structure:

{{
    "found": true,
    "original_url": "",
    "confidence": 0,
    "reason": ""
}}

confidence must be an integer between 0 and 100.
"""


# ==========================================================
# Clean possible JSON code fences
# ==========================================================

def clean_json_response(response):

    response = response.strip()

    if response.startswith(
        "```json"
    ):

        response = response[7:]

    elif response.startswith(
        "```"
    ):

        response = response[3:]

    if response.endswith(
        "```"
    ):

        response = response[:-3]

    return response.strip()


# ==========================================================
# Validate result
# ==========================================================

def validate_result(result):

    required_fields = [
        "found",
        "original_url",
        "confidence",
        "reason",
    ]

    for field in required_fields:

        if field not in result:

            raise ValueError(
                f"Missing field: {field}"
            )

    if not isinstance(
        result["found"],
        bool
    ):

        raise ValueError(
            "found must be true or false"
        )

    confidence = result[
        "confidence"
    ]

    if not isinstance(
        confidence,
        int
    ):

        raise ValueError(
            "confidence must be an integer"
        )

    if (
        confidence < 0
        or
        confidence > 100
    ):

        raise ValueError(
            "confidence must be between 0 and 100"
        )

    if not isinstance(
        result["reason"],
        str
    ):

        raise ValueError(
            "reason must be a string"
        )

    if result["found"]:

        original_url = result[
            "original_url"
        ]

        if not isinstance(
            original_url,
            str
        ):

            raise ValueError(
                "original_url must be a string"
            )

        if not (
            original_url.startswith(
                "https://"
            )
            or
            original_url.startswith(
                "http://"
            )
        ):

            raise ValueError(
                "original_url is not a valid HTTP URL"
            )


# ==========================================================
# Save discovery result
# ==========================================================

def save_discovery_result(
    job_id,
    found,
    confidence,
    reason,
    original_url=None
):

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE jobs

        SET
            url_discovery_attempted = 1,

            url_discovery_found = ?,

            url_discovery_confidence = ?,

            url_discovery_reason = ?,

            original_url =
                CASE

                    WHEN ? IS NOT NULL
                    THEN ?

                    ELSE original_url

                END

        WHERE id = ?
        """,
        (
            int(found),
            confidence,
            reason,
            original_url,
            original_url,
            job_id,
        )
    )

    connection.commit()

    connection.close()


# ==========================================================
# Main URL discovery
# ==========================================================

def main():

    print()

    print(
        "FuSa Original URL Discovery V4"
    )

    print(
        "=============================="
    )

    minimum_score = (
        get_minimum_preliminary_score()
    )

    eligible_jobs = (
        count_eligible_pending_jobs(
            minimum_score
        )
    )

    low_priority_jobs = (
        count_low_priority_jobs(
            minimum_score
        )
    )

    print()

    print(
        "Minimum preliminary score:",
        minimum_score
    )

    print(
        "Eligible priority jobs:",
        eligible_jobs
    )

    print(
        "Low-priority jobs skipped:",
        low_priority_jobs
    )

    job = load_one_priority_job(
        minimum_score
    )

    if not job:

        print()

        print(
            "No priority jobs waiting "
            "for URL discovery."
        )

        return

    (
        job_id,
        title,
        company,
        location,
        country,
        adzuna_url,
        match_score,
        country_attempts
    ) = job

    print()

    print(
        "Selected priority job"
    )

    print(
        "---------------------"
    )

    print(
        "Database ID:",
        job_id
    )

    print(
        "Job:",
        title
    )

    print(
        "Company:",
        company
    )

    print(
        "Location:",
        location
    )

    print(
        "Country:",
        country
    )

    print(
        "Preliminary score:",
        f"{match_score}%"
    )

    print(
        "Previous URL discoveries "
        "for this country:",
        country_attempts
    )

    prompt = build_search_prompt(
        job
    )

    provider = OpenAIProvider()

    print()

    print(
        "Searching the web..."
    )

    try:

        response = provider.search_web(
            prompt
        )

    except Exception as error:

        print()

        print(
            "ERROR: Web search failed."
        )

        print(
            "Reason:",
            error
        )

        print()

        print(
            "Attempt NOT cached because "
            "the API call failed."
        )

        return

    print()

    print(
        "Search response received."
    )

    try:

        result = json.loads(
            clean_json_response(
                response
            )
        )

        validate_result(
            result
        )

    except (
        json.JSONDecodeError,
        ValueError
    ) as error:

        print()

        print(
            "ERROR: Invalid search response."
        )

        print(
            "Reason:",
            error
        )

        print()

        print(
            "Attempt NOT cached because "
            "the response could not be "
            "safely evaluated."
        )

        return

    found = result[
        "found"
    ]

    confidence = result[
        "confidence"
    ]

    reason = result[
        "reason"
    ]

    original_url = result.get(
        "original_url",
        ""
    )

    print()

    print(
        "Found:",
        found
    )

    print(
        "Confidence:",
        confidence
    )

    print(
        "Reason:",
        reason
    )


    # ======================================================
    # Reliable official URL
    # ======================================================

    if (
        found
        and
        confidence >= AUTO_SAVE_CONFIDENCE
    ):

        save_discovery_result(
            job_id=job_id,
            found=True,
            confidence=confidence,
            reason=reason,
            original_url=original_url
        )

        print()

        print(
            "Original URL:"
        )

        print(
            original_url
        )

        print()

        print(
            "Original URL saved successfully."
        )

        print(
            "Discovery result cached."
        )

        print(
            "This job is ready for "
            "description enrichment."
        )

        return


    # ======================================================
    # Candidate URL but confidence too low
    # ======================================================

    if (
        found
        and
        confidence < AUTO_SAVE_CONFIDENCE
    ):

        save_discovery_result(
            job_id=job_id,
            found=False,
            confidence=confidence,
            reason=(
                "Candidate URL found but "
                "confidence below "
                f"{AUTO_SAVE_CONFIDENCE}. "
                f"{reason}"
            ),
            original_url=None
        )

        print()

        print(
            "Candidate URL rejected because "
            "confidence was below",
            AUTO_SAVE_CONFIDENCE
        )

        print(
            "Discovery attempt cached."
        )

        return


    # ======================================================
    # No reliable URL
    # ======================================================

    save_discovery_result(
        job_id=job_id,
        found=False,
        confidence=confidence,
        reason=reason,
        original_url=None
    )

    print()

    print(
        "No reliable original URL found."
    )

    print(
        "Discovery attempt cached."
    )


# ==========================================================
# Start
# ==========================================================

if __name__ == "__main__":

    main()