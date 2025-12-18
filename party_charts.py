from flask import Flask, render_template, jsonify
import pandas as pd
app = Flask(__name__)


def build_chart_data(submissions: list[dict], goal) -> dict:
    df = pd.DataFrame(submissions)

    if df.empty:
        return {
            "bar": {"labels": [], "counts": []},
            "progress": {"done": 0, "goal": goal},
            "line": {"dates": [], "series": {}},
        }

    df["submission_date"] = pd.to_datetime(df["submission_date"])
    df["date"] = df["submission_date"].dt.date

    # -------------------
    # Bar chart: total problems per person (all difficulties)
    # -------------------
    per_person = (
        df.groupby("name", as_index=False)
          .size()
          .rename(columns={"size": "cnt"})
          .sort_values("cnt", ascending=False)
    )
    bar = {
        "labels": per_person["name"].tolist(),
        "counts": per_person["cnt"].astype(int).tolist(),
    }

    # -------------------
    # Progress: total vs goal
    # -------------------
    done = int(len(df))
    progress = {"done": done, "goal": goal}

    # -------------------
    # Line chart: cumulative problems over time by person + total
    # -------------------
    daily_by_person = (
        df.groupby(["date", "name"], as_index=False)
          .size()
          .rename(columns={"size": "cnt"})
    )

    # Create a complete date index so missing days become 0s
    all_dates = pd.date_range(df["submission_date"].min().normalize(),
                              df["submission_date"].max().normalize(),
                              freq="D").date

    pivot = (
        daily_by_person
        .pivot(index="date", columns="name", values="cnt")
        .reindex(all_dates)
        .fillna(0)
        .astype(int)
    )

    # Cumulative per person
    cum = pivot.cumsum()

    # Total cumulative
    cum_total = cum.sum(axis=1)

    dates = [d.isoformat() for d in cum.index]
    series = {name: cum[name].tolist() for name in cum.columns}
    series["Total"] = cum_total.tolist()

    line = {"dates": dates, "series": series}

    return {"bar": bar, "progress": progress, "line": line}
