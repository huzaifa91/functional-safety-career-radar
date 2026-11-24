import json
import sqlite3

from datetime import datetime
from pathlib import Path
from html import escape

import yaml


DB_PATH = "data/jobs.db"
CONFIG_FILE = "config.yaml"
REPORT_DIR = Path("reports")

DEFAULT_URL_THRESHOLD = 35
DEFAULT_AI_THRESHOLD = 40


# ==========================================================
# Configuration
# ==========================================================

def load_config():

    try:

        with open(
            CONFIG_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            config = yaml.safe_load(file)

        return config or {}

    except FileNotFoundError:

        return {}


def get_thresholds():

    config = load_config()

    enrichment_priority = config.get(
        "enrichment_priority",
        {}
    )

    ai_priority = config.get(
        "ai_priority",
        {}
    )

    if not isinstance(
        enrichment_priority,
        dict
    ):
        enrichment_priority = {}

    if not isinstance(
        ai_priority,
        dict
    ):
        ai_priority = {}

    url_threshold = int(
        enrichment_priority.get(
            "minimum_preliminary_score",
            DEFAULT_URL_THRESHOLD
        )
    )

    ai_threshold = int(
        ai_priority.get(
            "minimum_rule_score",
            DEFAULT_AI_THRESHOLD
        )
    )

    return (
        url_threshold,
        ai_threshold
    )


# ==========================================================
# Load jobs
# ==========================================================

def load_jobs():

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
            original_url,

            description_complete,

            match_score,
            recommendation,
            confidence,
            matched_standards,
            matched_skills,

            ai_match_score,
            ai_recommendation,
            ai_strengths,
            ai_missing_requirements,
            ai_concerns,
            ai_career_growth,
            ai_why_fit,
            ai_analyzed,

            url_discovery_attempted,
            url_discovery_found,

            enrichment_attempts,
            enrichment_failed

        FROM jobs

        ORDER BY
            COALESCE(
                ai_match_score,
                match_score,
                0
            ) DESC
        """
    )

    jobs = cursor.fetchall()

    connection.close()

    return jobs


# ==========================================================
# JSON helper
# ==========================================================

def parse_json_list(value):

    if not value:
        return []

    try:

        parsed = json.loads(value)

        if isinstance(
            parsed,
            list
        ):
            return parsed

    except json.JSONDecodeError:
        pass

    return []


# ==========================================================
# HTML helpers
# ==========================================================

def list_to_html(
    items,
    color="#333333"
):

    if not items:

        return """
        <p style="color:#777777;">
            None identified
        </p>
        """

    content = ""

    for item in items:

        content += f"""
        <li style="
            margin-bottom:8px;
            line-height:1.5;
            color:{color};
        ">
            {escape(str(item))}
        </li>
        """

    return f"""
    <ul style="
        padding-left:22px;
        margin-top:8px;
    ">
        {content}
    </ul>
    """


def summary_box(
    label,
    value,
    background="#f5f5f5",
    color="#222222"
):

    return f"""
    <div style="
        background:{background};
        padding:15px;
        border-radius:8px;
        min-width:110px;
    ">

        {escape(label)}

        <div style="
            font-size:28px;
            font-weight:bold;
            color:{color};
            margin-top:4px;
        ">
            {value}
        </div>

    </div>
    """


def backlog_row(
    label,
    value,
    description="",
    color="#222222"
):

    return f"""
    <div style="
        display:flex;
        justify-content:space-between;
        gap:20px;
        padding:13px 0;
        border-bottom:1px solid #eeeeee;
    ">

        <div>

            <strong>
                {escape(label)}
            </strong>

            {
                f'<div style="color:#777777; font-size:12px; '
                f'margin-top:3px;">{escape(description)}</div>'
                if description
                else ""
            }

        </div>

        <div style="
            font-size:22px;
            font-weight:bold;
            color:{color};
        ">
            {value}
        </div>

    </div>
    """


# ==========================================================
# Recommendation styling
# ==========================================================

def recommendation_style(
    recommendation
):

    styles = {

        "STRONG APPLY": {
            "color": "#107c10",
            "background": "#e7f4e4",
            "icon": "🔥",
        },

        "APPLY": {
            "color": "#0067b8",
            "background": "#e5f1fb",
            "icon": "✓",
        },

        "CONSIDER": {
            "color": "#8a5700",
            "background": "#fff4ce",
            "icon": "△",
        },

        "SKIP": {
            "color": "#a4262c",
            "background": "#fde7e9",
            "icon": "×",
        },

        "LOW MATCH": {
            "color": "#a4262c",
            "background": "#fde7e9",
            "icon": "×",
        },
    }

    return styles.get(
        recommendation,
        {
            "color": "#666666",
            "background": "#eeeeee",
            "icon": "",
        }
    )


# ==========================================================
# Final recommendation
# ==========================================================

def get_final_recommendation(job):

    ai_analyzed = bool(
        job[19]
    )

    ai_recommendation = job[13]

    rule_recommendation = job[8]

    if (
        ai_analyzed
        and
        ai_recommendation
    ):

        return ai_recommendation

    return rule_recommendation


# ==========================================================
# Decision-ready jobs
# ==========================================================

def is_decision_ready(job):

    description_complete = bool(
        job[6]
    )

    ai_analyzed = bool(
        job[19]
    )

    final_recommendation = (
        get_final_recommendation(
            job
        )
    )

    accepted = {
        "STRONG APPLY",
        "APPLY",
        "CONSIDER",
    }

    return (
        description_complete
        and
        ai_analyzed
        and
        final_recommendation in accepted
    )


# ==========================================================
# Build job card
# ==========================================================

def build_job_card(job):

    (
        job_id,
        title,
        company,
        location,
        country,
        original_url,

        description_complete,

        rule_score,
        rule_recommendation,
        confidence,
        matched_standards,
        matched_skills,

        ai_score,
        ai_recommendation,
        ai_strengths,
        ai_missing_requirements,
        ai_concerns,
        ai_career_growth,
        ai_why_fit,
        ai_analyzed,

        url_discovery_attempted,
        url_discovery_found,

        enrichment_attempts,
        enrichment_failed

    ) = job

    final_recommendation = (
        get_final_recommendation(job)
    )

    style = recommendation_style(
        final_recommendation
    )

    strengths = parse_json_list(
        ai_strengths
    )

    missing = parse_json_list(
        ai_missing_requirements
    )

    concerns = parse_json_list(
        ai_concerns
    )

    standards = escape(
        matched_standards
        or
        "None identified"
    )

    skills = escape(
        matched_skills
        or
        "None identified"
    )

    if original_url:

        view_job_html = f"""
        <a
            href="{escape(original_url)}"
            target="_blank"
            rel="noopener noreferrer"
            style="
                display:inline-block;
                background:#0067b8;
                color:white;
                text-decoration:none;
                padding:12px 22px;
                border-radius:6px;
                font-weight:bold;
                margin-top:20px;
            "
        >
            View Job
        </a>
        """

    else:

        view_job_html = ""

    return f"""
    <div style="
        background:white;
        border-radius:12px;
        padding:26px;
        margin-bottom:28px;
        box-shadow:0 2px 10px rgba(0,0,0,0.07);
    ">

        <div style="
            display:inline-block;
            background:{style["background"]};
            color:{style["color"]};
            padding:7px 13px;
            border-radius:20px;
            font-weight:bold;
        ">
            {style["icon"]}
            {escape(final_recommendation or "")}
        </div>


        <h2 style="margin-bottom:6px;">
            {escape(title or "")}
        </h2>


        <div style="
            color:#555555;
            line-height:1.5;
        ">

            <strong>
                {escape(company or "")}
            </strong>

            <br>

            {escape(location or "")}

            {
                " | " + escape(country)
                if country
                else ""
            }

        </div>


        <div style="
            display:flex;
            flex-wrap:wrap;
            gap:15px;
            margin-top:20px;
            margin-bottom:20px;
        ">

            <div style="
                flex:1;
                min-width:180px;
                background:#f5f5f5;
                padding:16px;
                border-radius:8px;
            ">

                <div style="
                    font-size:12px;
                    color:#666666;
                ">
                    RULE SCORE
                </div>

                <div style="
                    font-size:30px;
                    font-weight:bold;
                ">
                    {rule_score or 0}%
                </div>

                <div>
                    {escape(rule_recommendation or "")}
                </div>

            </div>


            <div style="
                flex:1;
                min-width:180px;
                background:{style["background"]};
                padding:16px;
                border-radius:8px;
            ">

                <div style="
                    font-size:12px;
                    color:#666666;
                ">
                    AI SEMANTIC SCORE
                </div>

                <div style="
                    font-size:30px;
                    font-weight:bold;
                    color:{style["color"]};
                ">
                    {ai_score or 0}%
                </div>

                <div style="
                    font-weight:bold;
                    color:{style["color"]};
                ">
                    {escape(ai_recommendation or "")}
                </div>

            </div>

        </div>


        <div style="
            background:#fafafa;
            padding:16px;
            border-radius:8px;
        ">

            <p>
                <strong>
                    Rule confidence:
                </strong>

                {escape(confidence or "")}
            </p>

            <p>
                <strong>
                    Matched standards:
                </strong>

                <br>

                {standards}
            </p>

            <p>
                <strong>
                    Matched safety skills:
                </strong>

                <br>

                {skills}
            </p>

        </div>


        <h3 style="
            margin-top:25px;
            color:#222222;
        ">
            Why This Job Fits
        </h3>

        <p style="line-height:1.65;">
            {escape(ai_why_fit or "")}
        </p>


        <h3 style="color:#107c10;">
            Technical Strengths
        </h3>

        {list_to_html(strengths)}


        <h3 style="color:#8a5700;">
            Missing Requirements
        </h3>

        {
            list_to_html(
                missing,
                "#5c4400"
            )
        }


        <h3 style="color:#a4262c;">
            Potential Concerns
        </h3>

        {
            list_to_html(
                concerns,
                "#5a1b1f"
            )
        }


        <h3 style="color:#0067b8;">
            Career Growth
        </h3>

        <p style="line-height:1.65;">
            {escape(ai_career_growth or "")}
        </p>


        {view_job_html}

    </div>
    """


# ==========================================================
# Generate report
# ==========================================================

def generate_report():

    (
        url_threshold,
        ai_threshold
    ) = get_thresholds()

    jobs = load_jobs()

    decision_ready_jobs = [
        job
        for job in jobs
        if is_decision_ready(job)
    ]

    strong_apply_jobs = [
        job
        for job in decision_ready_jobs
        if get_final_recommendation(job)
        == "STRONG APPLY"
    ]

    apply_jobs = [
        job
        for job in decision_ready_jobs
        if get_final_recommendation(job)
        == "APPLY"
    ]

    consider_jobs = [
        job
        for job in decision_ready_jobs
        if get_final_recommendation(job)
        == "CONSIDER"
    ]

    discovered_count = len(jobs)

    ai_analyzed_count = sum(
        1
        for job in jobs
        if job[19]
    )

    decision_ready_count = len(
        decision_ready_jobs
    )

    # ======================================================
    # Real pipeline backlog
    # ======================================================

    priority_url_queue = sum(
        1
        for job in jobs
        if (
            not job[5]
            and
            not job[6]
            and
            not job[20]
            and
            (job[7] or 0) >= url_threshold
        )
    )

    low_priority_url_parked = sum(
        1
        for job in jobs
        if (
            not job[5]
            and
            not job[6]
            and
            not job[20]
            and
            (job[7] or 0) < url_threshold
        )
    )

    url_search_failed = sum(
        1
        for job in jobs
        if (
            job[20]
            and
            not job[21]
            and
            not job[6]
        )
    )

    waiting_enrichment = sum(
        1
        for job in jobs
        if (
            job[5]
            and
            not job[6]
            and
            not job[23]
        )
    )

    enrichment_failed = sum(
        1
        for job in jobs
        if bool(job[23])
    )

    priority_ai_queue = sum(
        1
        for job in jobs
        if (
            job[6]
            and
            not job[19]
            and
            (job[7] or 0) >= ai_threshold
        )
    )

    low_priority_ai_parked = sum(
        1
        for job in jobs
        if (
            job[6]
            and
            not job[19]
            and
            (job[7] or 0) < ai_threshold
        )
    )

    generated_time = (
        datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )
    )

    cards = ""

    for job in decision_ready_jobs:

        cards += build_job_card(job)

    if not cards:

        cards = """
        <div style="
            background:white;
            padding:25px;
            border-radius:10px;
        ">
            No decision-ready jobs are available yet.
        </div>
        """

    summary_html = "".join(
        [
            summary_box(
                "Discovered",
                discovered_count
            ),

            summary_box(
                "Strong Apply",
                len(strong_apply_jobs),
                "#e7f4e4",
                "#107c10"
            ),

            summary_box(
                "Apply",
                len(apply_jobs),
                "#e5f1fb",
                "#0067b8"
            ),

            summary_box(
                "Consider",
                len(consider_jobs),
                "#fff4ce",
                "#8a5700"
            ),

            summary_box(
                "Decision Ready",
                decision_ready_count
            ),

            summary_box(
                "AI Analyzed",
                ai_analyzed_count
            ),
        ]
    )

    backlog_html = "".join(
        [
            backlog_row(
                "Priority URL Queue",
                priority_url_queue,
                (
                    f"Preliminary score >= "
                    f"{url_threshold}% and waiting "
                    "for original vacancy discovery."
                ),
                "#0067b8"
            ),

            backlog_row(
                "Low-Priority / Parked",
                low_priority_url_parked,
                (
                    f"Preliminary score below "
                    f"{url_threshold}%. No paid URL "
                    "discovery is performed."
                ),
                "#777777"
            ),

            backlog_row(
                "URL Search Failed",
                url_search_failed,
                (
                    "Web search was attempted but no "
                    "reliable original vacancy was verified."
                ),
                "#a4262c"
            ),

            backlog_row(
                "Waiting Enrichment",
                waiting_enrichment,
                (
                    "Official URL available; full job "
                    "description still needs extraction."
                ),
                "#8a5700"
            ),

            backlog_row(
                "Enrichment Failed",
                enrichment_failed,
                (
                    "Description enrichment reached "
                    "the retry limit."
                ),
                "#a4262c"
            ),

            backlog_row(
                "Priority AI Queue",
                priority_ai_queue,
                (
                    f"Full description ready and final "
                    f"rule score >= {ai_threshold}%."
                ),
                "#107c10"
            ),

            backlog_row(
                "Low-Priority AI / Parked",
                low_priority_ai_parked,
                (
                    f"Full description ready but final "
                    f"rule score below {ai_threshold}%."
                ),
                "#777777"
            ),
        ]
    )

    html = f"""
<!DOCTYPE html>

<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>
        Functional Safety Career Radar
    </title>

</head>


<body style="
    margin:0;
    padding:30px;
    background:#f3f4f6;
    font-family:Arial, Helvetica, sans-serif;
    color:#222222;
">

<div style="
    max-width:950px;
    margin:auto;
">

    <div style="
        background:#0f3b5f;
        color:white;
        padding:30px;
        border-radius:12px;
        margin-bottom:25px;
    ">

        <h1 style="
            margin:0 0 8px 0;
        ">
            Functional Safety Career Radar
        </h1>

        <p style="
            margin:0;
            opacity:0.9;
        ">
            AI-assisted Functional Safety opportunity ranking
        </p>

        <p style="
            font-size:13px;
            opacity:0.8;
            margin-bottom:0;
        ">
            Generated: {generated_time}
        </p>

    </div>


    <div style="
        background:white;
        padding:22px;
        border-radius:10px;
        margin-bottom:25px;
        box-shadow:0 2px 8px rgba(0,0,0,0.05);
    ">

        <h2 style="margin-top:0;">
            Career Radar Summary
        </h2>

        <div style="
            display:flex;
            flex-wrap:wrap;
            gap:12px;
        ">

            {summary_html}

        </div>

    </div>


    <div style="
        background:white;
        padding:22px;
        border-radius:10px;
        margin-bottom:25px;
        box-shadow:0 2px 8px rgba(0,0,0,0.05);
    ">

        <h2 style="margin-top:0;">
            Pipeline Backlog
        </h2>

        <p style="
            color:#666666;
            margin-bottom:20px;
        ">
            The backlog is separated into active priority
            queues and intentionally parked low-priority jobs.
        </p>

        {backlog_html}

    </div>


    <div style="
        background:#eef6fc;
        padding:22px;
        border-radius:10px;
        margin-bottom:30px;
        border-left:5px solid #0067b8;
    ">

        <h2 style="
            margin-top:0;
            color:#0067b8;
        ">
            Cost Protection
        </h2>

        <div style="
            display:flex;
            flex-wrap:wrap;
            gap:15px;
        ">

            <div style="
                background:white;
                padding:16px 20px;
                border-radius:8px;
                flex:1;
                min-width:220px;
            ">

                <strong>
                    URL Discovery Threshold
                </strong>

                <div style="
                    font-size:28px;
                    font-weight:bold;
                    color:#0067b8;
                    margin-top:6px;
                ">
                    >= {url_threshold}%
                </div>

                <div style="
                    font-size:12px;
                    color:#666666;
                    margin-top:5px;
                ">
                    Lower-scoring vacancies remain parked.
                </div>

            </div>


            <div style="
                background:white;
                padding:16px 20px;
                border-radius:8px;
                flex:1;
                min-width:220px;
            ">

                <strong>
                    AI Analysis Threshold
                </strong>

                <div style="
                    font-size:28px;
                    font-weight:bold;
                    color:#107c10;
                    margin-top:6px;
                ">
                    >= {ai_threshold}%
                </div>

                <div style="
                    font-size:12px;
                    color:#666666;
                    margin-top:5px;
                ">
                    AI is reserved for relevant,
                    complete vacancies.
                </div>

            </div>

        </div>

    </div>


    <h2>
        Decision-Ready Opportunities
    </h2>

    {cards}


    <div style="
        text-align:center;
        color:#777777;
        font-size:12px;
        padding:25px;
    ">

        Rule and AI scores are decision-support signals.

        Review the original vacancy before applying.

    </div>

</div>

</body>

</html>
"""

    REPORT_DIR.mkdir(
        exist_ok=True
    )

    report_path = (
        REPORT_DIR
        /
        "weekly_job_report.html"
    )

    report_path.write_text(
        html,
        encoding="utf-8"
    )

    return report_path


# ==========================================================
# Main
# ==========================================================

def main():

    report_path = generate_report()

    (
        url_threshold,
        ai_threshold
    ) = get_thresholds()

    print()

    print(
        "Career Radar HTML report generated successfully."
    )

    print(
        "Report:",
        report_path
    )

    print()

    print(
        "URL discovery threshold:",
        f"{url_threshold}%"
    )

    print(
        "AI analysis threshold:",
        f"{ai_threshold}%"
    )

    print()

    print(
        "Open it with:"
    )

    print(
        r"start reports\weekly_job_report.html"
    )


if __name__ == "__main__":

    main()