import webbrowser

from . import tool

SITES = {
    "google": "https://google.com",
    "youtube": "https://youtube.com",
    "facebook": "https://facebook.com",
    "linkedin": "https://linkedin.com",
    "claude": "https://claude.ai",
    "chatgpt": "https://chatgpt.com",
}

SEARCH_URLS = {
    "google": "https://www.google.com/search?q={query}",
    "youtube": "https://www.youtube.com/results?search_query={query}",
    "claude": "https://claude.ai/new?q={query}",
    "chatgpt": "https://chatgpt.com/?q={query}",
}


@tool(
    name="open_website",
    description="Open a known website, or an arbitrary URL, in the default browser.",
    parameters={
        "type": "object",
        "properties": {
            "site": {
                "type": "string",
                "description": (
                    "One of google, youtube, facebook, linkedin, claude, chatgpt, "
                    "or a full URL (e.g. https://example.com)."
                ),
            }
        },
        "required": ["site"],
    },
)
def open_website(site: str) -> str:
    key = site.strip().lower()
    url = SITES.get(key)
    if url is None:
        url = site if site.startswith("http") else f"https://{site}"
    webbrowser.open(url)
    return f"Opened {site}."


@tool(
    name="web_search",
    description="Search a given engine/site (google, youtube, claude, chatgpt) for a query and open the results.",
    parameters={
        "type": "object",
        "properties": {
            "engine": {
                "type": "string",
                "enum": list(SEARCH_URLS.keys()),
                "description": "Which site to search on.",
            },
            "query": {
                "type": "string",
                "description": "What to search for.",
            },
        },
        "required": ["engine", "query"],
    },
)
def web_search(engine: str, query: str) -> str:
    engine = engine.strip().lower()
    template = SEARCH_URLS.get(engine, SEARCH_URLS["google"])
    separator = "+" if engine in ("google", "youtube") else "%20"
    url = template.format(query=query.replace(" ", separator))
    webbrowser.open(url)
    return f"Searching {engine} for {query}."
