import os

import requests

from dotenv import load_dotenv
from models import Job


load_dotenv()


APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")


def validate_credentials():

    if not APP_ID:
        raise ValueError(
            "ADZUNA_APP_ID was not found in .env"
        )

    if not APP_KEY:
        raise ValueError(
            "ADZUNA_APP_KEY was not found in .env"
        )


def search_jobs(
    keyword,
    country="de",
    results_per_page=10,
    page=1
):

    validate_credentials()

    url = (
        "https://api.adzuna.com/"
        f"v1/api/jobs/{country}/search/{page}"
    )

    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "what": keyword,
        "results_per_page": results_per_page,
        "content-type": "application/json",
    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    jobs = []

    for item in data.get("results", []):

        job = Job(
            title=item.get(
                "title",
                ""
            ),

            company=item.get(
                "company",
                {}
            ).get(
                "display_name",
                ""
            ),

            location=item.get(
                "location",
                {}
            ).get(
                "display_name",
                ""
            ),

            country=country,

            url=item.get(
                "redirect_url",
                ""
            ),

            description=item.get(
                "description",
                ""
            ),

            source="Adzuna",

            original_url=None,

            description_complete=False,
        )

        jobs.append(job)

    return jobs
