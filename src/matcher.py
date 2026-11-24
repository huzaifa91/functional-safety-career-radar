import sqlite3
import yaml


DB_PATH = "data/jobs.db"


# ==========================================================
# Load candidate profile
# ==========================================================

def load_candidate_profile():

    with open(
        "candidate.yaml",
        "r",
        encoding="utf-8"
    ) as file:

        data = yaml.safe_load(file)

    return data["candidate"]


# ==========================================================
# Load jobs from SQLite
# ==========================================================

def load_jobs():

    connection = sqlite3.connect(DB_PATH)

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            title,
            company,
            description
        FROM jobs
        """
    )

    jobs = cursor.fetchall()

    connection.close()

    return jobs


# ==========================================================
# Helper function
# ==========================================================

def contains_any(text, keywords):

    text = text.lower()

    return any(
        keyword.lower() in text
        for keyword in keywords
    )


# ==========================================================
# Calculate match score
# ==========================================================

def calculate_match(
    title,
    description,
    candidate
):

    description = description or ""

    title_text = title.lower()

    full_text = (
        f"{title} {description}"
    ).lower()

    score = 0

    details = []

    matched_standards = []

    matched_skills = []


    # ======================================================
    # 1. TITLE RELEVANCE
    # Maximum: 20 points
    # ======================================================

    title_keywords = [
        "functional safety",
        "system safety",
        "systems safety",
        "safety engineer",
        "safety architect",
        "safety manager",
    ]

    if contains_any(
        title_text,
        title_keywords
    ):

        score += 20

        details.append(
            "Title relevance: +20"
        )


    # ======================================================
    # 2. SAFETY STANDARDS
    # Maximum: 25 points
    # ======================================================

    standards = [
        "iso 26262",
        "iso26262",
        "iec 61508",
        "iec61508",
        "iso 21448",
        "sotif",
    ]

    for standard in standards:

        if standard in full_text:

            matched_standards.append(
                standard
            )

    if matched_standards:

        score += 25

        details.append(
            "Safety standards: +25"
        )


    # ======================================================
    # 3. SAFETY ENGINEERING SKILLS
    # Maximum: 25 points
    # ======================================================

    safety_skills = [
        "hara",
        "fmea",
        "fta",
        "fmeda",
        "dfa",
        "asil",
        "safety case",
        "safety plan",
        "safety requirement",
        "functional safety concept",
        "technical safety concept",
        "fsr",
        "tsr",
    ]

    for skill in safety_skills:

        if skill in full_text:

            matched_skills.append(
                skill
            )

    skill_score = min(
        len(matched_skills) * 5,
        25
    )

    score += skill_score

    if skill_score > 0:

        details.append(
            f"Safety skills: +{skill_score}"
        )


    # ======================================================
    # 4. SENIORITY
    # Maximum: 15 points
    # ======================================================

    seniority_keywords = [
        "principal",
        "senior",
        "lead",
        "manager",
        "architect",
        "expert",
    ]

    if contains_any(
        title_text,
        seniority_keywords
    ):

        score += 15

        details.append(
            "Seniority: +15"
        )


    # ======================================================
    # 5. DOMAIN RELEVANCE
    # Maximum: 10 points
    # ======================================================

    domain_keywords = [
        "automotive",
        "embedded",
        "vehicle",
        "ecu",
        "adas",
        "robot",
        "robotics",
        "semiconductor",
        "soc",
        "control system",
    ]

    if contains_any(
        full_text,
        domain_keywords
    ):

        score += 10

        details.append(
            "Domain relevance: +10"
        )


    # ======================================================
    # 6. CAREER GROWTH
    # Maximum: 5 points
    # ======================================================

    growth_keywords = [
        "robotics",
        "semiconductor",
        "autonomous",
        "ai safety",
        "safety architect",
        "functional safety manager",
    ]

    if contains_any(
        full_text,
        growth_keywords
    ):

        score += 5

        details.append(
            "Career growth: +5"
        )


    # ======================================================
    # Limit final score to 100
    # ======================================================

    score = min(
        score,
        100
    )


    # ======================================================
    # Preliminary recommendation
    # ======================================================

    if score >= 85:

        recommendation = (
            "STRONG APPLY"
        )

    elif score >= 70:

        recommendation = (
            "APPLY"
        )

    elif score >= 55:

        recommendation = (
            "CONSIDER"
        )

    else:

        recommendation = (
            "LOW MATCH"
        )


    # ======================================================
    # Check description quality
    # ======================================================

    description_length = len(
        description.strip()
    )

    description_is_short = (
        description_length < 1000
    )

    description_is_truncated = (
        description.strip().endswith(
            "..."
        )
        or
        description.strip().endswith(
            "…"
        )
    )


    # ======================================================
    # Confidence
    # ======================================================

    if (
        description_is_short
        or
        description_is_truncated
    ):

        confidence = "LOW"

        final_recommendation = (
            "NEEDS FULL DESCRIPTION"
        )

    else:

        confidence = "HIGH"

        final_recommendation = (
            recommendation
        )


    # ======================================================
    # Return analysis
    # ======================================================

    return {

        "score":
            score,

        "recommendation":
            final_recommendation,

        "confidence":
            confidence,

        "description_length":
            description_length,

        "matched_standards":
            matched_standards,

        "matched_skills":
            matched_skills,

        "details":
            details,
    }


# ==========================================================
# Save matcher results into SQLite
# ==========================================================

def save_match_result(
    job_id,
    result
):

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()


    matched_standards = ", ".join(
        result["matched_standards"]
    )

    matched_skills = ", ".join(
        result["matched_skills"]
    )


    cursor.execute(
        """
        UPDATE jobs
        SET
            match_score = ?,
            recommendation = ?,
            confidence = ?,
            matched_standards = ?,
            matched_skills = ?
        WHERE id = ?
        """,
        (
            result["score"],
            result["recommendation"],
            result["confidence"],
            matched_standards,
            matched_skills,
            job_id,
        )
    )


    connection.commit()

    connection.close()


# ==========================================================
# Display result
# ==========================================================

def print_match_result(
    title,
    company,
    result
):

    print()

    print(
        "--------------------------------"
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
        "Match Score:",
        f'{result["score"]}%'
    )

    print(
        "Confidence:",
        result["confidence"]
    )

    print(
        "Recommendation:",
        result["recommendation"]
    )

    print(
        "Description length:",
        result["description_length"],
        "characters"
    )


    # ======================================================
    # Score breakdown
    # ======================================================

    print()

    print(
        "Score breakdown:"
    )

    if result["details"]:

        for detail in result["details"]:

            print(
                " +",
                detail
            )

    else:

        print(
            " No matching criteria found"
        )


    # ======================================================
    # Matched standards
    # ======================================================

    print()

    print(
        "Matched standards:"
    )

    if result["matched_standards"]:

        for standard in result[
            "matched_standards"
        ]:

            print(
                " +",
                standard
            )

    else:

        print(
            " None found"
        )


    # ======================================================
    # Matched safety skills
    # ======================================================

    print()

    print(
        "Matched safety skills:"
    )

    if result["matched_skills"]:

        for skill in result[
            "matched_skills"
        ]:

            print(
                " +",
                skill
            )

    else:

        print(
            " None found"
        )


    # ======================================================
    # Description warning
    # ======================================================

    if result["confidence"] == "LOW":

        print()

        print(
            "NOTE: Job description is incomplete "
            "or too short."
        )

        print(
            "Final match decision cannot "
            "be made yet."
        )


# ==========================================================
# Main
# ==========================================================

def main():

    print()

    print(
        "Starting FuSa Job Matcher..."
    )


    candidate = (
        load_candidate_profile()
    )


    jobs = load_jobs()


    print()

    print(
        "FuSa Job Matcher V4"
    )

    print(
        "==================="
    )


    print(
        f"\nJobs in database: {len(jobs)}"
    )


    for (
        job_id,
        title,
        company,
        description
    ) in jobs:


        result = calculate_match(
            title,
            description,
            candidate
        )


        # Save result into SQLite

        save_match_result(
            job_id,
            result
        )


        # Display result

        print_match_result(
            title,
            company,
            result
        )


    print()

    print(
        "================================"
    )

    print(
        "Matching completed successfully."
    )

    print(
        "Results saved to jobs.db"
    )

    print(
        "================================"
    )


# ==========================================================
# Start program
# ==========================================================

if __name__ == "__main__":

    main()