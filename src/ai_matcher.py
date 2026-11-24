import json
import sqlite3

import yaml

from ai.openai_provider import OpenAIProvider


DB_PATH = "data/jobs.db"
CANDIDATE_FILE = "candidate.yaml"
CONFIG_FILE = "config.yaml"

DEFAULT_MINIMUM_RULE_SCORE = 40


# ==========================================================
# Load config
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
# Minimum AI score threshold
# ==========================================================

def get_minimum_rule_score():

    config = load_config()

    ai_priority = config.get(
        "ai_priority",
        {}
    )

    if not isinstance(
        ai_priority,
        dict
    ):

        ai_priority = {}

    return int(
        ai_priority.get(
            "minimum_rule_score",
            DEFAULT_MINIMUM_RULE_SCORE
        )
    )


# ==========================================================
# Load candidate
# ==========================================================

def load_candidate():

    with open(
        CANDIDATE_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = yaml.safe_load(
            file
        )

    return data["candidate"]


# ==========================================================
# Count AI eligible jobs
# ==========================================================

def count_pending_ai_jobs():

    minimum_rule_score = (
        get_minimum_rule_score()
    )

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM jobs

        WHERE
            description_complete = 1

            AND COALESCE(
                ai_analyzed,
                0
            ) = 0

            AND COALESCE(
                match_score,
                0
            ) >= ?
        """,
        (
            minimum_rule_score,
        )
    )

    count = cursor.fetchone()[0]

    connection.close()

    return count


# ==========================================================
# Count completed jobs skipped by AI threshold
# ==========================================================

def count_low_priority_ai_jobs():

    minimum_rule_score = (
        get_minimum_rule_score()
    )

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM jobs

        WHERE
            description_complete = 1

            AND COALESCE(
                ai_analyzed,
                0
            ) = 0

            AND COALESCE(
                match_score,
                0
            ) < ?
        """,
        (
            minimum_rule_score,
        )
    )

    count = cursor.fetchone()[0]

    connection.close()

    return count


# ==========================================================
# Load highest-priority AI job
# ==========================================================

def load_one_pending_job():

    minimum_rule_score = (
        get_minimum_rule_score()
    )

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
            country,
            description,
            match_score,
            recommendation

        FROM jobs

        WHERE
            description_complete = 1

            AND COALESCE(
                ai_analyzed,
                0
            ) = 0

            AND COALESCE(
                match_score,
                0
            ) >= ?

        ORDER BY
            match_score DESC,
            id DESC

        LIMIT 1
        """,
        (
            minimum_rule_score,
        )
    )

    job = cursor.fetchone()

    connection.close()

    return job


# ==========================================================
# Build AI prompt
# ==========================================================

def build_prompt(
    candidate,
    job
):

    (
        job_id,
        title,
        company,
        location,
        country,
        description,
        rule_score,
        rule_recommendation
    ) = job

    candidate_profile_text = (
        yaml.safe_dump(
            candidate,
            allow_unicode=True,
            sort_keys=False
        )
    )

    prompt = f"""
You are an expert Functional Safety career matching assistant.

Evaluate this vacancy against the COMPLETE candidate profile.

Do not simply count keywords.

Perform an independent semantic career assessment.


==================================================
COMPLETE CANDIDATE PROFILE
==================================================

{candidate_profile_text}


==================================================
JOB VACANCY
==================================================

Job Title:
{title}

Company:
{company}

Location:
{location}

Country:
{country}

Rule-Based Match Score:
{rule_score}

Rule-Based Recommendation:
{rule_recommendation}


==================================================
FULL JOB DESCRIPTION
==================================================

{description}


==================================================
EVALUATION RULES
==================================================

1. Do not invent candidate experience.

2. If experience appears anywhere in the candidate profile,
   do not report it as missing.

3. If a requirement cannot be verified from the profile,
   identify it as a gap.

4. Consider:
   - Functional Safety technical fit
   - Standards fit
   - Safety lifecycle
   - Safety analysis
   - Requirements engineering
   - Systems engineering
   - Software / hardware / embedded fit
   - Seniority
   - Domain alignment
   - Required tools
   - Education
   - Certifications
   - Language requirements
   - Location
   - Relocation
   - Work authorization constraints
   - Career growth value

5. Distinguish between:
   - critical blockers
   - learnable gaps
   - desirable requirements

6. Consider whether the role is:
   - career growth
   - appropriate lateral move
   - below candidate seniority

7. The rule score is supporting information only.
   Perform an independent assessment.


==================================================
OUTPUT
==================================================

Return ONLY valid JSON.

Do not include Markdown.

Do not use code fences.

Use exactly:

{{
    "ai_match_score": 0,
    "final_recommendation": "STRONG APPLY",
    "technical_strengths": [],
    "missing_requirements": [],
    "potential_concerns": [],
    "career_growth": "",
    "why_this_job_fits": ""
}}


ai_match_score must be an integer
between 0 and 100.

final_recommendation must be exactly
one of:

STRONG APPLY
APPLY
CONSIDER
SKIP
"""

    return prompt


# ==========================================================
# Clean AI response
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
# Validate AI result
# ==========================================================

def validate_analysis(analysis):

    required_fields = [
        "ai_match_score",
        "final_recommendation",
        "technical_strengths",
        "missing_requirements",
        "potential_concerns",
        "career_growth",
        "why_this_job_fits",
    ]

    for field in required_fields:

        if field not in analysis:

            raise ValueError(
                f"Missing AI response field: {field}"
            )

    score = analysis[
        "ai_match_score"
    ]

    if not isinstance(
        score,
        int
    ):

        raise ValueError(
            "ai_match_score must be an integer"
        )

    if (
        score < 0
        or
        score > 100
    ):

        raise ValueError(
            "ai_match_score must be between 0 and 100"
        )

    valid_recommendations = [
        "STRONG APPLY",
        "APPLY",
        "CONSIDER",
        "SKIP",
    ]

    if (
        analysis[
            "final_recommendation"
        ]
        not in valid_recommendations
    ):

        raise ValueError(
            "Invalid final recommendation"
        )

    list_fields = [
        "technical_strengths",
        "missing_requirements",
        "potential_concerns",
    ]

    for field in list_fields:

        if not isinstance(
            analysis[field],
            list
        ):

            raise ValueError(
                f"{field} must be a list"
            )


# ==========================================================
# Save analysis
# ==========================================================

def save_ai_analysis(
    job_id,
    analysis
):

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()

    strengths = json.dumps(
        analysis[
            "technical_strengths"
        ],
        ensure_ascii=False
    )

    missing = json.dumps(
        analysis[
            "missing_requirements"
        ],
        ensure_ascii=False
    )

    concerns = json.dumps(
        analysis[
            "potential_concerns"
        ],
        ensure_ascii=False
    )

    cursor.execute(
        """
        UPDATE jobs

        SET
            ai_match_score = ?,

            ai_recommendation = ?,

            ai_strengths = ?,

            ai_missing_requirements = ?,

            ai_concerns = ?,

            ai_career_growth = ?,

            ai_why_fit = ?,

            ai_analyzed = 1

        WHERE id = ?
        """,
        (
            analysis[
                "ai_match_score"
            ],

            analysis[
                "final_recommendation"
            ],

            strengths,

            missing,

            concerns,

            analysis[
                "career_growth"
            ],

            analysis[
                "why_this_job_fits"
            ],

            job_id,
        )
    )

    connection.commit()

    connection.close()


# ==========================================================
# Print result
# ==========================================================

def print_analysis(
    job,
    analysis
):

    title = job[1]
    company = job[2]
    rule_score = job[6]
    rule_recommendation = job[7]

    print()

    print(
        "=========================================="
    )

    print(
        "Job:",
        title
    )

    print(
        "Company:",
        company
    )

    print()

    print(
        "Rule Match Score:",
        f"{rule_score}%"
    )

    print(
        "Rule Recommendation:",
        rule_recommendation
    )

    print()

    print(
        "AI Match Score:",
        analysis[
            "ai_match_score"
        ]
    )

    print(
        "AI Recommendation:",
        analysis[
            "final_recommendation"
        ]
    )

    print()

    print(
        "Technical Strengths:"
    )

    for item in analysis[
        "technical_strengths"
    ]:

        print(
            " +",
            item
        )

    print()

    print(
        "Missing Requirements:"
    )

    if analysis[
        "missing_requirements"
    ]:

        for item in analysis[
            "missing_requirements"
        ]:

            print(
                " -",
                item
            )

    else:

        print(
            " None identified"
        )

    print()

    print(
        "Potential Concerns:"
    )

    if analysis[
        "potential_concerns"
    ]:

        for item in analysis[
            "potential_concerns"
        ]:

            print(
                " !",
                item
            )

    else:

        print(
            " None identified"
        )

    print()

    print(
        "Career Growth:"
    )

    print(
        analysis[
            "career_growth"
        ]
    )

    print()

    print(
        "Why This Job Fits:"
    )

    print(
        analysis[
            "why_this_job_fits"
        ]
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    minimum_rule_score = (
        get_minimum_rule_score()
    )

    print()

    print(
        "FuSa AI Matcher V3 - Priority"
    )

    print(
        "============================="
    )

    print()

    print(
        "Minimum rule score for AI:",
        minimum_rule_score
    )

    eligible_jobs = (
        count_pending_ai_jobs()
    )

    skipped_jobs = (
        count_low_priority_ai_jobs()
    )

    print(
        "Eligible jobs waiting for AI:",
        eligible_jobs
    )

    print(
        "Complete low-priority jobs skipped:",
        skipped_jobs
    )

    job = load_one_pending_job()

    if not job:

        print()

        print(
            "No priority jobs waiting "
            "for AI analysis."
        )

        return

    job_id = job[0]
    title = job[1]
    company = job[2]
    rule_score = job[6]

    print()

    print(
        "Selected highest-priority job"
    )

    print(
        "-----------------------------"
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
        "Rule Score:",
        f"{rule_score}%"
    )

    candidate = load_candidate()

    prompt = build_prompt(
        candidate,
        job
    )

    provider = OpenAIProvider()

    print()

    print(
        "Sending job to AI..."
    )

    try:

        response = provider.analyze(
            prompt
        )

    except Exception as error:

        print()

        print(
            "ERROR: AI request failed."
        )

        print(
            "Reason:",
            error
        )

        print()

        print(
            "Job was NOT marked as analyzed."
        )

        return

    print()

    print(
        "AI response received."
    )

    try:

        analysis = json.loads(
            clean_json_response(
                response
            )
        )

        validate_analysis(
            analysis
        )

    except (
        json.JSONDecodeError,
        ValueError
    ) as error:

        print()

        print(
            "ERROR: AI response "
            "validation failed."
        )

        print(
            "Reason:",
            error
        )

        print()

        print(
            "Database was NOT updated."
        )

        return

    save_ai_analysis(
        job_id,
        analysis
    )

    print_analysis(
        job,
        analysis
    )

    print()

    print(
        "=========================================="
    )

    print(
        "AI analysis saved successfully to jobs.db"
    )

    print(
        "This job will not be analyzed again."
    )

    print(
        "=========================================="
    )


if __name__ == "__main__":

    main()