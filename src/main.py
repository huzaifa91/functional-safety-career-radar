import json
import sqlite3
import sys
from pathlib import Path

import requests
import yaml


# ==========================================================
# Project paths
# ==========================================================

SRC_DIR = Path(__file__).resolve().parent

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


CONFIG_FILE = "config.yaml"
DB_PATH = "data/jobs.db"
SEARCH_STATE_FILE = Path("data/search_state.json")

DEFAULT_MINIMUM_PRELIMINARY_SCORE = 35
DEFAULT_MINIMUM_AI_RULE_SCORE = 40


# ==========================================================
# Project imports
# ==========================================================

from database import (
    init_database,
    job_exists,
    save_job,
)

from deduplicator import deduplicate_jobs
from searchers.adzuna import search_jobs

from enrichment.url_discovery import (
    main as run_one_url_discovery,
)

from enrichment.full_description import (
    main as run_enrichment,
)

from matcher import (
    main as run_rule_matcher,
)

from ai_matcher import (
    main as run_one_ai_match,
)

from html_reporter import (
    main as generate_html_report,
)


# ==========================================================
# Config
# ==========================================================

def load_config():

    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        config = yaml.safe_load(file)

    if not config:

        raise ValueError(
            "config.yaml is empty"
        )

    return config


def get_minimum_preliminary_score(config):

    priority = config.get(
        "enrichment_priority",
        {}
    )

    if not isinstance(
        priority,
        dict
    ):
        priority = {}

    return int(
        priority.get(
            "minimum_preliminary_score",
            DEFAULT_MINIMUM_PRELIMINARY_SCORE
        )
    )


def get_minimum_ai_rule_score(config):

    priority = config.get(
        "ai_priority",
        {}
    )

    if not isinstance(
        priority,
        dict
    ):
        priority = {}

    return int(
        priority.get(
            "minimum_rule_score",
            DEFAULT_MINIMUM_AI_RULE_SCORE
        )
    )


# ==========================================================
# Countries
# ==========================================================

def load_countries(config):

    groups = config.get(
        "countries",
        {}
    )

    countries = []

    for group_name, codes in groups.items():

        for code in codes:

            countries.append(
                {
                    "group": group_name,
                    "code": code,
                }
            )

    return countries


# ==========================================================
# Persistent Search Cursor
# ==========================================================

def load_search_state():

    if not SEARCH_STATE_FILE.exists():

        return {
            "query_index": 0
        }

    try:

        state = json.loads(
            SEARCH_STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        return {
            "query_index": int(
                state.get(
                    "query_index",
                    0
                )
            )
        }

    except (
        json.JSONDecodeError,
        ValueError,
        TypeError
    ):

        print()
        print(
            "WARNING: search_state.json invalid."
        )

        print(
            "Search cursor reset to 0."
        )

        return {
            "query_index": 0
        }


def save_search_state(query_index):

    SEARCH_STATE_FILE.parent.mkdir(
        exist_ok=True
    )

    SEARCH_STATE_FILE.write_text(
        json.dumps(
            {
                "query_index": query_index
            },
            indent=2
        ),
        encoding="utf-8"
    )


def get_current_query(queries):

    if not queries:

        raise ValueError(
            "No search_queries configured."
        )

    state = load_search_state()

    query_index = state[
        "query_index"
    ]

    if (
        query_index < 0
        or
        query_index >= len(queries)
    ):
        query_index = 0

    return (
        query_index,
        queries[query_index]
    )


def advance_search_cursor(
    current_index,
    query_count
):

    if query_count <= 0:
        return 0

    next_index = (
        current_index + 1
    ) % query_count

    save_search_state(
        next_index
    )

    return next_index


# ==========================================================
# Save new jobs
# ==========================================================

def save_new_jobs(jobs):

    new_jobs = []
    known_count = 0

    for job in jobs:

        if job_exists(job):

            known_count += 1
            continue

        save_job(job)

        new_jobs.append(job)

    return (
        new_jobs,
        known_count
    )


# ==========================================================
# STAGE 1
# Job Search
# ==========================================================

def run_search_stage(config):

    queries = config.get(
        "search_queries",
        []
    )

    countries = load_countries(
        config
    )

    settings = config.get(
        "search_settings",
        {}
    )

    results_per_page = settings.get(
        "results_per_page",
        10
    )

    max_search_calls = settings.get(
        "max_search_calls",
        4
    )

    if not queries:

        raise ValueError(
            "search_queries is empty."
        )

    if not countries:

        raise ValueError(
            "No countries configured."
        )

    (
        query_index,
        current_query
    ) = get_current_query(
        queries
    )

    print()
    print(
        "========================================"
    )
    print(
        "STAGE 1: PERSISTENT ROUND-ROBIN SEARCH"
    )
    print(
        "========================================"
    )

    print()
    print(
        "Current query index:",
        query_index
    )

    print(
        "Current query:",
        current_query
    )

    print(
        "Countries:",
        len(countries)
    )

    print(
        "Maximum API calls:",
        max_search_calls
    )

    all_jobs = []
    call_count = 0
    failed_calls = 0

    for country in countries:

        if call_count >= max_search_calls:
            break

        call_count += 1

        country_code = country[
            "code"
        ]

        country_group = country[
            "group"
        ]

        print()
        print(
            f"[{call_count}/{max_search_calls}]"
        )

        print(
            "Country:",
            country_code,
            f"({country_group})"
        )

        print(
            "Query:",
            current_query
        )

        try:

            jobs = search_jobs(
                keyword=current_query,
                country=country_code,
                results_per_page=results_per_page,
                page=1
            )

            print(
                "Results returned:",
                len(jobs)
            )

            all_jobs.extend(
                jobs
            )

        except requests.RequestException as error:

            failed_calls += 1

            print(
                "Search API error:",
                error
            )

        except Exception as error:

            failed_calls += 1

            print(
                "Unexpected search error:",
                error
            )

    unique_jobs = deduplicate_jobs(
        all_jobs
    )

    (
        new_jobs,
        known_count
    ) = save_new_jobs(
        unique_jobs
    )

    next_index = advance_search_cursor(
        query_index,
        len(queries)
    )

    next_query = queries[
        next_index
    ]

    print()
    print(
        "Raw jobs collected:",
        len(all_jobs)
    )

    print(
        "Unique jobs in this search:",
        len(unique_jobs)
    )

    print(
        "New jobs saved:",
        len(new_jobs)
    )

    print(
        "Already known jobs:",
        known_count
    )

    print(
        "Failed API calls:",
        failed_calls
    )

    print()
    print(
        "Search cursor advanced."
    )

    print(
        "Next run query:",
        next_query
    )

    return {
        "api_calls": call_count,
        "query": current_query,
        "next_query": next_query,
        "raw_jobs": len(all_jobs),
        "unique_jobs": len(unique_jobs),
        "new_jobs": len(new_jobs),
        "known_jobs": known_count,
        "failed_calls": failed_calls,
    }


# ==========================================================
# Priority URL counts
# ==========================================================

def count_pending_url_discovery(
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


def count_low_priority_url_jobs(
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
# STAGE 3
# Priority URL Discovery
# ==========================================================

def run_url_discovery_stage(
    max_jobs,
    minimum_score
):

    print()
    print(
        "========================================"
    )
    print(
        "STAGE 3: PRIORITY URL DISCOVERY"
    )
    print(
        "========================================"
    )

    print()
    print(
        "Minimum preliminary score:",
        minimum_score
    )

    processed = 0

    while processed < max_jobs:

        pending = (
            count_pending_url_discovery(
                minimum_score
            )
        )

        if pending == 0:

            print()
            print(
                "No priority jobs waiting "
                "for URL discovery."
            )

            break

        print()
        print(
            "Priority jobs waiting:",
            pending
        )

        print(
            "URL discovery:",
            processed + 1,
            "of",
            max_jobs
        )

        before_count = pending

        run_one_url_discovery()

        after_count = (
            count_pending_url_discovery(
                minimum_score
            )
        )

        if after_count >= before_count:

            print()
            print(
                "WARNING: URL discovery pending "
                "count did not decrease."
            )

            print(
                "Stopping to prevent repeated "
                "web-search calls."
            )

            break

        processed += 1

    print()
    print(
        "URL discovery attempts this run:",
        processed
    )


# ==========================================================
# Description state
# ==========================================================

def count_incomplete_jobs():

    connection = sqlite3.connect(
        DB_PATH
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM jobs

        WHERE COALESCE(
            description_complete,
            0
        ) = 0
        """
    )

    count = cursor.fetchone()[0]

    connection.close()

    return count


# ==========================================================
# AI priority counts
# ==========================================================

def count_pending_ai_jobs(
    minimum_rule_score
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


def count_low_priority_ai_jobs(
    minimum_rule_score
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
# STAGE 6
# Priority AI Matching
# ==========================================================

def run_ai_stage(
    max_ai_jobs,
    minimum_rule_score
):

    print()
    print(
        "========================================"
    )
    print(
        "STAGE 6: PRIORITY AI SEMANTIC MATCHING"
    )
    print(
        "========================================"
    )

    print()
    print(
        "Minimum rule score for AI:",
        minimum_rule_score
    )

    analyzed = 0

    while analyzed < max_ai_jobs:

        pending = (
            count_pending_ai_jobs(
                minimum_rule_score
            )
        )

        if pending == 0:

            print()
            print(
                "No priority jobs waiting "
                "for AI analysis."
            )

            break

        print()
        print(
            "Priority AI jobs waiting:",
            pending
        )

        print(
            "AI analysis:",
            analyzed + 1,
            "of",
            max_ai_jobs
        )

        before_count = pending

        run_one_ai_match()

        after_count = (
            count_pending_ai_jobs(
                minimum_rule_score
            )
        )

        if after_count >= before_count:

            print()
            print(
                "WARNING: AI pending count "
                "did not decrease."
            )

            print(
                "Stopping AI stage to prevent "
                "repeated API calls."
            )

            break

        analyzed += 1

    print()
    print(
        "AI jobs analyzed this run:",
        analyzed
    )


# ==========================================================
# MAIN PIPELINE
# ==========================================================

def main():

    print()
    print(
        "========================================"
    )
    print(
        "FUSA AI JOB AGENT"
    )
    print(
        "========================================"
    )

    config = load_config()

    pipeline_config = config.get(
        "pipeline",
        {}
    )

    if not isinstance(
        pipeline_config,
        dict
    ):
        pipeline_config = {}

    minimum_preliminary_score = (
        get_minimum_preliminary_score(
            config
        )
    )

    minimum_ai_rule_score = (
        get_minimum_ai_rule_score(
            config
        )
    )

    init_database()

    # ======================================================
    # STAGE 1
    # Job Search
    # ======================================================

    search_summary = run_search_stage(
        config
    )

    # ======================================================
    # STAGE 2
    # PRELIMINARY Rule Matching
    #
    # Important:
    # Run matcher BEFORE URL discovery.
    # New jobs initially have match_score = 0.
    # This stage scores Adzuna snippets so the
    # priority queue can decide which jobs deserve
    # expensive URL discovery.
    # ======================================================

    if pipeline_config.get(
        "run_rule_matcher",
        True
    ):

        print()
        print(
            "========================================"
        )
        print(
            "STAGE 2: PRELIMINARY RULE MATCHING"
        )
        print(
            "========================================"
        )

        print()
        print(
            "Scoring available Adzuna snippets "
            "before URL discovery..."
        )

        run_rule_matcher()

    # ======================================================
    # STAGE 3
    # Priority URL Discovery
    # ======================================================

    if pipeline_config.get(
        "run_url_discovery",
        True
    ):

        max_url_jobs = int(
            pipeline_config.get(
                "max_url_discovery_per_run",
                3
            )
        )

        run_url_discovery_stage(
            max_jobs=max_url_jobs,
            minimum_score=minimum_preliminary_score
        )

    # ======================================================
    # STAGE 4
    # Full Description Enrichment
    # ======================================================

    if pipeline_config.get(
        "run_enrichment",
        True
    ):

        max_enrichment_jobs = int(
            pipeline_config.get(
                "max_enrichment_jobs_per_run",
                3
            )
        )

        print()
        print(
            "========================================"
        )
        print(
            "STAGE 4: DESCRIPTION ENRICHMENT"
        )
        print(
            "========================================"
        )

        run_enrichment(
            max_jobs=max_enrichment_jobs
        )

    # ======================================================
    # STAGE 5
    # FINAL Rule Matching
    #
    # Jobs with full descriptions are now scored again.
    # This replaces the score based on the short snippet
    # with the more reliable full-description score.
    # ======================================================

    if pipeline_config.get(
        "run_rule_matcher",
        True
    ):

        print()
        print(
            "========================================"
        )
        print(
            "STAGE 5: FINAL RULE MATCHING"
        )
        print(
            "========================================"
        )

        print()
        print(
            "Re-scoring jobs after description "
            "enrichment..."
        )

        run_rule_matcher()

    # ======================================================
    # STAGE 6
    # Priority AI Semantic Matching
    # ======================================================

    if pipeline_config.get(
        "run_ai_matcher",
        True
    ):

        max_ai_jobs = int(
            pipeline_config.get(
                "max_ai_jobs_per_run",
                3
            )
        )

        run_ai_stage(
            max_ai_jobs=max_ai_jobs,
            minimum_rule_score=minimum_ai_rule_score
        )

    # ======================================================
    # STAGE 7
    # Career Radar
    # ======================================================

    if pipeline_config.get(
        "generate_html_report",
        True
    ):

        print()
        print(
            "========================================"
        )
        print(
            "STAGE 7: HTML CAREER RADAR"
        )
        print(
            "========================================"
        )

        generate_html_report()

    # ======================================================
    # FINAL SUMMARY
    # ======================================================

    priority_url_pending = (
        count_pending_url_discovery(
            minimum_preliminary_score
        )
    )

    low_priority_url_jobs = (
        count_low_priority_url_jobs(
            minimum_preliminary_score
        )
    )

    priority_ai_pending = (
        count_pending_ai_jobs(
            minimum_ai_rule_score
        )
    )

    low_priority_ai_jobs = (
        count_low_priority_ai_jobs(
            minimum_ai_rule_score
        )
    )

    print()
    print(
        "========================================"
    )
    print(
        "PIPELINE COMPLETED"
    )
    print(
        "========================================"
    )

    print()
    print(
        "Search strategy:",
        "PERSISTENT ROUND ROBIN"
    )

    print(
        "Query used:",
        search_summary[
            "query"
        ]
    )

    print(
        "Next query:",
        search_summary[
            "next_query"
        ]
    )

    print(
        "Adzuna calls:",
        search_summary[
            "api_calls"
        ]
    )

    print(
        "New jobs:",
        search_summary[
            "new_jobs"
        ]
    )

    print(
        "Known jobs:",
        search_summary[
            "known_jobs"
        ]
    )

    print(
        "Failed search calls:",
        search_summary[
            "failed_calls"
        ]
    )

    print()
    print(
        "URL priority threshold:",
        minimum_preliminary_score
    )

    print(
        "Priority jobs waiting "
        "for URL discovery:",
        priority_url_pending
    )

    print(
        "Low-priority URL jobs parked:",
        low_priority_url_jobs
    )

    print(
        "Jobs still needing "
        "full description:",
        count_incomplete_jobs()
    )

    print()
    print(
        "AI priority threshold:",
        minimum_ai_rule_score
    )

    print(
        "Priority jobs waiting for AI:",
        priority_ai_pending
    )

    print(
        "Complete low-priority jobs "
        "skipped by AI:",
        low_priority_ai_jobs
    )

    print()
    print(
        "HTML report:"
    )

    print(
        r"reports\weekly_job_report.html"
    )

    print()
    print(
        "Open report with:"
    )

    print(
        r"start reports\weekly_job_report.html"
    )


# ==========================================================
# Start
# ==========================================================

if __name__ == "__main__":

    main()