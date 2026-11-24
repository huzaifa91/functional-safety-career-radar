import json
import re
import sqlite3
import sys

from html import unescape
from pathlib import Path

import requests
from bs4 import BeautifulSoup


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

MINIMUM_COMPLETE_LENGTH = 1000

MINIMUM_WEB_SUMMARY_LENGTH = 700

MAX_ENRICHMENT_RETRIES = 3


# ==========================================================
# Clean extracted text
# ==========================================================

def clean_text(text):

    if not text:
        return ""

    soup = BeautifulSoup(
        unescape(str(text)),
        "html.parser"
    )

    cleaned_text = soup.get_text(
        separator="\n",
        strip=True
    )

    cleaned_text = re.sub(
        r"\n{3,}",
        "\n\n",
        cleaned_text
    )

    cleaned_text = re.sub(
        r"[ \t]{2,}",
        " ",
        cleaned_text
    )

    return cleaned_text.strip()


# ==========================================================
# Find JobPosting JSON-LD
# ==========================================================

def find_job_posting(data):

    if isinstance(data, dict):

        object_type = data.get(
            "@type"
        )

        if object_type == "JobPosting":
            return data

        if isinstance(
            object_type,
            list
        ):

            if "JobPosting" in object_type:
                return data

        for value in data.values():

            result = find_job_posting(
                value
            )

            if result:
                return result

    elif isinstance(data, list):

        for item in data:

            result = find_job_posting(
                item
            )

            if result:
                return result

    return None


# ==========================================================
# Extract JSON-LD description
# ==========================================================

def extract_json_ld_description(soup):

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        raw_json = script.string

        if not raw_json:
            continue

        try:

            data = json.loads(
                raw_json
            )

        except json.JSONDecodeError:
            continue

        job_posting = find_job_posting(
            data
        )

        if not job_posting:
            continue

        description = clean_text(
            job_posting.get(
                "description",
                ""
            )
        )

        if description:
            return description

    return ""


# ==========================================================
# Extract standard HTML content
# ==========================================================

def extract_main_content(soup):

    for unwanted_tag in soup(
        [
            "script",
            "style",
            "noscript",
            "nav",
            "footer",
            "header",
            "form",
            "svg",
        ]
    ):

        unwanted_tag.decompose()

    selectors = [
        "main",
        "article",
        "[class*='job-description']",
        "[class*='jobDescription']",
        "[class*='job-detail']",
        "[class*='jobDetail']",
        "[class*='description']",
        "[class*='job-content']",
        "[class*='jobContent']",
        "[id*='job-description']",
        "[id*='jobDescription']",
        "[id*='description']",
        "[id*='job-content']",
    ]

    candidates = []

    for selector in selectors:

        elements = soup.select(
            selector
        )

        for element in elements:

            text = clean_text(
                element.get_text(
                    separator="\n",
                    strip=True
                )
            )

            if text:
                candidates.append(
                    text
                )

    if candidates:

        return max(
            candidates,
            key=len
        )

    body = soup.find(
        "body"
    )

    if body:

        return clean_text(
            body.get_text(
                separator="\n",
                strip=True
            )
        )

    return ""


# ==========================================================
# Standard HTTP extraction
# ==========================================================

def fetch_page_description(url):

    headers = {

        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),

        "Accept-Language":
            "de-DE,de;q=0.9,en;q=0.8",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
        allow_redirects=True
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    description = (
        extract_json_ld_description(
            soup
        )
    )

    extraction_method = (
        "JSON-LD JobPosting"
    )

    if (
        len(description)
        <
        MINIMUM_COMPLETE_LENGTH
    ):

        html_description = (
            extract_main_content(
                soup
            )
        )

        if (
            len(html_description)
            >
            len(description)
        ):

            description = (
                html_description
            )

            extraction_method = (
                "HTML content"
            )

    return {

        "description":
            description,

        "final_url":
            response.url,

        "method":
            extraction_method,

        "status_code":
            response.status_code,
    }


# ==========================================================
# Build OpenAI Web Search fallback prompt
# ==========================================================

def build_web_fallback_prompt(
    title,
    company,
    location,
    original_url
):

    return f"""
Use web search to inspect the official job vacancy below.

JOB TITLE:
{title}

COMPANY:
{company}

LOCATION:
{location}

OFFICIAL JOB URL:
{original_url}


The normal HTML extractor could not retrieve a sufficiently
complete job description.

Find and verify the same vacancy and produce a detailed,
structured factual summary.


RULES:

1. Prefer the official employer vacancy.

2. Do not invent requirements.

3. Do not reproduce copyrighted vacancy text verbatim.

4. Paraphrase only information supported by the vacancy.

5. Include all available:
   - Responsibilities
   - Functional Safety standards
   - Safety methods
   - Technical skills
   - Systems/software/hardware requirements
   - Experience requirements
   - Seniority
   - Education
   - Languages
   - Tools
   - Domain knowledge
   - Location
   - Certification requirements

6. If the official page cannot be accessed,
   reliable copies may be used only when the
   company, title and location clearly match.

7. If the vacancy cannot be verified,
   return found=false.

8. The summary must be detailed enough
   for career matching.


Return ONLY valid JSON.

Do not use markdown.

Do not use code fences.

Use exactly:

{{
    "found": true,
    "confidence": 0,
    "source_url": "",
    "summary": "",
    "reason": ""
}}

confidence must be between 0 and 100.
"""


# ==========================================================
# Clean AI JSON
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
# OpenAI Web Search fallback
# ==========================================================

def fetch_with_openai_web_search(
    title,
    company,
    location,
    original_url
):

    provider = OpenAIProvider()

    prompt = build_web_fallback_prompt(
        title,
        company,
        location,
        original_url
    )

    response = provider.search_web(
        prompt
    )

    result = json.loads(
        clean_json_response(
            response
        )
    )

    required_fields = [
        "found",
        "confidence",
        "source_url",
        "summary",
        "reason",
    ]

    for field in required_fields:

        if field not in result:

            raise ValueError(
                f"Missing web fallback field: {field}"
            )

    if not isinstance(
        result["found"],
        bool
    ):

        raise ValueError(
            "found must be true or false"
        )

    if not isinstance(
        result["confidence"],
        int
    ):

        raise ValueError(
            "confidence must be an integer"
        )

    if (
        result["confidence"] < 0
        or
        result["confidence"] > 100
    ):

        raise ValueError(
            "confidence must be between 0 and 100"
        )

    summary = clean_text(
        result["summary"]
    )

    return {

        "found":
            result["found"],

        "confidence":
            result["confidence"],

        "source_url":
            result["source_url"],

        "description":
            summary,

        "reason":
            result["reason"],
    }


# ==========================================================
# Load jobs eligible for enrichment
# ==========================================================

def load_jobs_for_enrichment(
    max_jobs=3
):

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            title,
            company,
            location,
            original_url,
            COALESCE(
                enrichment_attempts,
                0
            )

        FROM jobs

        WHERE original_url IS NOT NULL

          AND TRIM(
              original_url
          ) != ''

          AND COALESCE(
              description_complete,
              0
          ) = 0

          AND COALESCE(
              enrichment_failed,
              0
          ) = 0

          AND COALESCE(
              enrichment_attempts,
              0
          ) < ?

        ORDER BY id

        LIMIT ?
        """,
        (
            MAX_ENRICHMENT_RETRIES,
            max_jobs,
        )
    )

    jobs = cursor.fetchall()

    connection.close()

    return jobs


# ==========================================================
# Record failed attempt
# ==========================================================

def record_failed_attempt(
    job_id,
    error_message
):

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE jobs

        SET
            enrichment_attempts =
                COALESCE(
                    enrichment_attempts,
                    0
                ) + 1,

            enrichment_last_error = ?,

            enrichment_failed =
                CASE

                    WHEN
                        COALESCE(
                            enrichment_attempts,
                            0
                        ) + 1 >= ?

                    THEN 1

                    ELSE 0

                END

        WHERE id = ?
        """,
        (
            str(
                error_message
            ),

            MAX_ENRICHMENT_RETRIES,

            job_id,
        )
    )

    connection.commit()

    connection.close()


# ==========================================================
# Save successful enrichment
# ==========================================================

def update_job_description(
    job_id,
    description,
    source_url,
    method
):

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE jobs

        SET
            description = ?,

            original_url = ?,

            description_complete = 1,

            enrichment_method = ?,

            enrichment_source_url = ?,

            enrichment_attempts =
                COALESCE(
                    enrichment_attempts,
                    0
                ) + 1,

            enrichment_failed = 0,

            enrichment_last_error = NULL

        WHERE id = ?
        """,
        (
            description,
            source_url,
            method,
            source_url,
            job_id,
        )
    )

    connection.commit()

    connection.close()


# ==========================================================
# OpenAI fallback
# ==========================================================

def try_web_search_fallback(
    job_id,
    title,
    company,
    location,
    original_url,
    normal_error
):

    print()

    print(
        "Trying OpenAI Web Search fallback..."
    )

    try:

        web_result = (
            fetch_with_openai_web_search(
                title=title,
                company=company,
                location=location,
                original_url=original_url
            )
        )

    except Exception as error:

        record_failed_attempt(
            job_id,
            (
                f"{normal_error} | "
                f"OpenAI web fallback failed: {error}"
            )
        )

        print(
            "Status: WEB FALLBACK FAILED"
        )

        print(
            "Reason:",
            error
        )

        return False


    description = (
        web_result[
            "description"
        ]
    )

    description_length = len(
        description
    )


    print(
        "Web confidence:",
        web_result[
            "confidence"
        ]
    )

    print(
        "Web summary characters:",
        description_length
    )

    print(
        "Web reason:",
        web_result[
            "reason"
        ]
    )


    if not web_result[
        "found"
    ]:

        record_failed_attempt(
            job_id,
            (
                f"{normal_error} | "
                "Vacancy could not be "
                "verified by web search."
            )
        )

        print(
            "Status: VACANCY NOT VERIFIED"
        )

        return False


    if (
        web_result[
            "confidence"
        ]
        <
        80
    ):

        record_failed_attempt(
            job_id,
            (
                f"{normal_error} | "
                "Web result confidence "
                "was below 80."
            )
        )

        print(
            "Status: WEB CONFIDENCE TOO LOW"
        )

        return False


    if (
        description_length
        <
        MINIMUM_WEB_SUMMARY_LENGTH
    ):

        record_failed_attempt(
            job_id,
            (
                f"{normal_error} | "
                "Web summary too short: "
                f"{description_length}"
            )
        )

        print(
            "Status: WEB SUMMARY TOO SHORT"
        )

        return False


    source_url = (
        web_result[
            "source_url"
        ]
        or
        original_url
    )


    update_job_description(
        job_id=job_id,
        description=description,
        source_url=source_url,
        method=(
            "OpenAI Web Search summary"
        )
    )


    print(
        "Status: DESCRIPTION UPDATED "
        "FROM WEB SEARCH"
    )

    print(
        "Description marked complete."
    )


    return True


# ==========================================================
# Main enrichment function
# ==========================================================

def main(
    max_jobs=3
):

    print()

    print(
        "FuSa Full Description Enrichment V4"
    )

    print(
        "==================================="
    )


    jobs = load_jobs_for_enrichment(
        max_jobs=max_jobs
    )


    print()

    print(
        "Maximum jobs this run:",
        max_jobs
    )

    print(
        "Jobs ready for enrichment:",
        len(jobs)
    )


    if not jobs:

        print()

        print(
            "No enrichment work required."
        )

        return


    processed = 0


    for (
        job_id,
        title,
        company,
        location,
        original_url,
        attempts
    ) in jobs:


        processed += 1


        print()

        print(
            "--------------------------------"
        )

        print(
            "Enrichment job:",
            processed,
            "of",
            len(jobs)
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
            "Previous attempts:",
            attempts
        )

        print(
            "Max retry attempts:",
            MAX_ENRICHMENT_RETRIES
        )

        print(
            "Fetching original job page..."
        )


        normal_error = ""


        try:

            result = fetch_page_description(
                original_url
            )


            description = result[
                "description"
            ]


            description_length = len(
                description
            )


            print(
                "HTTP status:",
                result[
                    "status_code"
                ]
            )


            print(
                "Extraction method:",
                result[
                    "method"
                ]
            )


            print(
                "Extracted characters:",
                description_length
            )


            if (
                description_length
                >=
                MINIMUM_COMPLETE_LENGTH
            ):

                update_job_description(
                    job_id=job_id,
                    description=description,
                    source_url=result[
                        "final_url"
                    ],
                    method=result[
                        "method"
                    ]
                )

                print(
                    "Status: DESCRIPTION UPDATED"
                )

                print(
                    "Description marked complete."
                )

                continue


            normal_error = (
                "Normal extraction returned only "
                f"{description_length} characters."
            )


            print(
                "Normal extraction was insufficient."
            )


        except requests.Timeout as error:

            normal_error = (
                "Normal download timed out: "
                f"{error}"
            )

            print(
                "Normal download timed out."
            )


        except requests.RequestException as error:

            normal_error = (
                "Normal download failed: "
                f"{error}"
            )

            print(
                "Normal download failed."
            )


        except Exception as error:

            normal_error = (
                "Normal extraction failed: "
                f"{error}"
            )

            print(
                "Normal extraction failed."
            )


        try_web_search_fallback(
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            original_url=original_url,
            normal_error=normal_error
        )


    print()

    print(
        "Enrichment jobs processed this run:",
        processed
    )


# ==========================================================
# Start
# ==========================================================

if __name__ == "__main__":

    main()