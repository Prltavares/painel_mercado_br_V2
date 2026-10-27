from __future__ import annotations

import base64
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf
from bs4 import BeautifulSoup
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh


# ============================================================
# CONFIGURAÇÃO E IDENTIDADE VISUAL
# ============================================================
st.set_page_config(
    page_title="Mercado BR | Painel financeiro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent
HERO_PATH = ROOT / "assets" / "market-hero.jpg"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0 Safari/537.36"
    )
}

PAGES = [
    "Visão geral",
    "Mercados",
    "Ações da B3",
    "Gráficos",
    "Notícias",
]

ASSETS: dict[str, str] = {
    "Ibovespa": "^BVSP",
    "Dólar / Real": "BRL=X",
    "Euro / Real": "EURBRL=X",
    "S&P 500": "^GSPC",
    "Nasdaq Composite": "^IXIC",
    "Dow Jones": "^DJI",
    "Ouro": "GC=F",
    "Petróleo WTI": "CL=F",
    "Bitcoin": "BTC-USD",
}

BRAZILIAN_STOCKS: dict[str, str] = {
    "Petrobras PN (PETR4)": "PETR4.SA",
    "Vale ON (VALE3)": "VALE3.SA",
    "Itaú Unibanco PN (ITUB4)": "ITUB4.SA",
    "Banco do Brasil ON (BBAS3)": "BBAS3.SA",
    "B3 ON (B3SA3)": "B3SA3.SA",
    "WEG ON (WEGE3)": "WEGE3.SA",
    "Ambev ON (ABEV3)": "ABEV3.SA",
    "Magazine Luiza ON (MGLU3)": "MGLU3.SA",
    "Localiza ON (RENT3)": "RENT3.SA",
    "Axia Energia ON (AXIA3)": "AXIA3.SA",
}

# As consultas são feitas via RSS do Google News com filtro de domínio.
# Isso oferece uma forma uniforme de ler os feeds, mas os links continuam
# levando para a publicação original e a disponibilidade varia por veículo.
NEWS_FEEDS = [
    {"name": "Valor Econômico", "query": "site:valor.globo.com mercados economia", "category": "Brasil", "lang": "pt-BR", "country": "BR", "ceid": "BR:pt-419"},
    {"name": "InfoMoney", "query": "site:infomoney.com.br mercados bolsa economia", "category": "Brasil", "lang": "pt-BR", "country": "BR", "ceid": "BR:pt-419"},
    {"name": "Agência Brasil", "query": "site:agenciabrasil.ebc.com.br economia mercado", "category": "Brasil", "lang": "pt-BR", "country": "BR", "ceid": "BR:pt-419"},
    {"name": "Money Times", "query": "site:moneytimes.com.br mercado bolsa economia", "category": "Brasil", "lang": "pt-BR", "country": "BR", "ceid": "BR:pt-419"},
    {"name": "Reuters", "query": "site:reuters.com/markets OR site:reuters.com/business economy markets", "category": "Internacional", "lang": "en-US", "country": "US", "ceid": "US:en"},
    {"name": "Bloomberg", "query": "site:bloomberg.com/news markets economy", "category": "Internacional", "lang": "en-US", "country": "US", "ceid": "US:en"},
    {"name": "CNBC", "query": "site:cnbc.com markets economy stocks", "category": "Internacional", "lang": "en-US", "country": "US", "ceid": "US:en"},
]


# ============================================================
# HELPERS VISUAIS / ACESSIBILIDADE
# ============================================================
def read_hero_base64() -> str:
    try:
        return base64.b64encode(HERO_PATH.read_bytes()).decode("ascii")
    except OSError:
        return ""


def apply_theme(theme: str, high_contrast: bool, large_text: bool) -> None:
    if theme == "Escuro":
        palette = {
            "bg": "#101722", "surface": "#182231", "surface_alt": "#202d3e",
            "text": "#eaf0f8", "muted": "#b2bfd0", "border": "#334257",
            "accent": "#67d7c2", "accent_text": "#071e1a", "accent_soft": "#213f42",
            "input": "#1a2636", "shadow": "rgba(0,0,0,.18)",
        }
    elif theme == "Noturno OLED":
        palette = {
            "bg": "#050607", "surface": "#0d1013", "surface_alt": "#161b20",
            "text": "#f5f7fa", "muted": "#bec7d2", "border": "#303740",
            "accent": "#63e6c8", "accent_text": "#001b15", "accent_soft": "#10332e",
            "input": "#11161b", "shadow": "rgba(0,0,0,.32)",
        }
    else:
        palette = {
            "bg": "#f4f6f9", "surface": "#ffffff", "surface_alt": "#edf1f5",
            "text": "#1c2735", "muted": "#657285", "border": "#dce3eb",
            "accent": "#087f70", "accent_text": "#ffffff", "accent_soft": "#e2f4ef",
            "input": "#ffffff", "shadow": "rgba(26,39,53,.045)",
        }

    if high_contrast:
        if theme == "Claro":
            palette.update({"bg": "#ffffff", "surface": "#ffffff", "surface_alt": "#f0f0f0", "text": "#000000", "muted": "#292929", "border": "#595959", "accent": "#005fcc", "accent_text": "#ffffff", "accent_soft": "#e6f0ff", "input": "#ffffff"})
        else:
            palette.update({"bg": "#000000", "surface": "#000000", "surface_alt": "#161616", "text": "#ffffff", "muted": "#f0f0f0", "border": "#bfbfbf", "accent": "#75d8ff", "accent_text": "#000000", "accent_soft": "#102c3c", "input": "#050505"})

    root_font = "18px" if large_text else "16px"
    heading_scale = "1.08" if large_text else "1"
    hero_b64 = read_hero_base64()
    hero_background = (
        f"linear-gradient(90deg, rgba(6,18,34,.96) 0%, rgba(6,18,34,.79) 42%, rgba(6,18,34,.10) 100%), url('data:image/jpeg;base64,{hero_b64}')"
        if hero_b64
        else "linear-gradient(120deg, #071a2e, #17374b)"
    )

    css = f"""
    <style>
    :root {{
      --app-bg: {palette['bg']}; --surface: {palette['surface']};
      --surface-alt: {palette['surface_alt']}; --text: {palette['text']};
      --muted: {palette['muted']}; --border: {palette['border']};
      --accent: {palette['accent']}; --accent-text: {palette['accent_text']};
      --accent-soft: {palette['accent_soft']}; --input-bg: {palette['input']};
      --shadow: {palette['shadow']};
    }}
    html, body, [class*="css"] {{ font-size: {root_font}; }}
    .stApp {{ background: var(--app-bg); color: var(--text); }}
    [data-testid="stHeader"] {{ background: transparent; }}
    [data-testid="stToolbar"] {{ right: 1rem; }}
    .block-container {{ padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1600px; }}
    h1, h2, h3, h4, h5, h6 {{ color: var(--text) !important; letter-spacing: -.025em; }}
    h1 {{ font-size: calc(2.15rem * {heading_scale}) !important; font-weight: 760 !important; }}
    h2 {{ font-size: calc(1.45rem * {heading_scale}) !important; font-weight: 710 !important; }}
    h3 {{ font-size: calc(1.1rem * {heading_scale}) !important; font-weight: 690 !important; }}
    p, li, label, span {{ color: inherit; }}
    .stMarkdown, .stCaption, [data-testid="stCaptionContainer"] {{ color: var(--muted); }}
    section[data-testid="stSidebar"] {{ background: var(--surface); border-right: 1px solid var(--border); }}
    section[data-testid="stSidebar"] > div {{ padding-top: 1.4rem; }}
    section[data-testid="stSidebar"] hr {{ border-color: var(--border); margin: 1rem 0; }}
    [data-testid="stMetric"] {{ background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 17px 18px; box-shadow: 0 5px 18px var(--shadow); min-height: 125px; }}
    [data-testid="stMetricLabel"] p {{ color: var(--muted) !important; font-size: .88rem !important; font-weight: 600; }}
    [data-testid="stMetricValue"] {{ color: var(--text) !important; font-size: clamp(1.2rem, 2vw, 1.75rem) !important; font-weight: 760 !important; }}
    [data-testid="stMetricDelta"] {{ font-size: .85rem !important; }}
    [data-testid="stVerticalBlockBorderWrapper"] {{ border-color: var(--border) !important; background: var(--surface); border-radius: 16px; }}
    [data-testid="stDataFrame"], [data-testid="stTable"] {{ border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }}
    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div {{ background: var(--input-bg); border-color: var(--border); border-radius: 10px; }}
    input, textarea {{ color: var(--text) !important; }}
    [data-testid="stCheckbox"] label, [data-testid="stRadio"] label {{ color: var(--text); }}
    [data-testid="stButton"] button {{ border-radius: 10px; border: 1px solid var(--border); font-weight: 650; transition: border-color .12s ease, transform .12s ease; }}
    [data-testid="stButton"] button:hover {{ border-color: var(--accent); color: var(--accent); transform: translateY(-1px); }}
    [data-testid="stLinkButton"] a {{ border-radius: 10px; }}
    a {{ color: var(--accent) !important; text-underline-offset: 3px; }}
    :focus-visible {{ outline: 3px solid var(--accent) !important; outline-offset: 2px !important; }}
    [data-testid="stAlert"] {{ border-radius: 12px; }}
    [data-testid="stTabs"] button {{ font-weight: 650; }}
    [data-testid="stTabs"] button[aria-selected="true"] {{ color: var(--accent) !important; }}

    .brand-lockup {{ display:flex; align-items:center; gap:11px; margin-bottom:8px; }}
    .brand-mark {{ display:flex; align-items:center; justify-content:center; width:38px; height:38px; border-radius:12px; background:var(--accent); color:var(--accent-text); font-size:15px; font-weight:850; letter-spacing:-1px; }}
    .brand-name {{ color:var(--text); font-size:1.13rem; font-weight:780; letter-spacing:-.03em; line-height:1.15; }}
    .brand-tagline {{ color:var(--muted); font-size:.78rem; margin-top:4px; }}
    .eyebrow {{ color:var(--accent); text-transform:uppercase; letter-spacing:.15em; font-size:.72rem; font-weight:800; margin-bottom:7px; }}
    .page-intro {{ color:var(--muted); font-size:1rem; margin-top:-.35rem; margin-bottom:1.4rem; max-width:850px; line-height:1.6; }}
    .hero {{ background-image: {hero_background}; background-size:cover; background-position:center; border-radius:22px; padding:36px 36px 32px; min-height:220px; display:flex; flex-direction:column; justify-content:center; margin:4px 0 24px; border:1px solid rgba(255,255,255,.08); box-shadow:0 14px 36px rgba(5,18,35,.15); }}
    .hero-kicker {{ color:#85e2d1; font-size:.72rem; letter-spacing:.16em; text-transform:uppercase; font-weight:800; margin-bottom:12px; }}
    .hero-title {{ color:#fff; font-size:clamp(1.8rem,3vw,2.7rem); line-height:1.07; font-weight:800; max-width:560px; letter-spacing:-.05em; }}
    .hero-copy {{ color:#d2dce9; font-size:.98rem; max-width:510px; margin-top:12px; line-height:1.6; }}
    .section-heading {{ display:flex; align-items:center; justify-content:space-between; gap:16px; margin:26px 0 12px; }}
    .section-label {{ color:var(--muted); text-transform:uppercase; font-size:.72rem; font-weight:800; letter-spacing:.13em; }}
    .news-image {{ width:100%; object-fit:cover; border-radius:11px; max-height:220px; }}
    .news-title {{ font-size:1.05rem; line-height:1.35; font-weight:740; color:var(--text); }}
    .news-meta {{ font-size:.76rem; color:var(--muted); }}
    .news-placeholder {{ min-height:104px; display:flex; justify-content:center; align-items:center; flex-direction:column; gap:6px; background:var(--surface-alt); border:1px dashed var(--border); border-radius:11px; color:var(--muted); font-size:.8rem; text-align:center; padding:10px; }}
    .status-pill {{ display:inline-block; padding:5px 9px; border-radius:999px; background:var(--accent-soft); color:var(--accent); font-size:.75rem; font-weight:750; }}
    .muted-note {{ color:var(--muted); font-size:.84rem; line-height:1.5; }}

    /* Navegação em botões: sem círculos de seleção, com estado ativo evidente. */
    section[data-testid="stSidebar"] [data-testid="stButton"] button {{
      width:100%; justify-content:flex-start; text-align:left; padding:.64rem .85rem;
      min-height:2.75rem; margin-bottom:.1rem; border-radius:10px;
    }}
    section[data-testid="stSidebar"] [data-testid="stButton"] button {{
      background:var(--surface) !important; color:var(--text) !important;
      border-color:var(--border) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stButton"] button p,
    section[data-testid="stSidebar"] [data-testid="stButton"] button span,
    section[data-testid="stSidebar"] [data-testid="stButton"] button div {{
      color:var(--text) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {{
      background:var(--accent-soft) !important; color:var(--accent) !important;
      border-color:var(--border) !important; box-shadow:inset 3px 0 0 var(--accent);
    }}
    section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] p,
    section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] span,
    section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] div {{
      color:var(--accent) !important; font-weight:750;
    }}
    section[data-testid="stSidebar"] [data-testid="stButton"] button:focus-visible {{
      outline:3px solid var(--accent) !important; outline-offset:2px !important;
    }}

    @media (max-width: 800px) {{
      .block-container {{ padding-left:1rem; padding-right:1rem; }}
      .hero {{ padding:24px 20px; min-height:190px; background-position:62% center; }}
      .hero-title {{ font-size:1.85rem; }}
      [data-testid="stMetric"] {{ padding:13px 12px; min-height:110px; }}
      div[data-testid="stHorizontalBlock"] {{ flex-wrap:wrap !important; gap:.75rem !important; }}
      div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{ flex:1 1 210px !important; min-width:min(100%, 210px) !important; }}
    }}
    @media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ transition:none !important; animation:none !important; scroll-behavior:auto !important; }} }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def chart_text_color() -> str:
    if st.session_state.get("high_contrast", False):
        return "#000000" if st.session_state.get("appearance", "Claro") == "Claro" else "#ffffff"
    return "#657285" if st.session_state.get("appearance", "Claro") == "Claro" else "#b2bfd0"


def page_header(eyebrow: str, title: str, description: str) -> None:
    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="page-intro">{description}</div>', unsafe_allow_html=True)


def section_title(title: str, eyebrow: str | None = None) -> None:
    if eyebrow:
        st.markdown(f'<div class="section-label">{eyebrow}</div>', unsafe_allow_html=True)
    st.markdown(f"## {title}")


# ============================================================
# DADOS DE MERCADO
# ============================================================
def format_brl(value: float, decimals: int = 2) -> str:
    text = f"{value:,.{decimals}f}"
    return "R$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")


def format_number_br(value: float, decimals: int = 0) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def format_price(value: float, ticker: str) -> str:
    if ticker in {"BRL=X", "EURBRL=X"}:
        return format_brl(value, 4)
    if ticker.endswith(".SA"):
        return format_brl(value, 2)
    if ticker in {"^BVSP", "^GSPC", "^IXIC", "^DJI"}:
        return format_number_br(value, 0)
    if ticker == "BTC-USD":
        return "US$ " + format_number_br(value, 2)
    if ticker in {"GC=F", "CL=F"}:
        return "US$ " + format_number_br(value, 2)
    return format_number_br(value, 2)


@st.cache_data(ttl=90, show_spinner=False)
def get_quote(ticker: str) -> dict[str, Any] | None:
    try:
        security = yf.Ticker(ticker)
        intraday = security.history(period="1d", interval="5m", auto_adjust=True)
        daily = security.history(period="5d", interval="1d", auto_adjust=True)

        intraday = intraday.dropna(subset=["Close"]) if not intraday.empty else intraday
        daily = daily.dropna(subset=["Close"]) if not daily.empty else daily

        if not intraday.empty:
            price = float(intraday["Close"].iloc[-1])
            timestamp = intraday.index[-1]
        elif not daily.empty:
            price = float(daily["Close"].iloc[-1])
            timestamp = daily.index[-1]
        else:
            return None

        # Compara com o fechamento diário anterior, em vez de comparar barras de 5 min.
        if len(daily) >= 2:
            previous_close = float(daily["Close"].iloc[-2])
        elif len(daily) == 1:
            previous_close = float(daily["Close"].iloc[0])
        elif len(intraday) >= 2:
            previous_close = float(intraday["Close"].iloc[-2])
        else:
            previous_close = price

        change_pct = ((price / previous_close) - 1) * 100 if previous_close else 0.0
        return {
            "ticker": ticker,
            "price": price,
            "previous_close": previous_close,
            "change_pct": change_pct,
            "timestamp": str(timestamp),
        }
    except Exception:
        return None


@st.cache_data(ttl=120, show_spinner=False)
def get_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    try:
        data = yf.Ticker(ticker).history(
            period=period,
            interval=interval,
            auto_adjust=True,
            prepost=False,
        )
        if data.empty or "Close" not in data.columns:
            return pd.DataFrame()
        return data.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()


def render_metric(label: str, ticker: str) -> None:
    quote_data = get_quote(ticker)
    if not quote_data:
        st.metric(label, "Sem cotação", help=f"Não foi possível consultar {ticker} agora.")
        return
    st.metric(
        label,
        format_price(quote_data["price"], ticker),
        f'{quote_data["change_pct"]:+.2f}%',
        help=f'Código: {ticker} · Consulta em {quote_data["timestamp"]}',
    )


def quote_table(asset_dict: dict[str, str]) -> pd.DataFrame:
    rows = []
    for name, ticker in asset_dict.items():
        data = get_quote(ticker)
        rows.append({
            "Ativo": name,
            "Código": ticker,
            "Último valor": format_price(data["price"], ticker) if data else "Indisponível",
            "Variação diária (%)": round(data["change_pct"], 2) if data else None,
            "Atualizado em": data["timestamp"] if data else "—",
        })
    return pd.DataFrame(rows)


# ============================================================
# NOTÍCIAS E IMAGENS
# ============================================================
def clean_html(value: str | None) -> str:
    if not value:
        return ""
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


def valid_image_url(value: str | None, base_url: str | None = None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value.startswith("//"):
        value = "https:" + value
    elif base_url and not value.startswith(("https://", "http://", "data:")):
        value = urljoin(base_url, value)
    if value.startswith(("https://", "http://")) and not value.lower().endswith(".svg"):
        return value
    return None


def item_image(item: ET.Element, description: str) -> str | None:
    # Procura namespaces Media RSS, thumbnails e enclosures no próprio feed.
    for element in item.iter():
        tag = element.tag.lower()
        if tag.endswith("thumbnail") or tag.endswith("content"):
            candidate = element.attrib.get("url") or element.attrib.get("href")
            image = valid_image_url(candidate)
            if image:
                return image
        if tag.endswith("enclosure"):
            candidate = element.attrib.get("url")
            media_type = element.attrib.get("type", "")
            image = valid_image_url(candidate)
            if image and media_type.startswith("image/"):
                return image

    # Alguns feeds colocam a imagem dentro do HTML da descrição.
    try:
        soup = BeautifulSoup(description or "", "html.parser")
        image_tag = soup.find("img")
        if image_tag:
            image = valid_image_url(image_tag.get("src"))
            if image:
                return image
    except Exception:
        pass
    return None


def get_article_image(url: str) -> str | None:
    """Segue o link e tenta extrair og:image / twitter:image da matéria original."""
    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=4,
            allow_redirects=True,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for attrs in (
            {"property": "og:image"},
            {"name": "twitter:image"},
            {"property": "twitter:image"},
        ):
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                candidate = valid_image_url(tag.get("content"), response.url)
                if candidate:
                    parsed = urlparse(candidate)
                    # Não usar imagem genérica do Google News como se fosse da matéria.
                    if parsed.netloc and "news.google.com" not in parsed.netloc:
                        return candidate
    except Exception:
        return None
    return None


def fetch_feed(feed: dict[str, str]) -> list[dict[str, Any]]:
    try:
        response = requests.get(
            "https://news.google.com/rss/search",
            params={
                "q": feed["query"],
                "hl": feed["lang"],
                "gl": feed["country"],
                "ceid": feed["ceid"],
            },
            headers=REQUEST_HEADERS,
            timeout=7,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        results: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = clean_html(item.findtext("title", ""))
            link = (item.findtext("link", "") or "").strip()
            pub_date = (item.findtext("pubDate", "") or "").strip()
            description = item.findtext("description", "") or ""
            if not title or not link:
                continue
            source_node = item.find("source")
            source = clean_html(source_node.text) if source_node is not None else feed["name"]
            results.append({
                "title": title,
                "url": link,
                "source": source or feed["name"],
                "date": pub_date,
                "category": feed["category"],
                "image": item_image(item, description),
                "description": clean_html(description),
            })
        return results
    except Exception as error:
        print(f"RSS indisponível ({feed['name']}): {error}")
        return []


def parse_news_date(value: str) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)


@st.cache_data(ttl=600, show_spinner=False)
def get_news() -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    # Busca os feeds simultaneamente para não deixar uma fonte lenta travar a página.
    with ThreadPoolExecutor(max_workers=7) as executor:
        batches = list(executor.map(fetch_feed, NEWS_FEEDS))
    for batch in batches:
        articles.extend(batch)

    # Remove duplicadas pelo título, mesmo quando vêm de dois feeds diferentes.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for article in articles:
        normalized = re.sub(r"\s+", " ", article["title"].lower()).strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(article)

    unique.sort(key=lambda x: parse_news_date(x["date"]), reverse=True)

    # Busca metadata de imagem só para as primeiras matérias sem imagem no feed.
    # Limitar chamadas torna a página bem mais rápida e reduz risco de bloqueio.
    missing = [article for article in unique[:18] if not article.get("image")]
    with ThreadPoolExecutor(max_workers=5) as executor:
        images = list(executor.map(lambda article: get_article_image(article["url"]), missing[:10]))
    image_map = {article["url"]: image for article, image in zip(missing[:10], images)}
    for article in unique:
        if not article.get("image") and article["url"] in image_map:
            article["image"] = image_map[article["url"]]

    return unique


def possible_market_drivers(title: str) -> list[str]:
    """Mapeamento indicativo de assuntos presentes no título, sem afirmar causa."""
    text = title.lower()
    terms = {
        "Juros e Banco Central": ["juros", "selic", "copom", "fed ", "interest rate", "central bank"],
        "Inflação": ["inflação", "ipca", "cpi", "inflation", "consumer prices"],
        "Câmbio": ["dólar", "câmbio", "dollar", "currency", "forex", "real brasileiro"],
        "Petróleo e energia": ["petróleo", "petrobras", "brent", "oil prices", "crude oil", "energia"],
        "Resultados de empresas": ["lucro", "prejuízo", "balanço", "earnings", "revenue", "profit"],
        "Política e governo": ["congresso", "governo", "presidente", "congress", "election", "trump"],
        "Comércio internacional": ["tarifas", "exportação", "importação", "trade war", "tariff", "china"],
        "Criptoativos": ["bitcoin", "ethereum", "cripto", "crypto"],
    }
    matches = [label for label, keywords in terms.items() if any(keyword in text for keyword in keywords)]
    return matches or ["Leia a matéria para identificar o assunto"]


def format_news_date(value: str) -> str:
    date = parse_news_date(value)
    if date == datetime.min.replace(tzinfo=timezone.utc):
        return "Data não informada"
    return date.astimezone().strftime("%d/%m/%Y · %H:%M")


def render_news_card(article: dict[str, Any]) -> None:
    with st.container(border=True):
        image = article.get("image")
        if image:
            try:
                st.image(image, use_container_width=True)
            except Exception:
                st.markdown('<div class="news-placeholder">Prévia da imagem indisponível</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="news-placeholder"><strong>Imagem não disponibilizada</strong><span>O veículo não forneceu uma miniatura acessível.</span></div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            f'<div class="news-meta">{article["source"]} &nbsp;·&nbsp; {article["category"]} &nbsp;·&nbsp; {format_news_date(article["date"])}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(f'#### [{article["title"]}]({article["url"]})')

        description = article.get("description", "")
        if description and len(description) > 20:
            snippet = description[:185].rstrip()
            if len(description) > 185:
                snippet += "…"
            st.write(snippet)

        drivers = possible_market_drivers(article["title"])
        st.caption("Assuntos detectados no título: " + " · ".join(drivers))
        st.markdown(f'[Abrir no veículo original ↗]({article["url"]})')


# ============================================================
# SIDEBAR / ESTADO DO USUÁRIO
# ============================================================
st.session_state.setdefault("page_navigation", PAGES[0])
st.session_state.setdefault("appearance", "Claro")
st.session_state.setdefault("high_contrast", False)
st.session_state.setdefault("large_text", False)
st.session_state.setdefault("auto_refresh", False)

with st.sidebar:
    st.markdown(
        '''
        <div class="brand-lockup">
          <div class="brand-mark">MB</div>
          <div>
            <div class="brand-name">Mercado BR</div>
            <div class="brand-tagline">Informação para acompanhar o mercado</div>
          </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown('<div class="section-label">Navegação</div>', unsafe_allow_html=True)
    for nav_page in PAGES:
        is_active = st.session_state["page_navigation"] == nav_page
        if st.button(
            nav_page,
            key="nav_" + re.sub(r"[^a-z0-9]+", "_", nav_page.lower()).strip("_"),
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            st.session_state["page_navigation"] = nav_page
            st.rerun()
    selected_page = st.session_state["page_navigation"]
    st.divider()
    st.markdown('<div class="section-label">Aparência e acessibilidade</div>', unsafe_allow_html=True)
    st.selectbox(
        "Tema de cores",
        ["Claro", "Escuro", "Noturno OLED"],
        key="appearance",
        help="Claro para ambientes iluminados; escuro ou OLED para ambientes com pouca luz.",
    )
    st.checkbox(
        "Contraste reforçado",
        key="high_contrast",
        help="Aumenta o contraste entre texto, fundos e bordas.",
    )
    st.checkbox(
        "Texto maior",
        key="large_text",
        help="Aumenta a escala da tipografia e facilita a leitura.",
    )
    st.checkbox(
        "Atualização automática (2 min)",
        key="auto_refresh",
        help="Atualiza a página periodicamente. Os dados respeitam o cache dos provedores.",
    )
    st.divider()
    if st.button("Atualizar agora", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown(
        '<div class="muted-note">Cotações de terceiros podem apresentar atraso, limites ou indisponibilidade.</div>',
        unsafe_allow_html=True,
    )

apply_theme(
    st.session_state["appearance"],
    st.session_state["high_contrast"],
    st.session_state["large_text"],
)

if st.session_state["auto_refresh"]:
    st_autorefresh(interval=120_000, key="market_auto_refresh")


# ============================================================
# PÁGINA: VISÃO GERAL
# ============================================================
if selected_page == "Visão geral":
    hero_b64 = read_hero_base64()
    hero_css = (
        f"background-image:linear-gradient(90deg,rgba(6,18,34,.96) 0%,rgba(6,18,34,.80) 43%,rgba(6,18,34,.12) 100%),url('data:image/jpeg;base64,{hero_b64}');"
        if hero_b64
        else "background:linear-gradient(120deg,#071a2e,#17374b);"
    )
    st.markdown(
        f'''
        <section class="hero" style="{hero_css}">
          <div class="hero-kicker">Mercado financeiro · Brasil e mundo</div>
          <div class="hero-title">O mercado, com mais contexto.</div>
          <div class="hero-copy">Acompanhe índices, moedas, ações e as principais notícias financeiras em um só lugar.</div>
        </section>
        ''',
        unsafe_allow_html=True,
    )

    section_title("Indicadores em destaque", "Acompanhe o dia")
    featured = [
        ("Ibovespa", "^BVSP"),
        ("Dólar / Real", "BRL=X"),
        ("S&P 500", "^GSPC"),
        ("Bitcoin", "BTC-USD"),
    ]
    cols = st.columns(4)
    for col, (label, ticker) in zip(cols, featured):
        with col:
            render_metric(label, ticker)

    cols = st.columns(4)
    for col, (label, ticker) in zip(cols, [("Euro / Real", "EURBRL=X"), ("Nasdaq", "^IXIC"), ("Ouro", "GC=F"), ("Petróleo WTI", "CL=F")]):
        with col:
            render_metric(label, ticker)

    st.markdown('<div class="section-heading"><div><div class="section-label">Visão de mercado</div><h2 style="margin-top:5px">Ibovespa · último mês</h2></div><span class="status-pill">Histórico diário</span></div>', unsafe_allow_html=True)
    history = get_history("^BVSP", "1mo", "1d")
    if not history.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=history.index,
            y=history["Close"],
            mode="lines",
            name="Ibovespa",
            line={"color": "#0f9b8e", "width": 2.6},
            fill="tozeroy",
            fillcolor="rgba(15,155,142,.09)",
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:,.0f} pontos<extra></extra>",
        ))
        fig.update_layout(
            height=330,
            margin=dict(l=8, r=8, t=12, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"color": chart_text_color()},
            xaxis={"showgrid": False, "title": ""},
            yaxis={"gridcolor": "rgba(130,145,165,.17)", "title": "Pontos"},
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "responsive": True})
    else:
        st.info("O histórico do Ibovespa não está disponível agora.")

    st.markdown('<div class="section-heading"><div><div class="section-label">Do Brasil e do exterior</div><h2 style="margin-top:5px">Últimas notícias</h2></div></div>', unsafe_allow_html=True)
    with st.spinner("Consultando fontes de notícias…"):
        news = get_news()
    if news:
        news_cols = st.columns(2)
        for index, article in enumerate(news[:4]):
            with news_cols[index % 2]:
                render_news_card(article)
        st.button("Ver todas as notícias", on_click=lambda: st.session_state.update(page_navigation="Notícias"))
    else:
        st.warning("Não foi possível carregar notícias agora. Tente atualizar em alguns minutos.")


# ============================================================
# PÁGINA: MERCADOS
# ============================================================
elif selected_page == "Mercados":
    page_header(
        "Indicadores globais",
        "Mercados",
        "Uma visão compacta de bolsas, câmbio, commodities e criptoativos. Valores podem ter atraso conforme o provedor.",
    )

    groups = {
        "Bolsas e índices": {k: ASSETS[k] for k in ["Ibovespa", "S&P 500", "Nasdaq Composite", "Dow Jones"]},
        "Moedas": {k: ASSETS[k] for k in ["Dólar / Real", "Euro / Real"]},
        "Commodities": {k: ASSETS[k] for k in ["Ouro", "Petróleo WTI"]},
        "Criptoativos": {"Bitcoin": ASSETS["Bitcoin"]},
    }

    for group_name, items in groups.items():
        st.markdown(f'<div class="section-heading"><div><div class="section-label">Mercado</div><h2 style="margin-top:5px">{group_name}</h2></div></div>', unsafe_allow_html=True)
        entries = list(items.items())
        for start in range(0, len(entries), 4):
            row = st.columns(4)
            for col, (name, ticker) in zip(row, entries[start:start + 4]):
                with col:
                    render_metric(name, ticker)

    with st.expander("Tabela completa de indicadores"):
        st.dataframe(quote_table(ASSETS), use_container_width=True, hide_index=True)


# ============================================================
# PÁGINA: AÇÕES DA B3
# ============================================================
elif selected_page == "Ações da B3":
    page_header(
        "Empresas listadas",
        "Ações da B3",
        "Escolha os papéis que deseja acompanhar. A lista é inicial e pode ser ampliada depois com favoritos pessoais, dividendos e fundamentos.",
    )

    names = list(BRAZILIAN_STOCKS.keys())
    chosen = st.multiselect(
        "Ações para acompanhar",
        names,
        default=names[:6],
        help="Selecione uma ou mais ações para montar sua lista de acompanhamento.",
    )

    if chosen:
        table = quote_table({name: BRAZILIAN_STOCKS[name] for name in chosen})
        if "Variação diária (%)" in table.columns:
            table = table.sort_values("Variação diária (%)", ascending=False, na_position="last")
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Variação diária (%)": st.column_config.NumberColumn(
                    "Variação diária (%)", format="%.2f%%"
                ),
                "Último valor": st.column_config.TextColumn("Último valor"),
                "Código": st.column_config.TextColumn("Código"),
            },
        )

        st.markdown('<div class="section-heading"><div><div class="section-label">Análise do ativo</div><h2 style="margin-top:5px">Histórico de preço</h2></div></div>', unsafe_allow_html=True)
        chart_name = st.selectbox("Escolha uma ação para o gráfico", chosen)
        chart_ticker = BRAZILIAN_STOCKS[chart_name]
        p_col, i_col, t_col = st.columns([1, 1, 1])
        with p_col:
            period_label = st.selectbox("Período", ["1 dia", "5 dias", "1 mês", "3 meses", "6 meses", "1 ano", "5 anos"], index=2)
        with i_col:
            interval_label = st.selectbox("Intervalo", ["1 minuto", "5 minutos", "15 minutos", "30 minutos", "1 hora", "Diário"], index=1)
        with t_col:
            chart_style = st.selectbox("Tipo de gráfico", ["Linha", "Candlestick"])

        period_map = {"1 dia": "1d", "5 dias": "5d", "1 mês": "1mo", "3 meses": "3mo", "6 meses": "6mo", "1 ano": "1y", "5 anos": "5y"}
        interval_map = {"1 minuto": "1m", "5 minutos": "5m", "15 minutos": "15m", "30 minutos": "30m", "1 hora": "60m", "Diário": "1d"}
        selected_period = period_map[period_label]
        selected_interval = interval_map[interval_label]

        if selected_interval in {"1m", "5m", "15m", "30m", "60m"} and selected_period in {"3mo", "6mo", "1y", "5y"}:
            st.info("Para intervalos intradiários, selecione até 1 mês. O Yahoo Finance limita a janela histórica intradiária.")
        else:
            hist = get_history(chart_ticker, selected_period, selected_interval)
            if hist.empty:
                st.warning("Não há dados para essa combinação. Tente outro período ou intervalo.")
            else:
                if chart_style == "Candlestick":
                    fig = go.Figure(go.Candlestick(
                        x=hist.index, open=hist["Open"], high=hist["High"], low=hist["Low"], close=hist["Close"], name=chart_name,
                        increasing_line_color="#0e9f87", decreasing_line_color="#d95c59",
                    ))
                else:
                    fig = go.Figure(go.Scatter(
                        x=hist.index, y=hist["Close"], mode="lines", name=chart_name,
                        line={"color": "#0f9b8e", "width": 2.3},
                    ))
                fig.update_layout(
                    height=430, margin=dict(l=8, r=8, t=15, b=8),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font={"color": chart_text_color()}, hovermode="x unified",
                    xaxis={"showgrid": False, "title": "Data e hora"},
                    yaxis={"gridcolor": "rgba(130,145,165,.17)", "title": "Preço (R$)"},
                    xaxis_rangeslider_visible=False,
                )
                st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "responsive": True})
                if st.checkbox("Mostrar tabela histórica", key="show_stock_history"):
                    st.dataframe(hist.reset_index(), use_container_width=True, hide_index=True)
    else:
        st.info("Selecione ao menos uma ação para montar a lista.")


# ============================================================
# PÁGINA: GRÁFICOS
# ============================================================
elif selected_page == "Gráficos":
    page_header(
        "Ferramentas de análise",
        "Gráficos",
        "Escolha o ativo, compare períodos e alterne entre linha e candlestick. Os intervalos curtos têm histórico limitado pelo provedor.",
    )

    all_assets = {**ASSETS, **BRAZILIAN_STOCKS}
    a_col, p_col, i_col = st.columns([1.35, 1, 1])
    with a_col:
        asset_name = st.selectbox("Ativo", list(all_assets.keys()))
    with p_col:
        period_label = st.selectbox("Período", ["1 dia", "5 dias", "1 mês", "3 meses", "6 meses", "1 ano", "5 anos"], index=2)
    with i_col:
        interval_label = st.selectbox("Intervalo", ["1 minuto", "5 minutos", "15 minutos", "30 minutos", "1 hora", "Diário", "Semanal"], index=1)

    second_row = st.columns([1, 1, 2])
    with second_row[0]:
        chart_style = st.selectbox("Visualização", ["Linha", "Candlestick"])
    with second_row[1]:
        show_volume = st.checkbox("Incluir volume", value=False, disabled=chart_style == "Candlestick")
    with second_row[2]:
        show_history_table = st.checkbox("Mostrar tabela de dados", value=False)

    period_map = {"1 dia": "1d", "5 dias": "5d", "1 mês": "1mo", "3 meses": "3mo", "6 meses": "6mo", "1 ano": "1y", "5 anos": "5y"}
    interval_map = {"1 minuto": "1m", "5 minutos": "5m", "15 minutos": "15m", "30 minutos": "30m", "1 hora": "60m", "Diário": "1d", "Semanal": "1wk"}
    period = period_map[period_label]
    interval = interval_map[interval_label]
    ticker = all_assets[asset_name]

    if interval in {"1m", "5m", "15m", "30m", "60m"} and period in {"3mo", "6mo", "1y", "5y"}:
        st.warning("O provedor limita o histórico intradiário. Escolha um período de até 1 mês ou use o intervalo Diário/Semanal.")
    else:
        hist = get_history(ticker, period, interval)
        if hist.empty:
            st.warning("Dados indisponíveis para o ativo, período ou intervalo selecionado.")
        else:
            include_volume = show_volume and chart_style == "Linha" and "Volume" in hist.columns
            fig = make_subplots(specs=[[{"secondary_y": True}]]) if include_volume else go.Figure()

            if chart_style == "Candlestick":
                trace = go.Candlestick(
                    x=hist.index, open=hist["Open"], high=hist["High"], low=hist["Low"], close=hist["Close"],
                    name=asset_name, increasing_line_color="#0e9f87", decreasing_line_color="#d95c59",
                )
            else:
                trace = go.Scatter(
                    x=hist.index, y=hist["Close"], mode="lines", name=asset_name,
                    line={"color": "#0f9b8e", "width": 2.3},
                )

            if include_volume:
                fig.add_trace(trace, row=1, col=1, secondary_y=False)
                fig.add_trace(go.Bar(
                    x=hist.index, y=hist["Volume"], name="Volume", opacity=.22,
                    marker_color="#8da3b8",
                ), row=1, col=1, secondary_y=True)
                # Esses eixos secundários só existem no layout de subplots criado
                # quando o volume está habilitado.
                fig.update_yaxes(title_text="Preço", secondary_y=False)
                fig.update_yaxes(title_text="Volume", secondary_y=True, showgrid=False)
            else:
                # Uma Figure simples não tem referência de subplot/secondary_y.
                # Definir o título pelo layout funciona em qualquer gráfico.
                fig.add_trace(trace)
                fig.update_layout(yaxis_title="Preço / pontos")
            fig.update_layout(
                title=asset_name,
                height=490,
                margin=dict(l=8, r=8, t=45, b=8),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"color": chart_text_color()},
                hovermode="x unified",
                xaxis={"showgrid": False, "title": "Data e hora"},
                yaxis={"gridcolor": "rgba(130,145,165,.17)", "title": "Preço / pontos"},
                xaxis_rangeslider_visible=False,
                legend={"orientation": "h", "y": 1.08, "x": 0},
            )
            st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "responsive": True})

            first_price = float(hist["Close"].iloc[0])
            last_price = float(hist["Close"].iloc[-1])
            variation = ((last_price / first_price) - 1) * 100 if first_price else 0
            m1, m2, m3 = st.columns(3)
            m1.metric("Primeiro valor no período", format_price(first_price, ticker))
            m2.metric("Último valor disponível", format_price(last_price, ticker))
            m3.metric("Variação no período", f"{variation:+.2f}%")
            if show_history_table:
                st.dataframe(hist.reset_index(), use_container_width=True, hide_index=True)

    st.caption("Gráficos são informativos. Intervalos de 1 minuto não significam, por si só, dados em tempo real.")


# ============================================================
# PÁGINA: NOTÍCIAS
# ============================================================
elif selected_page == "Notícias":
    page_header(
        "Acompanhe o que move os mercados",
        "Notícias financeiras",
        "Manchetes de veículos brasileiros e internacionais. O assunto relacionado é uma indicação automática pelo título, não uma confirmação de causa de mercado.",
    )

    filters = st.columns([1, 1.35, 1.2])
    with filters[0]:
        region = st.selectbox("Região", ["Todas", "Brasil", "Internacional"])
    with filters[1]:
        search_term = st.text_input("Buscar manchete", placeholder="Ex.: dólar, inflação, Petrobras")
    with filters[2]:
        source_filter = st.selectbox("Fonte", ["Todas"] + [feed["name"] for feed in NEWS_FEEDS])

    with st.spinner("Consultando notícias…"):
        news = get_news()

    if region != "Todas":
        news = [article for article in news if article["category"] == region]
    if source_filter != "Todas":
        source_match = source_filter.lower()
        news = [article for article in news if source_match in article["source"].lower() or source_match in article["url"].lower()]
    if search_term.strip():
        term = search_term.strip().casefold()
        news = [article for article in news if term in article["title"].casefold() or term in article.get("description", "").casefold()]

    if not news:
        st.info("Nenhuma notícia encontrada para esses filtros. Tente remover algum filtro ou volte a consultar mais tarde.")
    else:
        st.markdown(f'<span class="status-pill">{len(news)} matérias</span>', unsafe_allow_html=True)
        for start in range(0, len(news), 2):
            columns = st.columns(2)
            for col, article in zip(columns, news[start:start + 2]):
                with col:
                    render_news_card(article)

    st.caption("Imagens dependem do RSS ou dos metadados do site original. Alguns veículos bloqueiam a extração de miniaturas; nesses casos, a matéria continua disponível pelo link.")


# ============================================================
# RODAPÉ
# ============================================================
st.divider()
footer_cols = st.columns([2, 1])
with footer_cols[0]:
    st.caption("Mercado BR · Painel independente de acompanhamento financeiro")
with footer_cols[1]:
    st.caption(f"Página gerada em {datetime.now().astimezone().strftime('%d/%m/%Y às %H:%M')}")
st.caption("Os dados são fornecidos por serviços externos, podem atrasar ou conter falhas e não constituem recomendação de investimento.")
