"""Chart components for the Streamlit dashboard.

Provides radar charts for score breakdowns, bar charts for
score distributions, and timeline charts.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


def create_score_radar(
    skills_score: int,
    experience_score: int,
    title_score: int,
    location_score: int,
) -> go.Figure:
    """Create a radar chart showing the match score breakdown.

    Args:
        skills_score: Skills overlap score (0-100).
        experience_score: Experience match score.
        title_score: Title relevance score.
        location_score: Location compatibility score.

    Returns:
        A Plotly Figure object.
    """
    categories = ["Skills", "Experience", "Title Fit", "Location"]
    values = [skills_score, experience_score, title_score, location_score]
    # Close the polygon
    values_closed = values + [values[0]]
    categories_closed = categories + [categories[0]]

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=categories_closed,
        fill="toself",
        fillcolor="rgba(41, 121, 255, 0.2)",
        line=dict(color="#2979FF", width=2),
        marker=dict(size=8, color="#2979FF"),
        name="Score",
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(size=10, color="#9e9e9e"),
                gridcolor="#2d2f36",
            ),
            angularaxis=dict(
                tickfont=dict(size=12, color="#e0e0e0"),
                gridcolor="#2d2f36",
            ),
            bgcolor="#0e1117",
        ),
        showlegend=False,
        paper_bgcolor="#0e1117",
        margin=dict(l=60, r=60, t=30, b=30),
        height=300,
    )

    return fig


def create_score_distribution(matches: list[dict]) -> go.Figure:
    """Create a histogram of match scores.

    Args:
        matches: List of match dicts with overall_score field.

    Returns:
        A Plotly Figure object.
    """
    if not matches:
        fig = go.Figure()
        fig.update_layout(
            title="No matches yet",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
        )
        return fig

    scores = [m.get("overall_score", 0) for m in matches]

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=scores,
        nbinsx=20,
        marker=dict(
            color="#2979FF",
            line=dict(color="#1565C0", width=1),
        ),
    ))

    fig.update_layout(
        title="Score Distribution",
        xaxis_title="Match Score",
        yaxis_title="Count",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#1a1d23",
        font=dict(color="#e0e0e0"),
        xaxis=dict(gridcolor="#2d2f36", range=[0, 100]),
        yaxis=dict(gridcolor="#2d2f36"),
        margin=dict(l=50, r=20, t=50, b=50),
        height=300,
    )

    return fig


def create_matches_timeline(matches: list[dict]) -> go.Figure:
    """Create a timeline chart showing matches over time.

    Args:
        matches: List of match dicts with created_at and overall_score.

    Returns:
        A Plotly Figure object.
    """
    if not matches:
        fig = go.Figure()
        fig.update_layout(
            title="No matches yet",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
        )
        return fig

    df = pd.DataFrame(matches)
    df["date"] = pd.to_datetime(df["created_at"]).dt.date
    daily = df.groupby("date").agg(
        count=("overall_score", "count"),
        avg_score=("overall_score", "mean"),
    ).reset_index()

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=daily["date"],
        y=daily["count"],
        name="Matches Found",
        marker_color="#2979FF",
        yaxis="y",
    ))

    fig.add_trace(go.Scatter(
        x=daily["date"],
        y=daily["avg_score"],
        name="Avg Score",
        line=dict(color="#00E676", width=2),
        yaxis="y2",
    ))

    fig.update_layout(
        title="Matches Over Time",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#1a1d23",
        font=dict(color="#e0e0e0"),
        xaxis=dict(gridcolor="#2d2f36"),
        yaxis=dict(title="Count", gridcolor="#2d2f36", side="left"),
        yaxis2=dict(
            title="Avg Score",
            overlaying="y",
            side="right",
            range=[0, 100],
            gridcolor="#2d2f36",
        ),
        legend=dict(orientation="h", y=1.1),
        margin=dict(l=50, r=50, t=50, b=50),
        height=300,
    )

    return fig
