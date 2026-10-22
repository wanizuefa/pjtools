"""Statistics for CineScope.

- Analysis page: shows the results the group computed with Excel's Analysis
  ToolPak (read from data/analysis.xlsx by data_service). toolpak_report()
  only arranges those Excel numbers and writes short captions from them.
- Home page, Dashboard and Box Office Simulator: small calculations on the
  current movie data (key findings, highlights, regression models with numpy).

Every function returns plain Python values (numbers, lists, dicts) that the
templates can use directly. Nothing here reads or writes files.
"""

import math
from datetime import date

import numpy as np
import pandas as pd

MIN_GENRE_COUNT = 30        # genres with fewer movies are not ranked
MIN_YEAR_FINANCIAL = 10     # years with fewer budget+gross movies count as poorly covered
TOP_N = 10


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def format_money(value):
    """$1.2B / $1.2M / $350K / $950, or an em dash when missing."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    sign = "-" if value < 0 else ""
    amount = abs(float(value))
    if amount >= 1e9:
        text = f"{amount / 1e9:.1f}B"
    elif amount >= 1e6:
        text = f"{amount / 1e6:.1f}M"
    elif amount >= 1e3:
        text = f"{amount / 1e3:.0f}K"
    else:
        text = f"{amount:.0f}"
    return f"{sign}${text}"


def financial_rows(df):
    """Rows that have both budget and gross (the only rows used for money analysis)."""
    return df[df["profit"].notna()]


def pearson_r(x, y):
    """Pearson correlation using only rows where both values exist."""
    pair = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(pair) < 3 or pair["x"].std() == 0 or pair["y"].std() == 0:
        return None, len(pair)
    return float(np.corrcoef(pair["x"], pair["y"])[0, 1]), len(pair)


def strength_word(r):
    """Thai description of correlation strength."""
    size = abs(r)
    if size < 0.1:
        return "แทบไม่มีความสัมพันธ์"
    if size < 0.3:
        level = "ต่ำ"
    elif size < 0.5:
        level = "ปานกลาง"
    elif size < 0.7:
        level = "ค่อนข้างสูง"
    else:
        level = "สูง"
    direction = "เชิงบวก" if r > 0 else "เชิงลบ"
    return f"สัมพันธ์กัน{direction}ในระดับ{level}"


def genre_metric(df, column, how, min_count=MIN_GENRE_COUNT):
    """Aggregate `column` by genre, keeping genres with at least `min_count` values.

    Returns (ranked rows, names of genres that were left out).
    """
    data = df[["genre", column]].dropna()
    grouped = data.groupby("genre")[column].agg([how, "count"])
    kept = grouped[grouped["count"] >= min_count].sort_values(how, ascending=False)
    left_out = sorted(grouped.index[grouped["count"] < min_count].tolist())
    rows = [
        {"label": genre, "value": float(row[how]), "count": int(row["count"])}
        for genre, row in kept.iterrows()
    ]
    return rows, left_out


def top_by_total_gross(df, column, n=TOP_N):
    data = df[[column, "gross"]].dropna()
    grouped = data.groupby(column)["gross"].agg(["sum", "count"]).sort_values("sum", ascending=False)
    top = grouped.head(n)
    return [
        {"label": name, "value": float(row["sum"]), "count": int(row["count"])}
        for name, row in top.iterrows()
    ], float(data["gross"].sum())


<<<<<<< HEAD
def top_earners(df):
    """Q4: Companies and directors with the highest total gross."""
    companies, total_gross = top_by_total_gross(df, "company")
    directors, _ = top_by_total_gross(df, "director")
    if not companies or not directors:
        return {"ok": False, "caption": "ยังไม่มีข้อมูลรายได้สำหรับจัดอันดับ"}

    top_c, top_d = companies[0], directors[0]
    share = sum(row["value"] for row in companies) / total_gross * 100 if total_gross else 0
    company_caption = (
        f"{top_c['label']} ทำรายได้รวมสูงสุด {format_money(top_c['value'])} จาก {top_c['count']:,} เรื่อง "
        f"และ Top {len(companies)} บริษัทรวมกันคิดเป็น {share:.0f}% ของรายได้รวมทั้งหมดในข้อมูล "
        "แสดงว่ารายได้กระจุกตัวอยู่กับสตูดิโอใหญ่ไม่กี่แห่ง"
    )
    director_caption = (
        f"{top_d['label']} เป็นผู้กำกับที่ทำรายได้รวมสูงสุด {format_money(top_d['value'])} "
        f"จาก {top_d['count']:,} เรื่อง (เฉลี่ยเรื่องละ {format_money(top_d['value'] / top_d['count'])})"
    )
    return {
        "ok": True,
        "companies": chart_series(companies),
        "directors": chart_series(directors),
        "company_caption": company_caption,
        "director_caption": director_caption,
    }

def runtime_vs_score(df):
    """Q5: Is runtime related to score?"""
    r, n = pearson_r(df["runtime"], df["score"])
    reg = linear_regression(df["runtime"], df["score"])
    if r is None or reg is None:
        return {"ok": False, "caption": "ข้อมูลความยาวและคะแนนยังไม่พอสำหรับคำนวณ"}

    short = df.loc[df["runtime"] < 90, "score"].dropna()
    long = df.loc[df["runtime"] > 120, "score"].dropna()
    caption = f"ความยาวหนังกับคะแนน{strength_word(r)} (r = {r:.2f}, {n:,} เรื่อง)"
    if len(short) and len(long):
        caption += (
            f" หนังที่ยาวกว่า 120 นาทีได้คะแนนเฉลี่ย {long.mean():.2f} ({len(long):,} เรื่อง) "
            f"เทียบกับ {short.mean():.2f} ของหนังที่สั้นกว่า 90 นาที ({len(short):,} เรื่อง)"
        )
    caption += (
        " แต่ไม่ได้แปลว่าการทำหนังให้ยาวขึ้นจะทำให้ได้คะแนนดีขึ้น "
        "เพราะหนังดราม่าหรือหนังมหากาพย์ที่มักได้คะแนนดีก็มักจะยาวอยู่แล้ว"
    )
    pair = df[["runtime", "score"]].dropna()
    band_masks = [
        ("สั้นกว่า 90 นาที", pair["runtime"] < 90),
        ("90–120 นาที", pair["runtime"].between(90, 120)),
        ("ยาวกว่า 120 นาที", pair["runtime"] > 120),
    ]
    bands = []
    for label, mask in band_masks:
        scores = pair.loc[mask, "score"]
        bands.append({"label": label, "mean": float(scores.mean()) if len(scores) else None,
                      "count": int(len(scores))})
    return {
        "ok": True,
        "r": r,
        "n": n,
        "bands": bands,
        "caption": caption,
        "chart": {
            "points": [[float(x), float(y)] for x, y in pair.itertuples(index=False)],
            "line": [
                [reg["x_min"], reg["slope"] * reg["x_min"] + reg["intercept"]],
                [reg["x_max"], reg["slope"] * reg["x_max"] + reg["intercept"]],
            ],
        },
    }


def roi_by_genre(df):
    """Q6: Median ROI (gross ÷ budget) per genre."""
    fin = financial_rows(df)
    rows, left_out = genre_metric(fin, "roi", "median")
    if not rows:
        return {"ok": False, "caption": f"ยังไม่มีประเภทหนังที่มีข้อมูลการเงินอย่างน้อย {MIN_GENRE_COUNT} เรื่อง"}

    top, low = rows[0], rows[-1]
    loss_share = (fin["roi"] < 1).mean() * 100
    best = fin.loc[fin["roi"].idxmax()]
    caption = (
        f"{top['label']} มี ROI มัธยฐานสูงสุด ({top['value']:.2f} เท่า คือรายได้ประมาณ {top['value']:.2f} เท่าของทุนสร้าง) "
        f"ส่วน {low['label']} ต่ำสุด ({low['value']:.2f} เท่า) ในภาพรวมมีหนัง {loss_share:.0f}% "
        f"ที่รายได้ต่ำกว่าทุนสร้าง (ROI < 1) ที่ใช้มัธยฐานเพราะ ROI มีค่าผิดปกติสูงมาก "
        f"เช่น {best['name']} ({int(best['year'])}) มี ROI ถึง {best['roi']:,.0f} เท่า "
        f"ทำให้ค่าเฉลี่ย ROI ทั้งหมด ({fin['roi'].mean():,.1f} เท่า) สูงเกินจริงเมื่อเทียบกับมัธยฐาน "
        f"({fin['roi'].median():.2f} เท่า)"
    )
    return {"ok": True, "chart": chart_series(rows), "caption": caption, "left_out": left_out}


=======
>>>>>>> 118dbdc91cb76da493f09fd4c25e3e78735d2538
# ---------------------------------------------------------------------------
# Home page and Dashboard (computed from the current movie data)
# ---------------------------------------------------------------------------

def key_findings(df):
    """Three headline findings for the home page, computed from the current data."""
    # Pairwise rows, same as correlation_matrix(), so the numbers always agree.
    budget_gross, n_gross = pearson_r(df["budget"], df["gross"])
    budget_score, n_score = pearson_r(df["budget"], df["score"])
    gross_rows, _ = genre_metric(df, "gross", "median")
    top_genre = gross_rows[0] if gross_rows else None
    return {
        "budget_gross_r": budget_gross,
        "budget_gross_text": (
            f"ทุนสร้างกับรายได้{strength_word(budget_gross)} หนังที่ลงทุนมากมักทำรายได้มากตาม "
            f"(จาก {n_gross:,} เรื่อง)" if budget_gross is not None else "ข้อมูลยังไม่พอ"
        ),
        "budget_score_r": budget_score,
        "budget_score_text": (
            f"ทุนสร้างกับคะแนน{strength_word(budget_score)} ใช้เงินมากไม่ได้ทำให้ผู้ชมให้คะแนนดีขึ้น "
            f"(จาก {n_score:,} เรื่อง)" if budget_score is not None else "ข้อมูลยังไม่พอ"
        ),
        "top_genre": top_genre,
        "top_genre_text": (
            f"รายได้มัธยฐาน {format_money(top_genre['value'])} ต่อเรื่อง สูงสุดในบรรดาประเภทที่มีหนัง"
            f"อย่างน้อย {MIN_GENRE_COUNT} เรื่อง (จาก {top_genre['count']:,} เรื่อง)"
            if top_genre else "ข้อมูลยังไม่พอ"
        ),
    }


def home_summary(df):
    """Headline counters for the home page."""
    return {
        "movies": int(len(df)),
        "year_min": int(df["year"].min()) if len(df) else None,
        "year_max": int(df["year"].max()) if len(df) else None,
        "total_gross": float(df["gross"].sum()),
        "mean_score": float(df["score"].mean()) if df["score"].notna().any() else None,
    }


FEATURED_MIN_SCORE = 7.5


def featured_movie(df, day):
    """"Movie of the day": a random movie scoring 7.5+, the same for the whole day."""
    pool = df[df["score"] >= FEATURED_MIN_SCORE].sort_values("id")
    if pool.empty:
        return None
    rng = np.random.default_rng(day.toordinal())  # seeded by the date
    row = pool.iloc[int(rng.integers(len(pool)))]
    return {key: (None if pd.isna(value) else value) for key, value in row.to_dict().items()}


def dashboard_highlights(df):
    """One number per Tableau chart, from the current data, shown under the dashboard."""
    fin = financial_rows(df)
    by_year = df.groupby("year")["gross"].sum()
    genre_rows, _ = genre_metric(df, "gross", "mean")
    r, _ = pearson_r(df["budget"], df["gross"])
    countries = df["country"].value_counts()
    companies, _ = top_by_total_gross(df, "company", n=1)
    return {
        "year": (f"ปีที่รายได้รวมสูงสุดคือ {int(by_year.idxmax())} ({format_money(by_year.max())})"
                 if not by_year.empty else ""),
        "genre": (f"รายได้เฉลี่ยสูงสุด: {genre_rows[0]['label']} ({format_money(genre_rows[0]['value'])} ต่อเรื่อง)"
                  if genre_rows else ""),
        "scatter": (f"r = {r:.2f} จาก {len(fin):,} เรื่องที่มีทั้งทุนสร้างและรายได้" if r is not None else ""),
        "country": (f"{countries.index[0]} มีหนังมากที่สุด ({int(countries.iloc[0]):,} เรื่อง จาก {countries.size} ประเทศ)"
                    if not countries.empty else ""),
        "company": (f"อันดับ 1: {companies[0]['label']} ({format_money(companies[0]['value'])})"
                    if companies else ""),
    }


# ---------------------------------------------------------------------------
# Box Office Simulator: multiple linear regression with numpy (no scikit-learn)
# ---------------------------------------------------------------------------

VERDICTS = [
    # (minimum ROI, key, label, description)
    (3.0, "blockbuster", "BLOCKBUSTER", "ทำเงินได้ตั้งแต่ 3 เท่าของทุนสร้างขึ้นไป"),
    (1.5, "hit", "HIT", "ทำเงินได้ 1.5–3 เท่าของทุนสร้าง"),
    (1.0, "breakeven", "BREAK EVEN", "รายได้พอๆ กับทุนสร้าง (1–1.5 เท่า)"),
    (0.0, "flop", "FLOP", "รายได้ต่ำกว่าทุนสร้าง"),
]
SIMILAR_COUNT = 5
# Ranking similar movies: distance = |log budget difference|
#   + penalty when the rating differs + a small tie-breaker for distance in years.
RATING_MISMATCH_PENALTY = 0.25
YEAR_DISTANCE_WEIGHT = 0.005


def design_matrix(numeric_columns, genres, genre_list):
    """Build X = [1, numeric columns..., one dummy per genre except the baseline].

    The first genre in `genre_list` is the baseline (all dummies are 0).
    """
    columns = [np.ones(len(genres))] + [np.asarray(col, dtype=float) for col in numeric_columns]
    for genre in genre_list[1:]:
        columns.append((np.asarray(genres) == genre).astype(float))
    return np.column_stack(columns)


def fit_ols(X, y):
    """Ordinary least squares: returns coefficients, R² and residuals."""
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    residuals = y - X @ coef
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float((residuals ** 2).sum()) / ss_tot if ss_tot else 0.0
    return coef, r2, residuals


def build_simulator_models(df):
    """Fit the revenue and score models on the current data.

    Revenue: log(gross) = b0 + b1·log(budget) + b2·runtime + b3·year + genre dummies
    Score:   score      = c0 + c1·runtime     + c2·year    + genre dummies
    Only genres with at least MIN_GENRE_COUNT movies (with budget and gross)
    are modelled; the most common genre is the baseline.
    """
    fin = financial_rows(df)
    fin = fin[(fin["gross"] > 0) & fin["runtime"].notna()]
    counts = fin["genre"].value_counts()
    genre_list = counts[counts >= MIN_GENRE_COUNT].index.tolist()
    if len(genre_list) < 2:
        return None

    rev = fin[fin["genre"].isin(genre_list)]
    X_rev = design_matrix([np.log(rev["budget"]), rev["runtime"], rev["year"]], rev["genre"], genre_list)
    rev_coef, rev_r2, rev_resid = fit_ols(X_rev, np.log(rev["gross"].to_numpy(dtype=float)))

    sc = df[df["genre"].isin(genre_list)].dropna(subset=["score", "runtime"])
    X_sc = design_matrix([sc["runtime"], sc["year"]], sc["genre"], genre_list)
    sc_coef, sc_r2, _ = fit_ols(X_sc, sc["score"].to_numpy(dtype=float))

    per_year = rev.groupby("year").size()
    well_covered_years = per_year[per_year >= MIN_YEAR_FINANCIAL].index
    default_year = int(well_covered_years.max()) if len(well_covered_years) else int(rev["year"].max())

    # Genre effects relative to the baseline genre. On the log scale a
    # coefficient b means "gross × e^b"; for score it is simply "+b points".
    genre_effects = [{"genre": genre_list[0], "gross_multiplier": 1.0, "score_change": 0.0}] + [
        {"genre": g, "gross_multiplier": math.exp(rev_coef[4 + i]), "score_change": float(sc_coef[3 + i])}
        for i, g in enumerate(genre_list[1:])
    ]
    return {
        "genres": genre_list,
        "baseline": genre_list[0],
        "revenue": {
            "coef": rev_coef.tolist(),
            "r2": rev_r2,
            "n": len(rev),
            # Middle 50% of real movies fall within these residuals (log scale)
            "resid_low": float(np.percentile(rev_resid, 25)),
            "resid_high": float(np.percentile(rev_resid, 75)),
            # Plain-language effects, in percent change of predicted gross
            "budget_plus_10pct": (1.1 ** rev_coef[1] - 1) * 100,
            "runtime_plus_10min": (math.exp(10 * rev_coef[2]) - 1) * 100,
            "year_plus_1": (math.exp(rev_coef[3]) - 1) * 100,
        },
        "score": {
            "coef": sc_coef.tolist(),
            "r2": sc_r2,
            "n": len(sc),
            # Change in predicted score (points)
            "runtime_plus_10min": 10 * float(sc_coef[1]),
            "year_plus_10": 10 * float(sc_coef[2]),
        },
        "genre_effects": genre_effects,
        "ranges": {
            "budget_min": float(rev["budget"].min()),
            "budget_max": float(rev["budget"].max()),
            "budget_default": float(rev["budget"].median()),
            "runtime_min": int(rev["runtime"].min()),
            "runtime_max": int(rev["runtime"].max()),
            "runtime_default": int(round(rev["runtime"].median())),
            "year_min": int(rev["year"].min()),
            "year_max": max(int(rev["year"].max()), date.today().year),
            "year_default": default_year,
        },
    }


def verdict_for(roi):
    for minimum, key, label, description in VERDICTS:
        if roi >= minimum:
            return {"key": key, "label": label, "description": description}
    return {"key": "flop", "label": "FLOP", "description": VERDICTS[-1][3]}


def similar_movies(df, genre, budget, year, rating, count=SIMILAR_COUNT):
    """Real movies of the same genre with the closest budget (same rating preferred)."""
    pool = financial_rows(df)
    pool = pool[(pool["genre"] == genre) & (pool["budget"] > 0)]
    if pool.empty:
        return []
    distance = (np.log(pool["budget"]) - math.log(budget)).abs()
    distance = distance + (pool["year"] - year).abs() * YEAR_DISTANCE_WEIGHT
    if rating:
        distance = distance + (pool["rating"] != rating) * RATING_MISMATCH_PENALTY
    nearest = pool.loc[distance.nsmallest(count).index]
    return [
        {
            "name": row["name"],
            "year": int(row["year"]),
            "rating": None if pd.isna(row["rating"]) else row["rating"],
            "budget": float(row["budget"]),
            "gross": float(row["gross"]),
            "roi": float(row["roi"]),
            "score": None if pd.isna(row["score"]) else float(row["score"]),
        }
        for _, row in nearest.iterrows()
    ]


def simulate(models, df, genre, budget, runtime, year, rating=""):
    """Predict gross, profit, ROI and score for an imaginary movie."""
    genre_list = models["genres"]
    rev, sc = models["revenue"], models["score"]

    x_rev = design_matrix([[math.log(budget)], [runtime], [year]], [genre], genre_list)[0]
    log_gross = float(x_rev @ np.array(rev["coef"]))
    gross = math.exp(log_gross)

    x_sc = design_matrix([[runtime], [year]], [genre], genre_list)[0]
    score = min(10.0, max(0.0, float(x_sc @ np.array(sc["coef"]))))

    roi = gross / budget
    return {
        "gross": {
            "predicted": gross,
            "low": math.exp(log_gross + rev["resid_low"]),
            "high": math.exp(log_gross + rev["resid_high"]),
        },
        "profit": gross - budget,
        "roi": roi,
        "score": score,
        "verdict": verdict_for(roi),
        "models": {
            "revenue": {"r2": rev["r2"], "n": rev["n"]},
            "score": {"r2": sc["r2"], "n": sc["n"]},
        },
        "similar": similar_movies(df, genre, budget, year, rating),
    }


# ---------------------------------------------------------------------------
# Analysis page: results from Excel's Analysis ToolPak
# ---------------------------------------------------------------------------
# Only arranges the numbers read from data/analysis.xlsx and writes captions
# from them. The single check against the current data is how many movies the
# Excel file used, so the page can say when the ToolPak needs to be re-run.

DESCRIPTIVE_LABELS = {
    "Mean": "ค่าเฉลี่ย (Mean)",
    "Standard Error": "ความคลาดเคลื่อนมาตรฐาน (Standard Error)",
    "Median": "มัธยฐาน (Median)",
    "Mode": "ฐานนิยม (Mode)",
    "Standard Deviation": "ส่วนเบี่ยงเบนมาตรฐาน (SD)",
    "Sample Variance": "ความแปรปรวน (Sample Variance)",
    "Kurtosis": "ความโด่ง (Kurtosis)",
    "Skewness": "ความเบ้ (Skewness)",
    "Range": "พิสัย (Range)",
    "Minimum": "ค่าต่ำสุด (Minimum)",
    "Maximum": "ค่าสูงสุด (Maximum)",
    "Sum": "ผลรวม (Sum)",
    "Count": "จำนวน (Count)",
}


def format_p_value(p):
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def describe_skew(skewness):
    if skewness <= -0.5:
        return "ข้อมูลเบ้ซ้าย (ค่าส่วนใหญ่อยู่สูงกว่าค่าเฉลี่ย มีค่าต่ำผิดปกติบางส่วนดึงค่าเฉลี่ยลง)"
    if skewness >= 0.5:
        return "ข้อมูลเบ้ขวา (ค่าส่วนใหญ่อยู่ต่ำกว่าค่าเฉลี่ย มีค่าสูงผิดปกติบางส่วนดึงค่าเฉลี่ยขึ้น)"
    return "ข้อมูลค่อนข้างสมมาตร"


def toolpak_report(df, toolpak):
    """Everything the analysis page shows, taken from the ToolPak results."""
    if toolpak is None:
        return {"status": "missing"}
    if "error" in toolpak:
        return {"status": "error", "error": toolpak["error"]}

    # Regression
    reg = toolpak["regression"]
    x_coef = next((c for c in reg["coefficients"] if c["name"].lower() != "intercept"), None)
    intercept = next((c for c in reg["coefficients"] if c["name"].lower() == "intercept"), None)
    reg_data = toolpak["regression_data"]
    regression_caption = ""
    if x_coef and intercept:
        x_name = x_coef["name"]
        y_name = next((str(c) for c in reg_data.columns if str(c).lower() != x_name.lower()), "Y")
        slope, b0 = x_coef["Coefficients"], intercept["Coefficients"]
        b0_text = format_money(abs(b0)) if y_name.lower() in ("gross", "budget") else f"{abs(b0):,.2f}"
        sign = "−" if b0 < 0 else "+"
        r2 = reg["stats"].get("R Square")
        regression_caption = (
            f"สมการที่ได้คือ {y_name} = {slope:.2f} × {x_name} {sign} {b0_text} "
            f"แปลว่า {x_name} ที่เพิ่มขึ้น 1 หน่วย สัมพันธ์กับ {y_name} ที่เพิ่มขึ้นประมาณ {slope:.2f} หน่วยโดยเฉลี่ย"
        )
        if r2 is not None:
            regression_caption += (
                f" และ R Square = {r2:.4f} แปลว่า {x_name} อธิบายความแตกต่างของ {y_name} ได้ประมาณ {r2 * 100:.0f}%"
            )
        p = x_coef.get("P-value")
        if p is not None:
            regression_caption += (
                f" ช่วงความเชื่อมั่น 95% ของความชันคือ {x_coef.get('Lower 95%', float('nan')):.2f} ถึง "
                f"{x_coef.get('Upper 95%', float('nan')):.2f} และ P-value {format_p_value(p)} "
                + ("ซึ่งน้อยกว่า 0.05 จึงสรุปได้ว่าความสัมพันธ์นี้มีนัยสำคัญทางสถิติ"
                   if p < 0.05 else "ซึ่งไม่น้อยกว่า 0.05 จึงยังสรุปไม่ได้ว่ามีความสัมพันธ์อย่างมีนัยสำคัญ")
            )

    # Descriptive Statistics (one block per variable)
    descriptive = []
    for variable, stats in toolpak["descriptive"].items():
        is_money = variable.lower() in ("budget", "gross")
        show = format_money if is_money else (lambda v: f"{v:,.2f}")
        caption = ""
        if {"Mean", "Median", "Standard Deviation", "Count"} <= stats.keys():
            caption = (
                f"{variable} มีค่าเฉลี่ย {show(stats['Mean'])} มัธยฐาน {show(stats['Median'])} "
                f"และส่วนเบี่ยงเบนมาตรฐาน {show(stats['Standard Deviation'])} จาก {stats['Count']:,.0f} เรื่อง"
            )
            if "Skewness" in stats:
                caption += f" ความเบ้ {stats['Skewness']:.2f} แสดงว่า{describe_skew(stats['Skewness'])}"
        descriptive.append({
            "variable": variable,
            "rows": [{"label": label, "thai": DESCRIPTIVE_LABELS.get(label, ""), "value": value}
                     for label, value in stats.items()],
            "caption": caption,
        })

    # Correlation (each pair once)
    correlation = [
        {"a": a, "b": b, "r": r, "caption": f"{a} กับ {b} {strength_word(r)} (r = {r:.4f})"}
        for (a, b), r in toolpak["correlation"]["pairs"].items()
    ]

    excel_movies = len(toolpak["data"]) if not toolpak["data"].empty else None
    excel_financial = reg["stats"].get("Observations")
    current_financial = len(financial_rows(df))
    stale = ((excel_movies is not None and excel_movies != len(df))
             or (excel_financial is not None and int(excel_financial) != current_financial))
    return {
        "status": "ok",
        "modified": toolpak["modified"],
        "regression": reg,
        "regression_caption": regression_caption,
        "descriptive": descriptive,
        "correlation": correlation,
        "freshness": {
            "stale": stale,
            "excel_movies": excel_movies,
            "current_movies": len(df),
            "excel_financial": int(excel_financial) if excel_financial is not None else None,
            "current_financial": current_financial,
        },
    }
