import re
from difflib import SequenceMatcher


def normalize_text(text):

    if not text:
        return ""

    text = text.lower().strip()

    # Normalize common title variants
    replacements = {
        "(m/w/d)": "",
        "(w/m/d)": "",
        "(m/f/d)": "",
        "(f/m/d)": "",
        "(mensch)": "",
        "(human)": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove punctuation
    text = re.sub(
        r"[^a-z0-9äöüß\s]",
        " ",
        text
    )

    # Remove repeated spaces
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def title_similarity(
    title1,
    title2
):

    normalized1 = normalize_text(
        title1
    )

    normalized2 = normalize_text(
        title2
    )

    return SequenceMatcher(
        None,
        normalized1,
        normalized2
    ).ratio()


def same_company(
    company1,
    company2
):

    company1 = normalize_text(
        company1
    )

    company2 = normalize_text(
        company2
    )

    return company1 == company2


def jobs_are_duplicates(
    job1,
    job2,
    threshold=0.88
):

    if not same_company(
        job1.company,
        job2.company
    ):
        return False

    similarity = title_similarity(
        job1.title,
        job2.title
    )

    return similarity >= threshold


def deduplicate_jobs(jobs):

    unique_jobs = []

    duplicate_count = 0

    for job in jobs:

        duplicate_found = False

        for existing_job in unique_jobs:

            if jobs_are_duplicates(
                job,
                existing_job
            ):

                duplicate_found = True
                duplicate_count += 1

                break

        if not duplicate_found:
            unique_jobs.append(job)

    return unique_jobs