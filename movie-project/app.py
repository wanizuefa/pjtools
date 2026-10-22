"""CineScope - Flask entry point (routes only).

Run with:
    pip install -r requirements.txt
    python app.py
"""

import math
import re
from datetime import date

from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   url_for)

import analysis
import data_service

# ---------------------------------------------------------------------------
# Project settings - edit these values for your group
# ---------------------------------------------------------------------------

SITE_NAME = "CineScope"
SITE_TAGLINE = "ทุกความสำเร็จของหนัง มีตัวเลขเล่าเรื่อง"

# Group name and members, shown in the footer of every page.
GROUP = {
    "name": "CineScope",
    "members": [
        "นางสาว วนิดา พิทักษ์วัฒนานนท์ 67050499",
        "นางสาว สิริกร เจียรนัยเจริญ 67050572",
        "นางสาว สุธีมนต์ บุญถนอม 67050592",
        "นาย ภัทรดนัย บุญแก้ว 67051052",
    ],
}
DATA_SOURCE = "Movie Industry dataset (movies.csv) - 7,668 movies, 1980-2020"

# Paste your Tableau Public link here, for example:
#   "https://public.tableau.com/views/MovieIndustry/Dashboard"
# Leave it empty to show setup instructions on the Dashboard page.
TABLEAU_URL = "https://public.tableau.com/views/Dashboard_17926785905460/Dashboard1?:language=en-US&publish=yes&:sid=&:redirect=auth&:display_count=n&:origin=viz_share_link"

# Sheet name of each chart inside the same Tableau workbook: the last part of
# the sheet's link, https://public.tableau.com/views/<Workbook>/<Sheet>.
# The Dashboard page shows every chart on its own, then the full dashboard.
# Update these if the sheets are renamed in Tableau and published again.
TABLEAU_SHEETS = {
    "year": "sheet0",       # จำนวนหนังและรายได้ตามปี
    "genre": "sheet1",      # รายได้เฉลี่ยตามประเภท
    "scatter": "sheet2",    # ทุนสร้างเทียบรายได้
    "country": "sheet3",    # แผนที่จำนวนหนังตามประเทศ
    "company": "Top10",     # Top 10 บริษัท
}

# One color per genre, shared by every page and every chart.
# Tuned in OKLCH so every color has the same weight and stays readable on the
# dark navy background (lightness 0.52-0.67, contrast >= 3:1). Charts always
# print the genre name next to its color, so color is never the only cue.
GENRE_COLORS = {
    "Comedy": "#ae9203",
    "Action": "#d73337",
    "Drama": "#8b50cf",
    "Crime": "#067398",
    "Biography": "#b65400",
    "Adventure": "#2f9f3d",
    "Animation": "#468de5",
    "Horror": "#02a99b",
    "Fantasy": "#cf48ab",
    "Mystery": "#6b6cd0",
    "Thriller": "#d7506e",
    "Family": "#029e72",
    "Sci-Fi": "#01a4b9",
    "Romance": "#d76797",
    "Western": "#a67537",
    "Musical": "#cf6872",
    "Music": "#a75fb7",
    "History": "#95752a",
    "Sport": "#64a737",
}
DEFAULT_GENRE_COLOR = "#7c8799"

# Navbar entries: (endpoint, label, emoji), the same on every page.
NAV_ITEMS = [
    ("home", "หน้าแรก", ""),
    ("movies", "รายการหนัง", ""),
    ("analysis", "วิเคราะห์ข้อมูล", ""),
    ("simulator", "Box Office Simulator", ""),
    ("dashboard", "Dashboard", ""),
]

PER_PAGE = 20

app = Flask(__name__)
app.config["SECRET_KEY"] = "cinescope-data-tools-project"
app.json.ensure_ascii = False


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

def is_missing(value):
    return value is None or (isinstance(value, float) and math.isnan(value))


app.add_template_filter(analysis.format_money, "money")


@app.template_filter("number")
def format_number(value, decimals=0):
    """Thousands separators, or an em dash when missing."""
    if is_missing(value):
        return "—"
    return f"{float(value):,.{decimals}f}"


@app.template_filter("text")
def format_text(value):
    return "—" if is_missing(value) or value == "" else value


def genre_color(genre):
    return GENRE_COLORS.get(genre, DEFAULT_GENRE_COLOR)


def nav_items():
    """Navbar links with the current page marked (the add/edit form counts as "movies")."""
    endpoint = request.endpoint or ""
    current = "movies" if endpoint.startswith("movie") else endpoint
    return [
        {"url": url_for(name), "label": label, "icon": icon, "active": name == current}
        for name, label, icon in NAV_ITEMS
    ]


@app.context_processor
def inject_site_info():
    """Make site and group info available in every template."""
    return {
        "site_name": SITE_NAME,
        "site_tagline": SITE_TAGLINE,
        "group": GROUP,
        "data_source": DATA_SOURCE,
        "tableau_url": TABLEAU_URL,
        "genre_colors": GENRE_COLORS,
        "genre_color": genre_color,
        "nav_items": nav_items,
        "current_year": date.today().year,
    }


# ---------------------------------------------------------------------------
# Request helpers
# ---------------------------------------------------------------------------

def parse_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def safe_next(target, fallback):
    """Only allow redirects to paths on this site (prevents open redirects)."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return fallback


def current_path():
    """Current path + query string, used as the 'next' link back to a list view."""
    return request.full_path.rstrip("?")


def to_form_values(movie):
    """Convert a stored movie into strings for the form inputs."""
    values = {}
    for col in data_service.COLUMNS:
        value = movie.get(col)
        if is_missing(value):
            values[col] = ""
        elif isinstance(value, float) and value.is_integer():
            values[col] = str(int(value))
        else:
            values[col] = str(value)
    return values


@app.errorhandler(data_service.MovieNotFoundError)
def handle_movie_not_found(error):
    flash(str(error), "error")
    return redirect(url_for("movies"))


@app.errorhandler(data_service.ExcelLockedError)
def handle_excel_locked(error):
    flash(str(error), "error")
    return redirect(url_for("movies"))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    """Home: headline counters, key findings and the movie of the day."""
    df = data_service.load_movies()
    return render_template(
        "index.html",
        summary=analysis.home_summary(df),
        findings=analysis.key_findings(df),
        featured=analysis.featured_movie(df, date.today()),
        featured_min_score=analysis.FEATURED_MIN_SCORE,
    )


@app.route("/movies")
def movies():
    """Movie list with search, filters, sorting and pagination (all in the URL)."""
    df = data_service.load_movies()
    choices = data_service.get_choices(df)

    filters = {
        "q": request.args.get("q", "").strip(),
        "genre": request.args.get("genre", ""),
        "rating": request.args.get("rating", ""),
        "year_min": parse_int(request.args.get("year_min")),
        "year_max": parse_int(request.args.get("year_max")),
        "sort": request.args.get("sort", "year"),
        "order": "asc" if request.args.get("order") == "asc" else "desc",
    }
    if filters["sort"] not in data_service.SORTABLE_COLUMNS:
        filters["sort"] = "year"

    result = data_service.search_movies(
        df, page=parse_int(request.args.get("page")) or 1, per_page=PER_PAGE, **filters
    )

    def page_url(**changes):
        """URL of the list with the current filters plus `changes`."""
        args = {key: value for key, value in filters.items() if value not in (None, "")}
        args.update(changes)
        args = {key: value for key, value in args.items() if value not in (None, "")}
        return url_for("movies", **args)

    return render_template(
        "movies.html",
        filters=filters,
        result=result,
        choices=choices,
        year_bounds=(int(df["year"].min()), int(df["year"].max())),
        page_url=page_url,
        per_page=PER_PAGE,
        next_url=current_path(),
        has_filters=any(request.args.get(key) for key in
                        ("q", "genre", "rating", "year_min", "year_max")),
    )


@app.route("/movies/new", methods=["GET", "POST"])
def movie_new():
    return movie_form()


@app.route("/movies/<int:movie_id>/edit", methods=["GET", "POST"])
def movie_edit(movie_id):
    return movie_form(movie_id)


def movie_form(movie_id=None):
    """Shared add/edit form: validate, write to Excel, then redirect."""
    is_edit = movie_id is not None
    next_url = safe_next(request.values.get("next"), url_for("movies"))
    errors = {}
    status = 200

    if request.method == "POST":
        values = request.form.to_dict()
        record, errors = data_service.validate_movie(values)
        if errors:
            status = 400
        else:
            try:
                if is_edit:
                    data_service.update_movie(movie_id, record)
                    flash(f'แก้ไขข้อมูล "{record["name"]}" ลงไฟล์ Excel เรียบร้อยแล้ว', "success")
                    return redirect(next_url)
                new_id = data_service.add_movie(record)
                flash(f'เพิ่ม "{record["name"]}" (รหัส {new_id}) ลงไฟล์ Excel เรียบร้อยแล้ว', "success")
                return redirect(url_for("movies", q=record["name"]))
            except data_service.ExcelLockedError as error:
                # Keep the user's input on screen so nothing is lost.
                flash(str(error), "error")
                status = 423
    else:
        values = to_form_values(data_service.get_movie(movie_id)) if is_edit else {}

    return render_template(
        "form.html",
        is_edit=is_edit,
        movie_id=movie_id,
        values=values,
        errors=errors,
        choices=data_service.get_choices(),
        next_url=next_url,
    ), status


@app.route("/movies/<int:movie_id>/delete", methods=["POST"])
def movie_delete(movie_id):
    next_url = safe_next(request.form.get("next"), url_for("movies"))
    movie = data_service.get_movie(movie_id)
    try:
        data_service.delete_movie(movie_id)
        flash(f'ลบ "{movie["name"]}" ออกจากไฟล์ Excel เรียบร้อยแล้ว', "success")
    except data_service.ExcelLockedError as error:
        flash(str(error), "error")
    return redirect(next_url)


@app.route("/analysis", endpoint="analysis")
def analysis_page():
    """Results the group computed with Excel's Analysis ToolPak (data/analysis.xlsx)."""
    report = analysis.toolpak_report(data_service.load_movies(), data_service.read_toolpak_results())
    return render_template("analysis.html", report=report)


# ---------------------------------------------------------------------------
# Box Office Simulator
# ---------------------------------------------------------------------------

_simulator_cache = {"version": None, "models": None}


def simulator_models():
    """Regression models, rebuilt only when the Excel file has changed."""
    version = data_service.data_version()
    if _simulator_cache["version"] != version:
        _simulator_cache["models"] = analysis.build_simulator_models(data_service.load_movies())
        _simulator_cache["version"] = version
    return _simulator_cache["models"]


def parse_simulation_input(payload, models, ratings):
    """Validate simulator input. Returns (values, errors) with Thai messages."""
    ranges = models["ranges"]
    errors = {}

    def number(field, label, low, high, separator=","):
        try:
            value = float(payload.get(field))
        except (TypeError, ValueError):
            errors[field] = f"{label}ต้องเป็นตัวเลข"
            return None
        if not low <= value <= high:
            spec = f"{separator}.0f"
            errors[field] = f"{label}ต้องอยู่ระหว่าง {low:{spec}} ถึง {high:{spec}}"
            return None
        return value

    genre = str(payload.get("genre") or "")
    if genre not in models["genres"]:
        errors["genre"] = "กรุณาเลือกประเภทหนังจากรายการ"
    rating = str(payload.get("rating") or "")
    if rating and rating not in ratings:
        errors["rating"] = "กรุณาเลือกเรทจากรายการ"

    values = {
        "genre": genre,
        "rating": rating,
        "budget": number("budget", "ทุนสร้าง", ranges["budget_min"], ranges["budget_max"]),
        "runtime": number("runtime", "ความยาว", ranges["runtime_min"], ranges["runtime_max"]),
        "year": number("year", "ปีที่ฉาย", ranges["year_min"], ranges["year_max"], separator=""),
    }
    return values, errors


@app.route("/simulator")
def simulator():
    models = simulator_models()
    choices = data_service.get_choices()
    return render_template("simulator.html", models=models, ratings=choices["rating"])


@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    """Predict gross, ROI and score for an imaginary movie (JSON in, JSON out)."""
    models = simulator_models()
    if models is None:
        return jsonify({"ok": False, "error": "ข้อมูลยังไม่พอสำหรับสร้างโมเดล"}), 503

    payload = request.get_json(silent=True) or request.form
    ratings = data_service.get_choices()["rating"]
    values, errors = parse_simulation_input(payload, models, ratings)
    if errors:
        return jsonify({"ok": False, "error": "ข้อมูลไม่ถูกต้อง", "errors": errors}), 400

    result = analysis.simulate(
        models, data_service.load_movies(),
        genre=values["genre"], budget=values["budget"], runtime=values["runtime"],
        year=int(values["year"]), rating=values["rating"],
    )
    return jsonify({"ok": True, "input": values, **result})


# ---------------------------------------------------------------------------
# Dashboard (Tableau Public)
# ---------------------------------------------------------------------------

TABLEAU_EMBED_OPTIONS = ":embed=y&:showVizHome=no&:toolbar=yes&:display_count=no&:tabs=no"


def tableau_parts(url):
    """(workbook, view) from a Tableau Public link, or (None, None).

    Accepts both link styles Tableau Public gives out:
      https://public.tableau.com/views/<Workbook>/<Sheet>?...
      https://public.tableau.com/app/profile/<user>/viz/<Workbook>/<Sheet>
    """
    match = re.search(r"/(?:views|viz)/([^/?#]+)/([^/?#]+)", url or "")
    return (match.group(1), match.group(2)) if match else (None, None)


def tableau_links(workbook, view):
    """Embeddable iframe URL and the normal public page of one Tableau view."""
    page = f"https://public.tableau.com/views/{workbook}/{view}"
    return {"embed": f"{page}?{TABLEAU_EMBED_OPTIONS}", "page": page}


@app.route("/dashboard")
def dashboard():
    workbook, view = tableau_parts(TABLEAU_URL)
    combined = tableau_links(workbook, view) if workbook else None
    sheets = {
        key: tableau_links(workbook, sheet)
        for key, sheet in TABLEAU_SHEETS.items()
        if workbook and sheet
    }
    return render_template(
        "dashboard.html",
        combined=combined,
        sheets=sheets,
        highlights=analysis.dashboard_highlights(data_service.load_movies()),
    )


@app.route("/api/status")
def api_status():
    """Data status check: confirms the Excel file loads and is cleaned."""
    df = data_service.load_movies()
    return jsonify({
        "site": SITE_NAME,
        "excel_file": data_service.XLSX_PATH,
        "movies": int(len(df)),
        "year_range": [int(df["year"].min()), int(df["year"].max())],
        "rows_missing_budget": int(df["budget"].isna().sum()),
        "rows_with_budget_and_gross": int(df["profit"].notna().sum()),
        "ratings": df["rating"].value_counts().to_dict(),
    })


if __name__ == "__main__":
    if data_service.ensure_excel():
        print("Created data/movies.xlsx from data/movies.csv")
    app.run(debug=True)
