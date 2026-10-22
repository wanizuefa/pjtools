"""Statistics for CineScope.

Every function takes the movie DataFrame from data_service.load_movies()
and returns plain Python values (numbers, lists, dicts) that the templates
and Chart.js can use directly. Nothing here reads or writes files.

Captions are generated from the computed numbers, so the text on the page
always matches the current Excel data.
"""

import math
from datetime import date

import numpy as np
import pandas as pd

MIN_GENRE_COUNT = 30        # genres with fewer movies are not ranked
MIN_YEAR_FINANCIAL = 10     # years with fewer budget+gross movies are left out of money trends
TOP_N = 10

STAT_COLUMNS = {
    "score": "คะแนน IMDb",
    "budget": "ทุนสร้าง (USD)",
    "gross": "รายได้ (USD)",
    "runtime": "ความยาว (นาที)",
}
CORR_COLUMNS = {
    "score": "คะแนน",
    "votes": "จำนวนโหวต",
    "budget": "ทุนสร้าง",
    "gross": "รายได้",
    "runtime": "ความยาว",
}


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


def linear_regression(x, y):
    """Simple least-squares line y = slope * x + intercept, with R²."""
    pair = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(pair) < 3 or pair["x"].std() == 0:
        return None
    slope, intercept = np.polyfit(pair["x"], pair["y"], 1)
    predicted = slope * pair["x"] + intercept
    ss_res = float(((pair["y"] - predicted) ** 2).sum())
    ss_tot = float(((pair["y"] - pair["y"].mean()) ** 2).sum())
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "r2": 1 - ss_res / ss_tot if ss_tot else 0.0,
        "n": len(pair),
        "x_min": float(pair["x"].min()),
        "x_max": float(pair["x"].max()),
    }


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


def chart_series(rows):
    """Split [{label, value, count}] into parallel lists for Chart.js."""
    return {
        "labels": [row["label"] for row in rows],
        "values": [row["value"] for row in rows],
        "counts": [row["count"] for row in rows],
    }


# ---------------------------------------------------------------------------
# Descriptive statistics and correlation
# ---------------------------------------------------------------------------

def descriptive_stats(df):
    """Mean, median, mode, SD (sample), min and max for the key columns."""
    rows = []
    for column, label in STAT_COLUMNS.items():
        values = df[column].dropna()
        counts = values.value_counts()
        has_mode = len(counts) > 0 and counts.iloc[0] > 1
        rows.append({
            "column": column,
            "label": label,
            "n": int(len(values)),
            "mean": float(values.mean()) if len(values) else None,
            "median": float(values.median()) if len(values) else None,
            "mode": float(counts.index[0]) if has_mode else None,
            "mode_count": int(counts.iloc[0]) if has_mode else 0,
            "sd": float(values.std()) if len(values) > 1 else None,  # ddof=1, same as Excel STDEV.S
            "min": float(values.min()) if len(values) else None,
            "max": float(values.max()) if len(values) else None,
        })

    gross = next(row for row in rows if row["column"] == "gross")
    caption = ""
    if gross["mean"] and gross["median"]:
        ratio = gross["mean"] / gross["median"]
        if ratio > 1.3:
            caption = (
                f"รายได้เฉลี่ย ({format_money(gross['mean'])}) สูงกว่ามัธยฐาน "
                f"({format_money(gross['median'])}) ถึง {ratio:.1f} เท่า แสดงว่าข้อมูลเบ้ขวา "
                "มีหนังทำเงินมหาศาลไม่กี่เรื่องดึงค่าเฉลี่ยขึ้น จึงควรใช้มัธยฐานเมื่อเปรียบเทียบรายได้ระหว่างกลุ่ม"
            )
        else:
            caption = (
                f"รายได้เฉลี่ย ({format_money(gross['mean'])}) ใกล้เคียงกับมัธยฐาน "
                f"({format_money(gross['median'])}) การกระจายของรายได้จึงค่อนข้างสมมาตร"
            )
    return {"rows": rows, "caption": caption}


def correlation_matrix(df):
    """Pearson correlation between the key numeric columns (pairwise complete rows)."""
    columns = list(CORR_COLUMNS)
    matrix = df[columns].corr(method="pearson")
    cells = [[None if pd.isna(v) else float(v) for v in matrix.loc[col, columns]] for col in columns]

    pairs = []
    for i, a in enumerate(columns):
        for j in range(i + 1, len(columns)):
            if cells[i][j] is not None:
                pairs.append((cells[i][j], a, columns[j]))
    caption = ""
    if pairs:
        strongest = max(pairs, key=lambda p: abs(p[0]))
        weakest = min(pairs, key=lambda p: abs(p[0]))
        caption = (
            f"คู่ที่สัมพันธ์กันมากที่สุดคือ {CORR_COLUMNS[strongest[1]]} กับ {CORR_COLUMNS[strongest[2]]} "
            f"(r = {strongest[0]:.2f}) ส่วนคู่ที่สัมพันธ์กันน้อยที่สุดคือ "
            f"{CORR_COLUMNS[weakest[1]]} กับ {CORR_COLUMNS[weakest[2]]} (r = {weakest[0]:.2f})"
        )
    return {
        "columns": columns,
        "labels": [CORR_COLUMNS[c] for c in columns],
        "cells": cells,
        "caption": caption,
    }


# ---------------------------------------------------------------------------
# The six research questions
# ---------------------------------------------------------------------------

def budget_vs_gross(df):
    """Q1: How much does budget drive gross? (scatter + regression line)"""
    fin = financial_rows(df)
    reg = linear_regression(fin["budget"], fin["gross"])
    r, n = pearson_r(fin["budget"], fin["gross"])
    if reg is None or r is None:
        return {"ok": False, "caption": "ข้อมูลที่มีทั้งทุนสร้างและรายได้ยังไม่พอสำหรับคำนวณ regression"}

    sign = "+" if reg["intercept"] >= 0 else "−"
    equation = f"รายได้ = {reg['slope']:.2f} × ทุนสร้าง {sign} {format_money(abs(reg['intercept']))}"
    caption = (
        f"ทุนสร้างกับรายได้{strength_word(r)} (r = {r:.2f}) "
        f"ทุนสร้างที่เพิ่มขึ้น $1 สัมพันธ์กับรายได้ที่เพิ่มขึ้นประมาณ ${reg['slope']:.2f} โดยเฉลี่ย "
        f"และ R² = {reg['r2']:.2f} แปลว่าทุนสร้างอธิบายความแตกต่างของรายได้ได้ประมาณ "
        f"{reg['r2'] * 100:.0f}% ส่วนที่เหลือมาจากปัจจัยอื่น เช่น ประเภทหนัง นักแสดง หรือการตลาด "
        f"(คำนวณจาก {n:,} เรื่องที่มีทั้งทุนสร้างและรายได้)"
    )
    points = [
        [float(b), float(g), name, int(year)]
        for b, g, name, year in fin[["budget", "gross", "name", "year"]].itertuples(index=False)
    ]
    line = [
        [reg["x_min"], reg["slope"] * reg["x_min"] + reg["intercept"]],
        [reg["x_max"], reg["slope"] * reg["x_max"] + reg["intercept"]],
    ]
    return {
        "ok": True,
        "r": r,
        "slope": reg["slope"],
        "intercept": reg["intercept"],
        "r2": reg["r2"],
        "n": n,
        "equation": equation,
        "caption": caption,
        "chart": {"points": points, "line": line},
    }


def genre_performance(df):
    """Q2: Which genres earn the most (median gross) and score the best (mean score)?"""
    gross_rows, gross_left_out = genre_metric(df, "gross", "median")
    score_rows, score_left_out = genre_metric(df, "score", "mean")
    if not gross_rows or not score_rows:
        return {"ok": False, "caption": f"ยังไม่มีประเภทหนังที่มีข้อมูลอย่างน้อย {MIN_GENRE_COUNT} เรื่อง"}

    top_gross, top_score, low_score = gross_rows[0], score_rows[0], score_rows[-1]
    gross_caption = (
        f"{top_gross['label']} มีรายได้มัธยฐานสูงสุด ({format_money(top_gross['value'])} จาก "
        f"{top_gross['count']:,} เรื่อง)"
    )
    if len(gross_rows) > 1:
        second = gross_rows[1]
        gross_caption += f" ตามด้วย {second['label']} ({format_money(second['value'])})"
    gross_caption += f" ส่วนต่ำสุดคือ {gross_rows[-1]['label']} ({format_money(gross_rows[-1]['value'])})"

    score_caption = (
        f"{top_score['label']} ได้คะแนนเฉลี่ยสูงสุด ({top_score['value']:.2f}) "
        f"ส่วน {low_score['label']} ได้คะแนนเฉลี่ยต่ำสุด ({low_score['value']:.2f})"
    )
    if top_gross["label"] == top_score["label"]:
        summary = f"{top_gross['label']} เป็นประเภทที่โดดเด่นทั้งด้านรายได้และคะแนน"
    else:
        summary = (
            f"ประเภทที่ทำเงินได้มากที่สุด ({top_gross['label']}) ไม่ใช่ประเภทที่ผู้ชมให้คะแนนสูงที่สุด "
            f"({top_score['label']}) แสดงว่าความสำเร็จด้านรายได้กับด้านคะแนนไม่ได้ไปด้วยกันเสมอ"
        )
    return {
        "ok": True,
        "gross": chart_series(gross_rows),
        "score": chart_series(score_rows),
        "gross_caption": gross_caption,
        "score_caption": score_caption,
        "caption": summary,
        "left_out": sorted(set(gross_left_out) | set(score_left_out)),
    }


def yearly_trends(df):
    """Q3: Number of movies, average budget and average gross per year."""
    counts = df.groupby("year").size()
    fin = financial_rows(df)
    money = fin.groupby("year").agg(budget=("budget", "mean"), gross=("gross", "mean"),
                                    n=("budget", "size"))
    money_kept = money[money["n"] >= MIN_YEAR_FINANCIAL]
    money_left_out = [int(y) for y in money.index[money["n"] < MIN_YEAR_FINANCIAL]]
    if counts.empty or money_kept.empty:
        return {"ok": False, "caption": "ข้อมูลรายปียังไม่พอสำหรับแสดงแนวโน้ม"}

    peak_year = int(counts.idxmax())
    first_year = int(money_kept.index.min())
    budget_peak_year = int(money_kept["budget"].idxmax())
    gross_peak_year = int(money_kept["gross"].idxmax())

    peak_years = counts.index[counts == counts.max()]
    if len(peak_years) >= 3:
        # The dataset keeps a fixed number of popular movies per year.
        count_caption = (
            f"{len(peak_years)} จาก {len(counts)} ปีมีหนังเท่ากันพอดีที่ {int(counts.max()):,} เรื่อง "
            f"(ช่วงปี {int(peak_years.min())}–{int(peak_years.max())}) แสดงว่าชุดข้อมูลเก็บหนังยอดนิยมเป็นโควตาต่อปี "
            "จำนวนหนังในกราฟนี้จึงไม่ได้สะท้อนขนาดของอุตสาหกรรมภาพยนตร์จริง "
            f"ส่วนปีที่มีน้อยที่สุดคือ {int(counts.idxmin())} ({int(counts.min()):,} เรื่อง)"
        )
    else:
        count_caption = (
            f"ข้อมูลมีหนังมากที่สุดในปี {peak_year} ({int(counts.max()):,} เรื่อง) "
            f"และน้อยที่สุดในปี {int(counts.idxmin())} ({int(counts.min()):,} เรื่อง)"
        )
    money_caption = (
        f"ทุนสร้างเฉลี่ยเปลี่ยนจาก {format_money(money_kept.loc[first_year, 'budget'])} ในปี {first_year} "
        f"ไปสูงสุดที่ {format_money(money_kept['budget'].max())} ในปี {budget_peak_year} "
        f"ส่วนรายได้เฉลี่ยสูงสุดอยู่ที่ปี {gross_peak_year} ({format_money(money_kept['gross'].max())})"
    )
    if (money_kept["gross"] > money_kept["budget"]).all():
        money_caption += " และรายได้เฉลี่ยสูงกว่าทุนสร้างเฉลี่ยในทุกปีที่แสดง"
    return {
        "ok": True,
        "count_chart": {"labels": [int(y) for y in counts.index], "values": [int(v) for v in counts.values]},
        "money_chart": {
            "labels": [int(y) for y in money_kept.index],
            "budget": [float(v) for v in money_kept["budget"]],
            "gross": [float(v) for v in money_kept["gross"]],
            "counts": [int(v) for v in money_kept["n"]],
        },
        "count_caption": count_caption,
        "money_caption": money_caption,
        "money_left_out": money_left_out,
    }


def top_by_total_gross(df, column, n=TOP_N):
    data = df[[column, "gross"]].dropna()
    grouped = data.groupby(column)["gross"].agg(["sum", "count"]).sort_values("sum", ascending=False)
    top = grouped.head(n)
    return [
        {"label": name, "value": float(row["sum"]), "count": int(row["count"])}
        for name, row in top.iterrows()
    ], float(data["gross"].sum())


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


# ---------------------------------------------------------------------------
# Data quality and page assembly
# ---------------------------------------------------------------------------

def data_limitations(df):
    total = len(df)
    fin = len(financial_rows(df))
    return {
        "total": total,
        "missing_budget": int(df["budget"].isna().sum()),
        "missing_gross": int(df["gross"].isna().sum()),
        "financial_rows": fin,
        "financial_share": fin / total * 100 if total else 0,
        "year_min": int(df["year"].min()) if total else None,
        "year_max": int(df["year"].max()) if total else None,
    }


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


def run_analysis(df):
    """Everything the analysis page needs, recomputed from the current data."""
    return {
        "limitations": data_limitations(df),
        "stats": descriptive_stats(df),
        "correlation": correlation_matrix(df),
        "q1": budget_vs_gross(df),
        "q2": genre_performance(df),
        "q3": yearly_trends(df),
        "q4": top_earners(df),
        "q5": runtime_vs_score(df),
        "q6": roi_by_genre(df),
        "min_genre_count": MIN_GENRE_COUNT,
        "min_year_financial": MIN_YEAR_FINANCIAL,
    }
