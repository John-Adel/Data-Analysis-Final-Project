"""GoBike Insights: four full-screen, cross-filtered slides for the Ford GoBike February 2019 trips."""
import json
import traceback
from urllib.parse import quote
from contextvars import ContextVar
from functools import wraps

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import (ALL, Dash, Input, Output, State, callback, clientside_callback, ctx, dcc, html,
                  no_update)

from dashboard.db import AGE_LABELS, DAY_ORDER, REGIONS, df

FONTS = ("https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;"
         "12..96,700;12..96,800&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&display=swap")

app = Dash(__name__, external_stylesheets=[FONTS], suppress_callback_exceptions=True)
app.title = "GoBike Insights"
server = app.server

# ── Colour system ──────────────────────────────────────────────────────────
BLUE, CORAL, TEAL, SUN, VIOLET, PINK, SLATE = ("#3D5AFE", "#FF6B4A", "#10B9A5", "#FFB020",
                                              "#8B5CF6", "#F0487F", "#8A93B2")
USER_COLORS = {"Subscriber": BLUE, "Customer": CORAL}
GENDER_COLORS = {"Male": BLUE, "Female": PINK, "Other": SUN, "Unknown": SLATE}
REGION_COLORS = {"San Francisco": BLUE, "East Bay": TEAL, "San Jose": SUN}

THEMES = {
    "light": dict(text="#161C38", muted="#646E8F", grid="rgba(40,60,130,0.08)", line="#E3E7F2",
                  surface="#FFFFFF", sel="#161C38", track="#F0F2FA", weekend="rgba(255,107,74,0.09)",
                  fill=0.12, dim=0.2, map="carto-positron",
                  heat=[[0, "#EEF1FB"], [0.25, "#C3CCFF"], [0.55, BLUE], [0.8, VIOLET], [1, PINK]]),
    "dark": dict(text="#EEF1FB", muted="#9BA4C7", grid="rgba(170,185,240,0.10)", line="#2C3466",
                 surface="#1A1F42", sel=SUN, track="#222857", weekend="rgba(255,107,74,0.10)",
                 fill=0.18, dim=0.25, map="carto-darkmatter",
                 heat=[[0, "#1F2552"], [0.25, "#2B3A9C"], [0.55, BLUE], [0.8, VIOLET], [1, SUN]]),
}
_THEME = ContextVar("theme", default="light")


def T():
    return THEMES[_THEME.get()]


AGE_ORDER = AGE_LABELS + ["Unknown"]
DAY_SHORT = {d: d[:3] for d in DAY_ORDER}
DUR_MAX = int(np.ceil(df["duration_min"].max()))
ALL_USER = sorted(df["user_type"].cat.categories)
ALL_GENDER = [g for g in ["Male", "Female", "Other", "Unknown"] if g in set(df["gender"].cat.categories)]
D_MIN, D_MAX = df["date"].min().date(), df["date"].max().date()
N_ALL = len(df)
MONTH_AVG = df["duration_min"].mean()
N_STATIONS = pd.concat([df["start_station"].astype(str), df["end_station"].astype(str)]).nunique()

SLIDES = [
    ("Overview", "February 2019, ride by ride", "The month at a glance"),
    ("When", "When the Bay Area rides", "Hours, days and the commute"),
    ("Who", "Who is riding", "The people behind the trips"),
    ("Where", "Where trips start and end", "Stations, routes and flows"),
]

DIMS = {
    "trend": "date", "region": "region", "utype_o": "user_type",
    "heat": "dayhour", "weekday": "day", "hourly": "hour", "durhour": "hour",
    "utype": "user_type", "gender": "gender", "age": "age_group", "agedur": "age_group",
    "map": "station", "rank": "station",
}
DIM_LABEL = {"date": "Date", "region": "Area", "user_type": "Rider", "day": "Day", "hour": "Hour",
             "dayhour": "Slot", "gender": "Gender", "age_group": "Age", "station": "Station",
             "route": "Route"}


# ── Helpers ────────────────────────────────────────────────────────────────
def rgba(hex_color, a):
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def hour_label(h):
    h = int(h)
    return f"{(h % 12) or 12} {'AM' if h < 12 else 'PM'}"


def short(name, n=30):
    name = str(name)
    return name if len(name) <= n else name[: n - 1].rstrip() + "…"


def paint(cats, selected, color, colors=None):
    base = [colors.get(c, color) if colors else color for c in cats]
    if selected is None:
        return base
    return [b if c == selected else rgba(b, T()["dim"]) for c, b in zip(cats, base)]


def fin(fig, anim=True, **kw):
    t = T()
    fig.update_layout(
        template="none", autosize=True, uirevision="keep", clickmode="event",
        font=dict(family="DM Sans, system-ui, sans-serif", size=12, color=t["muted"]),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="#161C38", bordercolor="#161C38",
                        font=dict(family="DM Sans, sans-serif", color="#FFFFFF", size=12)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=t["text"], size=12)),
        margin=dict(t=6, l=6, r=6, b=6), bargap=0.3, hovermode="closest", showlegend=False,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, showline=False, automargin=True,
                     tickfont=dict(color=t["muted"]), ticks="")
    fig.update_yaxes(gridcolor=t["grid"], zeroline=False, showline=False, automargin=True,
                     tickfont=dict(color=t["muted"]), ticks="")
    if anim:
        fig.update_layout(transition=dict(duration=320, easing="cubic-out"))
    fig.update_layout(**kw)
    return fig


def empty(msg="No trips match. Widen the filters or clear a selection."):
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font=dict(size=13, color=T()["muted"]))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fin(fig, anim=False)


# ── Filtering ──────────────────────────────────────────────────────────────
def base_mask(start, end, users, genders, ages, dur, regions):
    if not (users and genders and ages and regions):
        return np.zeros(N_ALL, dtype=bool)
    lo, hi = (dur or [0, DUR_MAX])
    return (df["date"].between(pd.to_datetime(start), pd.to_datetime(end))
            & df["user_type"].isin(users) & df["gender"].isin(genders)
            & df["age_group"].isin(ages) & df["region"].isin(regions)
            & df["duration_min"].between(lo, hi)).to_numpy()


def dim_mask(dim, v):
    if dim == "date":
        m = df["date"] == pd.Timestamp(v)
    elif dim == "day":
        m = df["day_of_week"] == v
    elif dim == "hour":
        m = df["hour"] == int(v)
    elif dim == "dayhour":
        m = (df["day_of_week"] == v[0]) & (df["hour"] == int(v[1]))
    elif dim == "station":
        m = (df["start_station"] == v) | (df["end_station"] == v)
    elif dim == "route":
        m = (df["start_station"] == v[0]) & (df["end_station"] == v[1])
    else:
        m = df[dim] == v
    return m.to_numpy()


class View:
    """get(*exclude) skips selections on those dimensions, so the chart that owns a
    selection keeps every category visible and just highlights the chosen one."""

    def __init__(self, filters, xf):
        self.filters = filters
        self.base = base_mask(*filters)
        self.xf = xf or {}
        self.xm = {d: dim_mask(d, v) for d, v in self.xf.items()}

    def get(self, *exclude):
        m = self.base.copy()
        for d, mm in self.xm.items():
            if d not in exclude:
                m &= mm
        return df[m]

    def sel(self, dim):
        return self.xf.get(dim)


FILTERS = [Input("date-range", "start_date"), Input("date-range", "end_date"),
           Input("f-user", "value"), Input("f-gender", "value"), Input("f-age", "value"),
           Input("f-dur", "value"), Input("f-region", "value")]
XF = Input("xf", "data")
THEME = Input("theme", "data")


SLIDE = Input("slide", "data")
SPIKE = dict(showspikes=True, spikemode="across", spikesnap="data", spikethickness=1,
             spikedash="dot", spikecolor="rgba(120,130,170,0.6)")


def charts(idx, n, extra=0, tail=()):
    """Chart callback wrapper.
    Only the visible slide is rendered, and a slide is never re-rendered for the same
    filters, selections and theme. That keeps clicks and slide changes instant."""
    def deco(fn):
        @wraps(fn)
        def inner(*args):
            *core, slide_i, theme, last = args
            total = n + len(tail) + 1
            if slide_i != idx:
                return (no_update,) * total
            theme = theme if theme in THEMES else "light"
            extras = tuple(core[len(core) - extra:]) if extra else ()
            core = core[:len(core) - extra] if extra else core
            f, xf = tuple(core[:-1]), core[-1]
            key = json.dumps([f, xf, extras, theme], default=str, sort_keys=True)
            if key == last:
                return (no_update,) * total
            _THEME.set(theme)
            try:
                out = fn(View(f, xf), *extras)
            except Exception as e:
                traceback.print_exc()
                out = (empty("Chart error: " + str(e)[:110]),) * n + tuple(tail)
            return (*out, key)
        return inner
    return deco


def track(cats, top, horizontal=False):
    """Soft full-height column behind each bar. It lights up under the pointer."""
    kw = dict(y=cats, x=[top] * len(cats), orientation="h") if horizontal else dict(x=cats, y=[top] * len(cats))
    return go.Bar(**kw, customdata=cats, meta="track", hoverinfo="none", showlegend=False,
                  marker=dict(color=T()["track"], cornerradius=8, line=dict(width=0)))


def spark(vals, color, bars=None):
    """Tiny inline SVG sparkline for the KPI cards (served as a data URI)."""
    v = np.nan_to_num(np.asarray(vals, dtype=float))
    if len(v) < 2:
        return None
    W, H = 120, 38
    mn, mx = (0.0, v.max()) if bars else (v.min(), v.max())
    rng = (mx - mn) or 1.0
    if bars:
        n = len(v)
        bw = W / n
        rects = "".join(
            f'<rect x="{i * bw + bw * .18:.1f}" y="{H - 2 - (x - mn) / rng * (H - 6):.1f}" width="{bw * .64:.1f}" '
            f'height="{(x - mn) / rng * (H - 6) + 0.5:.1f}" rx="2" fill="{bars[i]}"/>' for i, x in enumerate(v))
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none">{rects}</svg>'
    else:
        xs = np.linspace(1, W - 1, len(v))
        ys = H - 3 - (v - mn) / rng * (H - 10)
        line = " L".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none">'
               f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{color}" stop-opacity=".38"/>'
               f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
               f'<path d="M1,{H} L{line} L{W - 1},{H} Z" fill="url(#g)"/>'
               f'<path d="M{line}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" '
               f'stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>')
    return "data:image/svg+xml;utf8," + quote(svg)


# ── Layout pieces ──────────────────────────────────────────────────────────
BLANK = {"data": [], "layout": {"xaxis": {"visible": False}, "yaxis": {"visible": False},
                                "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
                                "margin": {"t": 0, "l": 0, "r": 0, "b": 0}}}


def graph(key, clickable=True):
    gid = {"type": "xf", "key": key} if clickable else key
    return dcc.Graph(id=gid, figure=BLANK, config={"displayModeBar": False, "responsive": True,
                                     "scrollZoom": key == "map"},
                     style={"height": "100%", "width": "100%"},
                     className="chart" + (" is-clickable" if clickable else ""))


def panel(title, child, note=None, area="", d=0, extra_head=None, hint=True, cls="", accent=BLUE):
    head = [html.H3(title, className="panel-title")]
    if extra_head is not None:
        head.append(extra_head)
    elif note:
        head.append(html.Span(note, className="panel-note"))
    elif hint:
        head.append(html.Span("Click to filter", className="panel-note tap"))
    return html.Section([html.Div(head, className="panel-head"),
                         html.Div(child, className="panel-body")],
                        className=f"panel {cls}", style={"gridArea": area, "--d": d, "--accent": accent})


def slide(i, body, cls):
    _, title, desc = SLIDES[i]
    return html.Div([
        html.Div([html.H2(title, className="slide-title"), html.P(desc, className="slide-desc")],
                 className="slide-head"),
        *body,
    ], className="slide", id={"type": "slide", "index": i}, **{"data-layout": cls})


slide_overview = slide(0, [
    html.Div(id="kpis", className="kpi-band"),
    html.Div([
        panel("Trips per day", graph("trend"), note="Weekends shaded. Click a day to focus it",
              area="trend", d=1),
        html.Section([html.Div(html.H3("What stands out", className="panel-title"), className="panel-head"),
                      html.Div(id="insights", className="insights")],
                     className="panel insights-panel", style={"gridArea": "ins", "--d": 2, "--accent": SUN}),
        panel("Trips by area", graph("region"), area="region", d=3, accent=TEAL),
        panel("Subscribers vs casual riders", graph("utype_o"), area="donut", d=4, accent=CORAL),
    ], className="grid"),
], "overview")

slide_time = slide(1, [html.Div([
    panel("Trips by day and hour", graph("heat"), note="Click a cell to focus that time slot", area="a", d=0),
    panel("Trips by weekday", graph("weekday"), area="b", d=1, accent=CORAL),
    panel("Hourly rhythm by rider type", graph("hourly"), area="c", d=2, accent=VIOLET),
    panel("Average ride length by hour", graph("durhour"), area="d", d=3, accent=TEAL),
], className="grid")], "time")

slide_riders = slide(2, [html.Div([
    panel("Rider type", graph("utype"), area="a", d=0, accent=CORAL),
    panel("Gender", graph("gender"), area="b", d=1, accent=PINK),
    panel("Age group", graph("age"), area="c", d=2, accent=VIOLET),
    panel("How long rides last", graph("durhist", clickable=False),
          note="First 60 minutes, which covers 99% of trips", area="d", d=3, accent=SUN),
    panel("Average ride by age", graph("agedur"), area="e", d=4, accent=TEAL),
], className="grid")], "riders")

rank_switch = dcc.RadioItems(
    id="rank-mode", value="start", className="seg",
    options=[{"label": "Starts", "value": "start"}, {"label": "Ends", "value": "end"},
             {"label": "Routes", "value": "route"}])

slide_stations = slide(3, [html.Div([
    panel("Station map", graph("map"), note="Dot size shows departures. Click a station",
          area="map", d=0, cls="map-panel"),
    panel("Busiest", graph("rank"), area="rank", d=1, extra_head=rank_switch, accent=VIOLET),
    html.Section(id="spotlight", className="panel spotlight", style={"gridArea": "spot", "--d": 2, "--accent": CORAL}),
], className="grid")], "stations")

route_nav = html.Nav([
    html.Div(className="route-line"),
    html.Div(id="route-fill", className="route-fill"),
    html.Div(html.Img(src=app.get_asset_url("bike.svg"), alt="", className="bike-img"),
             id="bike", className="bike"),
    html.Div([
        html.Button([html.Span(className="stop-dot"), html.Span(name, className="stop-name")],
                    id={"type": "nav", "index": i}, className="stop", n_clicks=0, title=title)
        for i, (name, title, _) in enumerate(SLIDES)
    ], className="stops"),
], className="route", **{"aria-label": "Slides"})

header = html.Header([
    html.Div([
        html.Div([html.Span("Go", className="brand-a"), html.Span("Bike", className="brand-b")], className="brand"),
        html.Div("Bay Area trip insights", className="brand-sub"),
    ], className="brand-wrap"),
    route_nav,
    html.Div([
        html.Button(id="theme-btn", className="icon-btn theme-btn", n_clicks=0, title="Switch light or dark"),
        html.Button([html.Span("Filters"), html.Span(id="filter-count", className="count")],
                    id="filter-btn", className="filter-btn", n_clicks=0),
    ], className="top-actions"),
], className="topbar")

toolbar = html.Div([
    html.Div(id="summary", className="summary"),
    html.Div(id="chips", className="chips"),
    html.Button("Clear selections", id="clear-xf", className="clear-xf", n_clicks=0),
    html.Div([
        html.Button("‹", id="prev-btn", className="pg-btn", n_clicks=0, title="Previous slide (←)"),
        html.Span(id="pg-count", className="pg-count"),
        html.Button("›", id="next-btn", className="pg-btn", n_clicks=0, title="Next slide (→)"),
    ], className="pager"),
], className="toolbar")

drawer = html.Aside([
    html.Div([html.H3("Filters", className="drawer-title"),
              html.Button("×", id="drawer-close", className="icon-btn", n_clicks=0,
                          **{"aria-label": "Close filters"})], className="drawer-head"),
    html.P("Filters apply to every slide. Clicking a chart adds a selection on top of them.",
           className="drawer-note"),
    html.Label("Dates", className="f-label"),
    dcc.DatePickerRange(id="date-range", start_date=D_MIN, end_date=D_MAX,
                        min_date_allowed=D_MIN, max_date_allowed=D_MAX, display_format="MMM D",
                        number_of_months_shown=1, minimum_nights=0, className="date-range"),
    html.Label("Area", className="f-label"),
    dcc.Checklist(id="f-region", options=REGIONS, value=REGIONS, className="pills"),
    html.Label("Rider type", className="f-label"),
    dcc.Checklist(id="f-user", options=ALL_USER, value=ALL_USER, className="pills"),
    html.Label("Gender", className="f-label"),
    dcc.Checklist(id="f-gender", options=ALL_GENDER, value=ALL_GENDER, className="pills"),
    html.Label("Age group", className="f-label"),
    dcc.Checklist(id="f-age", options=AGE_ORDER, value=AGE_ORDER, className="pills"),
    html.Label("Ride length (minutes)", className="f-label"),
    dcc.RangeSlider(id="f-dur", min=0, max=DUR_MAX, step=1, value=[0, DUR_MAX],
                    marks={i: str(i) for i in range(0, DUR_MAX + 1, 30)},
                    tooltip={"placement": "bottom", "always_visible": False}),
    html.Div([
        html.Button("Reset everything", id="reset", className="btn ghost", n_clicks=0),
        html.Button("Download filtered CSV", id="download-btn", className="btn solid", n_clicks=0),
    ], className="drawer-actions"),
    dcc.Download(id="download-data"),
], id="drawer", className="drawer")

app.layout = html.Div([
    dcc.Store(id="slide", data=0),
    dcc.Store(id="slide-names", data=[s[0] for s in SLIDES]),
    dcc.Store(id="xf", data={}),
    dcc.Store(id="theme", data="light", storage_type="local"),
    *[dcc.Store(id=f"rk-{i}") for i in range(4)],
    html.Div(className="backdrop"),
    header,
    toolbar,
    html.Main([slide_overview, slide_time, slide_riders, slide_stations], className="stage"),
    html.Div(id="scrim", className="scrim", n_clicks=0),
    drawer,
], id="app", className="app theme-light")


# ── Client-side: navigation, theme, drawer ────────────────────────────────
clientside_callback(
    """
    function(navClicks, prev, next, cur) {
        const trig = dash_clientside.callback_context.triggered;
        if (!trig || !trig.length || !trig[0].value) { return dash_clientside.no_update; }
        const pid = trig[0].prop_id, id = pid.slice(0, pid.lastIndexOf('.'));
        const n = %d;
        if (id === 'prev-btn') { return Math.max(0, cur - 1); }
        if (id === 'next-btn') { return Math.min(n - 1, cur + 1); }
        try { const o = JSON.parse(id); if (o.type === 'nav') { return o.index; } } catch (e) {}
        return dash_clientside.no_update;
    }
    """ % len(SLIDES),
    Output("slide", "data"),
    Input({"type": "nav", "index": ALL}, "n_clicks"), Input("prev-btn", "n_clicks"),
    Input("next-btn", "n_clicks"), State("slide", "data"), prevent_initial_call=True,
)

clientside_callback(
    """
    function(cur, names) {
        const n = names.length;
        const slides = names.map((_, i) => 'slide' + (i === cur ? ' active' : (i < cur ? ' before' : ' after')));
        const stops = names.map((_, i) => 'stop' + (i === cur ? ' active' : (i < cur ? ' passed' : '')));
        const pct = (cur / (n - 1)) * 100;
        window.__gbPrev = (window.__gbPrev === undefined) ? cur : window.__gbPrev;
        const dir = cur >= window.__gbPrev ? 'fwd' : 'back';
        const moving = cur !== window.__gbPrev;
        window.__gbPrev = cur;
        return [slides, stops,
                {left: 'calc(' + pct + '% * var(--route-span) + var(--route-start))'},
                'bike ' + dir + (moving ? (cur % 2 ? ' ride-a' : ' ride-b') : ''),
                {width: 'calc(' + pct + '% * var(--route-span))'},
                cur === 0, cur === n - 1, (cur + 1) + ' / ' + n];
    }
    """,
    Output({"type": "slide", "index": ALL}, "className"),
    Output({"type": "nav", "index": ALL}, "className"),
    Output("bike", "style"), Output("bike", "className"), Output("route-fill", "style"),
    Output("prev-btn", "disabled"), Output("next-btn", "disabled"), Output("pg-count", "children"),
    Input("slide", "data"), State("slide-names", "data"),
)

clientside_callback(
    """
    function(n, theme) {
        if (!n) { return dash_clientside.no_update; }
        return theme === 'dark' ? 'light' : 'dark';
    }
    """,
    Output("theme", "data"), Input("theme-btn", "n_clicks"), State("theme", "data"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(theme) {
        const t = theme === 'dark' ? 'dark' : 'light';
        document.documentElement.style.colorScheme = t;
        return ['app theme-' + t, t === 'dark' ? '☀' : '☾'];
    }
    """,
    Output("app", "className"), Output("theme-btn", "children"), Input("theme", "data"),
)

clientside_callback(
    """
    function(a, b, c, cls) {
        const trig = dash_clientside.callback_context.triggered;
        if (!trig || !trig.length || !trig[0].value) { return [dash_clientside.no_update, dash_clientside.no_update]; }
        const open = trig[0].prop_id.startsWith('filter-btn') && !(cls || '').includes('open');
        return [open ? 'drawer open' : 'drawer', open ? 'scrim open' : 'scrim'];
    }
    """,
    Output("drawer", "className"), Output("scrim", "className"),
    Input("filter-btn", "n_clicks"), Input("drawer-close", "n_clicks"), Input("scrim", "n_clicks"),
    State("drawer", "className"), prevent_initial_call=True,
)


# ── Cross-filter state ─────────────────────────────────────────────────────
def parse_click(key, p):
    dim = DIMS[key]
    if key == "heat":
        return dim, [p["y"], int(p["x"])]
    if key in ("utype", "utype_o"):
        return dim, p.get("label")
    cd = p.get("customdata")
    if key == "rank" and isinstance(cd, list) and len(cd) == 2:
        return "route", cd
    if isinstance(cd, list):
        cd = cd[0]
    if dim == "date" and cd:
        cd = str(cd)[:10]
    if dim == "hour" and cd is not None:
        cd = int(cd)
    return dim, cd


@callback(
    Output("xf", "data"), Output({"type": "xf", "key": ALL}, "clickData"),
    Input({"type": "xf", "key": ALL}, "clickData"),
    Input({"type": "chip-x", "dim": ALL, "src": ALL}, "n_clicks"),
    Input({"type": "pick", "name": ALL}, "n_clicks"),
    Input("clear-xf", "n_clicks"), Input("reset", "n_clicks"),
    State("xf", "data"), prevent_initial_call=True,
)
def update_xf(_clicks, _chips, _picks, _clear, _reset, xf):
    blank = [None] * len(ctx.outputs_list[1])
    keep = [no_update] * len(blank)
    trig, value = ctx.triggered_id, ctx.triggered[0]["value"]
    xf = dict(xf or {})
    if trig in ("clear-xf", "reset"):
        return {}, blank
    if not isinstance(trig, dict) or not value:
        return no_update, keep
    if trig["type"] == "chip-x":
        xf.pop(trig["dim"], None)
        return xf, keep
    if trig["type"] == "pick":
        dim, val = "station", trig["name"]
    else:
        dim, val = parse_click(trig["key"], value["points"][0])
        if val is None:
            return no_update, blank
    if xf.get(dim) == val:
        xf.pop(dim)
    else:
        xf[dim] = val
        if dim == "dayhour":
            xf.pop("day", None)
            xf.pop("hour", None)
        elif dim in ("day", "hour"):
            xf.pop("dayhour", None)
    return xf, blank


def chip_text(dim, v):
    if dim == "date":
        return pd.Timestamp(v).strftime("%a, %b ") + str(pd.Timestamp(v).day)
    if dim == "hour":
        return hour_label(v)
    if dim == "dayhour":
        return f"{v[0][:3]} {hour_label(v[1])}"
    if dim == "route":
        return f"{short(v[0], 20)} to {short(v[1], 20)}"
    if dim == "station":
        return short(v, 34)
    return str(v)


@callback(Output("chips", "children"), Output("clear-xf", "className"),
          Output("summary", "children"), Output("filter-count", "children"), *FILTERS, XF)
def toolbar_cb(*args):
    f, xf = args[:-1], args[-1] or {}
    n = int(View(f, xf).get().shape[0])
    chips = [html.Button([html.Span(DIM_LABEL[d], className="chip-k"),
                          html.Span(chip_text(d, val), className="chip-v"),
                          html.Span("×", className="chip-x")],
                         id={"type": "chip-x", "dim": d, "src": "bar"}, className="chip", n_clicks=0,
                         title="Remove this selection")
             for d, val in xf.items()]
    if not chips:
        chips = [html.Span("Tip: click any bar, cell, slice or station to filter every slide.",
                           className="chips-empty")]
    summary = [html.Strong(f"{n:,}", className="count-up"), html.Span(f" of {N_ALL:,} trips"),
               html.Span(className="meter", children=html.Span(style={"width": f"{n / N_ALL * 100:.1f}%"}))]
    start, end, users, genders, ages, dur, regions = f
    changed = sum([
        str(start)[:10] != str(D_MIN) or str(end)[:10] != str(D_MAX),
        set(users or []) != set(ALL_USER), set(genders or []) != set(ALL_GENDER),
        set(ages or []) != set(AGE_ORDER), set(regions or []) != set(REGIONS),
        list(dur or []) != [0, DUR_MAX],
    ])
    return chips, "clear-xf" + (" show" if xf else ""), summary, (str(changed) if changed else "")


@callback(Output("date-range", "start_date"), Output("date-range", "end_date"),
          Output("f-user", "value"), Output("f-gender", "value"), Output("f-age", "value"),
          Output("f-dur", "value"), Output("f-region", "value"),
          Input("reset", "n_clicks"), prevent_initial_call=True)
def reset_filters(_):
    return D_MIN, D_MAX, ALL_USER, ALL_GENDER, AGE_ORDER, [0, DUR_MAX], REGIONS


# ── Slide 1: overview ─────────────────────────────────────────────────────
def kpi(label, value, context, accent, hero=False, bar=None, sp=None):
    row = [html.Div(value, className="kpi-value count-up")]
    if sp:
        row.append(html.Img(src=sp, className="spark", alt=""))
    kids = [html.Div(label, className="kpi-label"), html.Div(row, className="kpi-row"),
            html.Div(context, className="kpi-context")]
    if bar is not None:
        kids.append(html.Div(html.Span(style={"width": f"{bar * 100:.1f}%"}), className="kpi-bar"))
    return html.Div(kids, className="kpi" + (" hero" if hero else ""), style={"--accent": accent})


def insight(color, strong, rest):
    return html.Div([html.Span(className="ins-dot", style={"background": color}),
                     html.P([html.Strong(strong), " ", rest])], className="ins")


@callback(Output("kpis", "children"), Output("insights", "children"), *FILTERS, XF)
def overview_text(*args):
    d = View(args[:-1], args[-1]).get()
    if d.empty:
        return ([kpi("Trips", "0", "Nothing matches the current filters", BLUE, hero=True)],
                [html.P("Widen the filters or clear a selection to see insights.", className="ins-empty")])
    n = len(d)
    avg = d["duration_min"].mean()
    delta = avg - MONTH_AVG
    bikes = d["bike_id"].nunique()
    stations = pd.concat([d["start_station"].astype(str), d["end_station"].astype(str)]).nunique()
    sub = (d["user_type"] == "Subscriber").mean()
    wknd = d["weekend_flag"].mean()
    share = f"{n / N_ALL:.0%}" if n / N_ALL >= 0.01 else "Under 1%"
    days_idx = pd.date_range(D_MIN, D_MAX)
    g = d.assign(is_sub=(d["user_type"] == "Subscriber")).groupby("date")
    daily = pd.DataFrame({
        "trips": g.size(), "dur": g["duration_min"].mean(), "bikes": g["bike_id"].nunique(),
        "st": g["start_station"].nunique(), "sub": g["is_sub"].mean(),
    }).reindex(days_idx)
    wk = d["day_of_week"].value_counts().reindex(DAY_ORDER, fill_value=0)
    wk_cols = [CORAL if k in ("Saturday", "Sunday") else "#C9CFE6" for k in DAY_ORDER]
    kpis = [
        kpi("Trips", f"{n:,}", f"{share} of all February trips", BLUE, hero=True, bar=n / N_ALL,
            sp=spark(daily["trips"].fillna(0), "#FFFFFF")),
        kpi("Average ride", f"{avg:.1f} min",
            "Same as the month average" if abs(delta) < 0.05 else
            f"{abs(delta):.1f} min {'longer' if delta > 0 else 'shorter'} than average", TEAL,
            sp=spark(daily["dur"].ffill().fillna(0), TEAL)),
        kpi("Bikes in use", f"{bikes:,}", f"{n / bikes:.1f} trips per bike", SUN,
            sp=spark(daily["bikes"].fillna(0), SUN)),
        kpi("Stations used", f"{stations:,}", f"of {N_STATIONS} in the network", VIOLET,
            sp=spark(daily["st"].fillna(0), VIOLET)),
        kpi("Subscribers", f"{sub:.0%}", f"{1 - sub:.0%} casual riders", PINK,
            sp=spark(daily["sub"].ffill().fillna(0), PINK)),
        kpi("Weekend trips", f"{wknd:.0%}", "Saturday and Sunday", CORAL,
            sp=spark(wk.values, CORAL, bars=wk_cols)),
    ]
    hours = d["hour"].value_counts()
    peak_h = int(hours.idxmax())
    days = d["day_of_week"].value_counts()
    peak_d = days.idxmax()
    n_peak_days = max(1, d.loc[d["day_of_week"] == peak_d, "date"].nunique())
    top_st = d["start_station"].value_counts()
    ins = [insight(BLUE, f"{hour_label(peak_h)} is the peak hour,",
                   f"with {hours.max() / n:.0%} of trips starting then."),
           insight(SUN, f"{peak_d} is the busiest day,",
                   f"averaging {days.max() / n_peak_days:,.0f} trips per {peak_d}.")]
    if top_st.max() > 0:
        ins.append(insight(TEAL, short(top_st.idxmax(), 40),
                           f"is the top starting point with {top_st.max():,} departures."))
    by_type = d.groupby("user_type", observed=True)["duration_min"].median()
    if {"Subscriber", "Customer"} <= set(by_type.index):
        ratio = by_type["Customer"] / by_type["Subscriber"]
        ins.append(insight(CORAL, f"Casual riders ride {ratio:.1f}× longer",
                           f"than subscribers ({by_type['Customer']:.0f} vs {by_type['Subscriber']:.0f} min median)."))
    wk = d[~d["weekend_flag"]]
    if len(wk):
        commute = wk["hour"].isin([7, 8, 9, 16, 17, 18]).mean()
        ins.append(insight(VIOLET, f"{commute:.0%} of weekday trips",
                           "fall in the 7 to 9 AM and 4 to 6 PM commute windows."))
    return kpis, ins


def donut(v, dim, colors):
    d = v.get(dim)
    if d.empty:
        return empty()
    s = d[dim].value_counts()
    s = s[s > 0]
    sel = v.sel(dim)
    t = T()
    fig = go.Figure(go.Pie(
        labels=list(s.index), values=s.values, hole=0.7, sort=False, direction="clockwise",
        marker=dict(colors=paint(list(s.index), sel, BLUE, colors), line=dict(color=t["surface"], width=4)),
        pull=[0.06 if k == sel else 0 for k in s.index], textinfo="none",
        hovertemplate="%{label}<br><b>%{value:,} trips</b> (%{percent})<extra></extra>"))
    lead = sel if sel in s.index else s.idxmax()
    fig.add_annotation(
        text=f"<b>{s[lead] / s.sum():.0%}</b><br><span style='font-size:12px;color:{t['muted']}'>{lead}</span>",
        showarrow=False, font=dict(size=26, color=t["text"], family="Bricolage Grotesque, DM Sans, sans-serif"))
    return fin(fig, anim=False, showlegend=True,
               legend=dict(orientation="v", x=1.0, y=0.5, xanchor="left", font=dict(color=t["text"])))


@callback(Output({"type": "xf", "key": "trend"}, "figure"),
          Output({"type": "xf", "key": "region"}, "figure"),
          Output({"type": "xf", "key": "utype_o"}, "figure"), Output("rk-0", "data"),
          *FILTERS, XF, SLIDE, THEME, State("rk-0", "data"))
@charts(0, 3)
def overview_charts(v):
    t = T()
    d = v.get("date")
    if d.empty:
        f1 = empty()
    else:
        daily = d.groupby("date").size().reindex(pd.date_range(D_MIN, D_MAX), fill_value=0)
        sel = v.sel("date")
        f1 = go.Figure()
        for day in daily.index:
            if day.dayofweek >= 5:
                f1.add_vrect(x0=day - pd.Timedelta(hours=12), x1=day + pd.Timedelta(hours=12),
                             fillcolor=t["weekend"], line_width=0, layer="below")
        on = [bool(sel) and str(x.date()) == sel for x in daily.index]
        f1.add_trace(go.Scatter(
            x=daily.index, y=daily.values, mode="lines+markers", fill="tozeroy",
            line=dict(color=BLUE, width=3, shape="spline", smoothing=0.35),
            fillgradient=dict(type="vertical", colorscale=[[0, rgba(BLUE, 0)], [1, rgba(BLUE, t["fill"] * 2.4)]]),
            marker=dict(size=[13 if o else 7 for o in on], color=[CORAL if o else BLUE for o in on],
                        line=dict(color=t["surface"], width=2)),
            customdata=[str(x.date()) for x in daily.index],
            hovertemplate="%{x|%A, %b %d}<br><b>%{y:,} trips</b><extra></extra>"))
        if sel:
            f1.add_vline(x=pd.Timestamp(sel), line=dict(color=CORAL, width=1.5, dash="dot"))
        fin(f1, hovermode="x")
        f1.update_xaxes(tickformat="%b %d", dtick=7 * 86400000, tick0=str(D_MIN), **SPIKE)
        f1.update_yaxes(rangemode="tozero")

    d = v.get("region")
    if d.empty:
        f2 = empty()
    else:
        r = d["region"].value_counts().reindex(REGIONS, fill_value=0)[::-1]
        f2 = go.Figure(track(list(r.index), max(1, r.max()) * 1.12, horizontal=True))
        f2.add_trace(go.Bar(
            x=r.values, y=list(r.index), orientation="h",
            marker=dict(color=paint(list(r.index), v.sel("region"), BLUE, REGION_COLORS), cornerradius=8),
            customdata=list(r.index), text=[f"{x:,}  ({x / max(1, r.sum()):.0%})" for x in r.values],
            textposition="outside", cliponaxis=False, textfont=dict(color=t["text"]),
            hovertemplate="%{y}<br><b>%{x:,} trips</b><extra></extra>"))
        fin(f2, bargap=0.38, barmode="overlay", hovermode="y")
        f2.update_xaxes(visible=False, range=[0, max(1, r.max()) * 1.6])
        f2.update_yaxes(tickfont=dict(color=t["text"], size=13), gridcolor="rgba(0,0,0,0)")

    return f1, f2, donut(v, "user_type", USER_COLORS)


# ── Slide 2: time ─────────────────────────────────────────────────────────
SPIKE = dict(showspikes=True, spikemode="across", spikesnap="data", spikethickness=1,
             spikedash="dot", spikecolor="rgba(120,130,170,0.6)")
HOUR_TICKS = dict(tickvals=list(range(0, 24, 3)), ticktext=[hour_label(h) for h in range(0, 24, 3)])


@callback(Output({"type": "xf", "key": "heat"}, "figure"),
          Output({"type": "xf", "key": "weekday"}, "figure"),
          Output({"type": "xf", "key": "hourly"}, "figure"),
          Output({"type": "xf", "key": "durhour"}, "figure"), Output("rk-1", "data"),
          *FILTERS, XF, SLIDE, THEME, State("rk-1", "data"))
@charts(1, 4)
def time_charts(v):
    t = T()
    sel_day, sel_hour, sel_dh = v.sel("day"), v.sel("hour"), v.sel("dayhour")

    d = v.get("day", "hour", "dayhour")
    if d.empty:
        f1 = empty()
    else:
        piv = (d.groupby(["day_of_week", "hour"], observed=False).size().unstack(fill_value=0)
               .reindex(index=DAY_ORDER, columns=range(24), fill_value=0))
        f1 = go.Figure(go.Heatmap(
            z=piv.values, x=list(range(24)), y=DAY_ORDER, colorscale=t["heat"], xgap=3, ygap=3,
            showscale=False, customdata=[[hour_label(h) for h in range(24)]] * 7,
            hovertemplate="%{y}, %{customdata}<br><b>%{z:,} trips</b><extra></extra>"))
        fin(f1, anim=False)
        f1.update_yaxes(autorange="reversed", tickvals=DAY_ORDER, ticktext=[DAY_SHORT[x] for x in DAY_ORDER],
                        gridcolor="rgba(0,0,0,0)")
        f1.update_xaxes(**HOUR_TICKS)
        box = dict(type="rect", line=dict(color=t["sel"], width=2.5), fillcolor="rgba(0,0,0,0)")
        if sel_dh:
            i = DAY_ORDER.index(sel_dh[0])
            f1.add_shape(**box, x0=sel_dh[1] - .5, x1=sel_dh[1] + .5, y0=i - .5, y1=i + .5)
        if sel_day:
            i = DAY_ORDER.index(sel_day)
            f1.add_shape(**box, x0=-.5, x1=23.5, y0=i - .5, y1=i + .5)
        if sel_hour is not None:
            f1.add_shape(**box, x0=sel_hour - .5, x1=sel_hour + .5, y0=-.5, y1=6.5)

    d = v.get("day", "dayhour")
    if d.empty:
        f2 = empty()
    else:
        wk = d["day_of_week"].value_counts().reindex(DAY_ORDER, fill_value=0)
        base = {k: (CORAL if k in ("Saturday", "Sunday") else BLUE) for k in DAY_ORDER}
        labels = [DAY_SHORT[k] for k in DAY_ORDER]
        f2 = go.Figure(track(labels, max(1, wk.max()) * 1.1))
        f2.data[0].customdata = DAY_ORDER
        f2.add_trace(go.Bar(
            x=labels, y=wk.values, customdata=DAY_ORDER,
            marker=dict(color=paint(DAY_ORDER, sel_day, BLUE, base), cornerradius=8),
            hovertemplate="%{customdata}<br><b>%{y:,} trips</b><extra></extra>"))
        fin(f2, barmode="overlay", hovermode="x")
        f2.update_yaxes(range=[0, max(1, wk.max()) * 1.1])

    d = v.get("hour", "dayhour")
    if d.empty:
        f3 = empty()
    else:
        f3 = go.Figure()
        hh = d.groupby(["user_type", "hour"], observed=True).size().unstack(fill_value=0)
        for ut in [u for u in ["Subscriber", "Customer"] if u in hh.index]:
            y = hh.loc[ut].reindex(range(24), fill_value=0)
            f3.add_trace(go.Scatter(
                x=list(range(24)), y=y.values, name=ut, mode="lines+markers",
                line=dict(color=USER_COLORS[ut], width=3, shape="spline", smoothing=0.5),
                marker=dict(size=6, line=dict(color=t["surface"], width=1.5)), customdata=list(range(24)),
                fill="tozeroy",
                fillgradient=dict(type="vertical", colorscale=[[0, rgba(USER_COLORS[ut], 0)],
                                                                [1, rgba(USER_COLORS[ut], t["fill"] * 2)]]),
                hovertemplate=ut + ": <b>%{y:,}</b><extra></extra>"))
        if sel_hour is not None:
            f3.add_vrect(x0=sel_hour - .5, x1=sel_hour + .5, fillcolor=rgba(CORAL, 0.14), line_width=0)
        fin(f3, showlegend=True, hovermode="x unified",
            legend=dict(orientation="h", y=1.02, yanchor="bottom", x=1, xanchor="right", font=dict(color=t["text"])))
        f3.update_xaxes(**HOUR_TICKS, **SPIKE)

    d = v.get("hour", "dayhour")
    if d.empty:
        f4 = empty()
    else:
        a = d.groupby("hour")["duration_min"].mean().reindex(range(24))
        f4 = go.Figure(track(list(range(24)), np.nanmax(a.values) * 1.1))
        f4.add_trace(go.Bar(
            x=list(range(24)), y=a.values, customdata=list(range(24)),
            marker=dict(color=paint(list(range(24)), sel_hour, TEAL), cornerradius=4),
            hovertemplate="%{x}:00<br><b>%{y:.1f} min</b> average<extra></extra>"))
        fin(f4, bargap=0.2, barmode="overlay", hovermode="x")
        f4.update_yaxes(range=[0, np.nanmax(a.values) * 1.1])
        f4.update_xaxes(tickvals=list(range(0, 24, 6)), ticktext=[hour_label(h) for h in range(0, 24, 6)])
        f4.update_yaxes(ticksuffix=" m")
    return f1, f2, f3, f4


# ── Slide 3: riders ───────────────────────────────────────────────────────
def vbar(v, dim, order, color, colors=None, value=None, fmt="%{y:,} trips"):
    d = v.get(dim)
    if d.empty:
        return empty()
    if value:
        s = d.groupby(dim, observed=True)[value].mean().reindex(order)
    else:
        s = d[dim].value_counts().reindex(order, fill_value=0)
    s = s.dropna()
    cats = list(s.index)
    top = max(1e-9, float(s.max())) * 1.1
    fig = go.Figure(track(cats, top))
    fig.add_trace(go.Bar(
        x=cats, y=s.values, customdata=cats,
        marker=dict(color=paint(cats, v.sel(dim), color, colors), cornerradius=8),
        hovertemplate="%{x}<br><b>" + fmt + "</b><extra></extra>"))
    fin(fig, barmode="overlay", hovermode="x")
    fig.update_yaxes(range=[0, top])
    return fig


@callback(Output({"type": "xf", "key": "utype"}, "figure"),
          Output({"type": "xf", "key": "gender"}, "figure"),
          Output({"type": "xf", "key": "age"}, "figure"),
          Output("durhist", "figure"),
          Output({"type": "xf", "key": "agedur"}, "figure"), Output("rk-2", "data"),
          *FILTERS, XF, SLIDE, THEME, State("rk-2", "data"))
@charts(2, 5)
def rider_charts(v):
    t = T()
    f1 = donut(v, "user_type", USER_COLORS)
    f2 = vbar(v, "gender", ALL_GENDER, BLUE, GENDER_COLORS)
    f3 = vbar(v, "age_group", AGE_ORDER, VIOLET)
    f5 = vbar(v, "age_group", AGE_ORDER, TEAL, value="duration_min", fmt="%{y:.1f} min average")
    f5.update_yaxes(ticksuffix=" m")
    d = v.get()
    if d.empty:
        f4 = empty()
    else:
        bins = np.arange(0, 62, 2)
        f4 = go.Figure()
        for ut in [u for u in ["Subscriber", "Customer"] if u in set(d["user_type"])]:
            cnt, _ = np.histogram(d.loc[d["user_type"] == ut, "duration_min"], bins=bins)
            share = cnt / max(1, (d["user_type"] == ut).sum())
            f4.add_trace(go.Bar(
                x=bins[:-1] + 1, y=share, name=ut, marker=dict(color=USER_COLORS[ut], cornerradius=3),
                customdata=np.stack([bins[:-1], bins[1:], cnt], axis=1),
                hovertemplate=ut + "<br>%{customdata[0]} to %{customdata[1]} min<br>"
                                   "<b>%{y:.1%}</b> of their trips (%{customdata[2]:,})<extra></extra>"))
        fin(f4, barmode="group", bargap=0.14, bargroupgap=0.06, showlegend=True, hovermode="x unified",
            legend=dict(orientation="h", y=1.02, yanchor="bottom", x=1, xanchor="right", font=dict(color=t["text"])))
        f4.update_xaxes(title=dict(text="Ride length (minutes)", font=dict(size=11)), dtick=10)
        f4.update_yaxes(tickformat=".0%")
    return f1, f2, f3, f4, f5


# ── Slide 4: stations ─────────────────────────────────────────────────────
MAP_SCALE = [[0, VIOLET], [0.5, BLUE], [1, TEAL]]
CENTERS = {"San Francisco": (37.779, -122.405, 12.2), "East Bay": (37.828, -122.268, 11.8),
           "San Jose": (37.334, -121.892, 12.6)}


def rank_chart(v, d, mode):
    t = T()
    if mode == "route":
        r = d.groupby(["start_station", "end_station"], observed=True).size().sort_values(ascending=False).head(10)[::-1]
        keys = [[str(a), str(b)] for a, b in r.index]
        labels = [f"{short(a, 17)} → {short(b, 17)}" for a, b in keys]
        sel = v.sel("route")
        color, hover = SUN, [f"{a}<br>to {b}" for a, b in keys]
        colors = [color if (sel is None or sel == k) else rgba(color, t["dim"]) for k in keys]
    else:
        col = "start_station" if mode == "start" else "end_station"
        r = d[col].value_counts()
        r = r[r > 0].head(10)[::-1]
        keys = [str(x) for x in r.index]
        labels = [short(k, 30) for k in keys]
        color = BLUE if mode == "start" else TEAL
        colors, hover = paint(keys, v.sel("station"), color), keys
    if r.empty:
        return empty()
    idx = list(range(len(labels)))
    fig = go.Figure(go.Bar(x=[r.max() * 1.08] * len(idx), y=idx, orientation="h", customdata=keys, meta="track",
                           hoverinfo="none", showlegend=False, marker=dict(color=t["track"], cornerradius=6)))
    fig.add_trace(go.Bar(
        x=r.values, y=idx, orientation="h", customdata=keys, hovertext=hover,
        marker=dict(color=colors, cornerradius=6),
        text=[f"{x:,}" for x in r.values], textposition="outside", cliponaxis=False,
        textfont=dict(color=t["muted"]),
        hovertemplate="%{hovertext}<br><b>%{x:,} trips</b><extra></extra>"))
    fin(fig, bargap=0.42, margin=dict(t=2, l=2, r=6, b=2), barmode="overlay", hovermode="y")
    fig.update_xaxes(visible=False, range=[0, r.max() * 1.3])
    fig.update_yaxes(tickmode="array", tickvals=idx, ticktext=labels, gridcolor="rgba(0,0,0,0)",
                     tickfont=dict(size=11.5, color=t["text"]))
    return fig


@callback(Output({"type": "xf", "key": "map"}, "figure"),
          Output({"type": "xf", "key": "rank"}, "figure"),
          Output("spotlight", "children"), Output("rk-3", "data"),
          *FILTERS, XF, Input("rank-mode", "value"), SLIDE, THEME, State("rk-3", "data"))
@charts(3, 2, extra=1, tail=(html.P("Something went wrong building this panel."),))
def station_charts(v, mode):
    t = T()
    sel = v.sel("station")
    d = v.get("station", "route")
    if d.empty:
        return empty(), empty(), spotlight(v, d, sel)

    st = (d.groupby("start_station", observed=True)
          .agg(trips=("trip_id", "size"), lat=("start_lat", "first"), lng=("start_lng", "first"))
          .reset_index())
    st["start_station"] = st["start_station"].astype(str)
    size = 6 + 24 * np.sqrt(st["trips"] / st["trips"].max())
    Scatter = getattr(go, "Scattermap", None) or go.Scattermapbox
    f1 = go.Figure(Scatter(
        lat=st["lat"], lon=st["lng"], mode="markers",
        marker=dict(size=size, color=st["trips"], colorscale=MAP_SCALE, opacity=0.8 if sel is None else 0.35),
        customdata=st["start_station"], text=st["trips"],
        hovertemplate="%{customdata}<br><b>%{text:,} departures</b><extra></extra>"))
    if sel is not None and (st["start_station"] == sel).any():
        row = st[st["start_station"] == sel].iloc[0]
        f1.add_trace(Scatter(lat=[row.lat], lon=[row.lng], mode="markers",
                             marker=dict(size=30, color=CORAL, opacity=1), customdata=[sel],
                             hovertemplate="%{customdata}<extra></extra>"))
        center, zoom = dict(lat=row.lat, lon=row.lng), 13.2
    else:
        rsel = v.sel("region")
        focus = [rsel] if rsel else (v.filters[6] or REGIONS)
        la, lo, zoom = CENTERS[focus[0]] if len(focus) == 1 and focus[0] in CENTERS else (37.62, -122.20, 9.3)
        center = dict(lat=la, lon=lo)
    mapkw = dict(style=t["map"], center=center, zoom=zoom)
    fin(f1, anim=False, margin=dict(t=0, l=0, r=0, b=0))
    f1.update_layout(**({"map": mapkw} if Scatter is getattr(go, "Scattermap", None) else {"mapbox": mapkw}))
    f1.update_layout(uirevision=f"{sel}-{v.sel('region')}-{v.filters[6]}")

    d_rank = v.get("route") if mode == "route" else d
    return f1, rank_chart(v, d_rank, mode), spotlight(v, d, sel)


def spotlight(v, d, sel):
    t = T()
    head_title = html.H3("Station spotlight", className="panel-title")
    if sel is None or d.empty:
        top = (pd.concat([d["start_station"].astype(str), d["end_station"].astype(str)]).value_counts().head(8)
               if not d.empty else pd.Series(dtype=int))
        mx = top.max() if len(top) else 1
        return [
            html.Div(head_title, className="panel-head"),
            html.P("Pick a station on the map or in the ranking to see departures, arrivals, "
                   "where riders go next and when it is busiest.", className="spot-intro"),
            html.Div("Busiest stations", className="spot-sub"),
            html.Div([html.Button([html.Span(short(n, 32), className="pick-name"),
                                   html.Span(f"{c:,}", className="pick-n"),
                                   html.Span(className="pick-bar", style={"width": f"{c / mx * 100:.0f}%"})],
                                  id={"type": "pick", "name": n}, className="pick", n_clicks=0)
                      for n, c in top.items()], className="pick-list"),
        ]
    dep = d[d["start_station"] == sel]
    arr = d[d["end_station"] == sel]
    net = len(arr) - len(dep)
    region = dep["region"].mode().iloc[0] if len(dep) else (arr["region"].mode().iloc[0] if len(arr) else "")
    dest = dep["end_station"].astype(str).value_counts()
    dest = dest[dest.index != sel]
    peak = int(dep["hour"].value_counts().idxmax()) if len(dep) else None
    hd = dep["hour"].value_counts().reindex(range(24), fill_value=0)
    ha = arr["hour"].value_counts().reindex(range(24), fill_value=0)
    mini = go.Figure()
    mini.add_trace(go.Bar(x=list(range(24)), y=hd.values, name="Departures", marker=dict(color=BLUE, cornerradius=2),
                          hovertemplate="%{x}:00 departures: %{y:,}<extra></extra>"))
    mini.add_trace(go.Bar(x=list(range(24)), y=-ha.values, name="Arrivals", marker=dict(color=TEAL, cornerradius=2),
                          customdata=ha.values, hovertemplate="%{x}:00 arrivals: %{customdata:,}<extra></extra>"))
    fin(mini, barmode="relative", bargap=0.18, showlegend=True,
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(size=11, color=t["text"])))
    mini.update_yaxes(showticklabels=False, zeroline=True, zerolinecolor=t["line"], gridcolor="rgba(0,0,0,0)")
    mini.update_xaxes(tickvals=[0, 6, 12, 18], ticktext=["12 AM", "6 AM", "12 PM", "6 PM"])

    def stat(label, value, color):
        return html.Div([html.Div(value, className="st-v"), html.Div(label, className="st-l")],
                        className="st", style={"--accent": color})

    return [
        html.Div([head_title, html.Button("Close", id={"type": "chip-x", "dim": "station", "src": "spot"},
                                          className="spot-close", n_clicks=0)], className="panel-head"),
        html.Div(sel, className="spot-name"),
        html.Div(region, className="spot-region"),
        html.Div([stat("Departures", f"{len(dep):,}", BLUE), stat("Arrivals", f"{len(arr):,}", TEAL),
                  stat("Net bikes", f"{net:+,}", CORAL if net < 0 else TEAL),
                  stat("Busiest hour", hour_label(peak) if peak is not None else "–", SUN)], className="st-grid"),
        html.P("Gains bikes over the period, so it tends to fill up." if net > 0 else
               "Loses bikes over the period, so it tends to run empty." if net < 0 else
               "Departures and arrivals balance out.", className="spot-flow"),
        html.Div(dcc.Graph(figure=mini, config={"displayModeBar": False, "responsive": True},
                           style={"height": "100%", "width": "100%"}), className="spot-chart"),
        html.Div([html.Span("Most common next stop: ", className="muted"),
                  html.Strong(short(dest.index[0], 40) if len(dest) else "–")], className="spot-dest"),
    ]


# ── Download ──────────────────────────────────────────────────────────────
@callback(Output("download-data", "data"), Input("download-btn", "n_clicks"),
          State("date-range", "start_date"), State("date-range", "end_date"), State("f-user", "value"),
          State("f-gender", "value"), State("f-age", "value"), State("f-dur", "value"),
          State("f-region", "value"), State("xf", "data"), prevent_initial_call=True)
def download_filtered(_, *args):
    d = View(args[:-1], args[-1]).get()
    return dcc.send_data_frame(d.to_csv, "gobike_filtered_trips.csv", index=False)


if __name__ == "__main__":
    app.run(debug=False, port=8050)
