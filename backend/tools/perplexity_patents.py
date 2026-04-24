"""
Perplexity Patents API wrapper.
Location: backend/tools/perplexity_patents.py

Reads configuration from env vars:
  PERPLEXITY_API_KEY           – API key
  PERPLEXITY_PATENTS_ENDPOINT  – full endpoint URL
  PERPLEXITY_MAX_RESULTS       – max references to return (default 10)

The wrapper is designed so USPTO / OpenAlex can be added later by
implementing the same interface and selecting via env var PATENT_BACKEND.
"""
import json
import logging
import os
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
_ENDPOINT = os.environ.get(
    "PERPLEXITY_PATENTS_ENDPOINT",
    "https://api.perplexity.ai/chat/completions",
)
_MAX_RESULTS = int(os.environ.get("PERPLEXITY_MAX_RESULTS", "10"))
_BACKEND = os.environ.get("PATENT_BACKEND", "perplexity")  # perplexity | mock


def search_patents(query: str) -> list[dict]:
    """
    Search for prior art using the configured backend.

    Args:
        query: UCS search string from NAA agent.

    Returns:
        List of dicts with keys: title, abstract, url, year, authors.
    """
    # if _BACKEND == "mock" or not _API_KEY:
    #     logger.warning("Using mock patent results (PERPLEXITY_API_KEY not set or PATENT_BACKEND=mock)")
    #     return _mock_results(query)

    if _BACKEND == "perplexity":
        return _perplexity_search(query)

    # Future: elif _BACKEND == "openalex": return _openalex_search(query)
    # Future: elif _BACKEND == "uspto":    return _uspto_search(query)

    raise ValueError(f"Unknown PATENT_BACKEND: {_BACKEND}")


# ── Perplexity ────────────────────────────────────────────────────────────────

def _perplexity_search(query: str) -> list[dict]:
    """
    Uses the Perplexity Sonar model to do web-grounded patent/literature search.
    """
    system_msg = (
        "You are a patent research assistant. "
        "When given a search query, find the most relevant patents and academic papers. "
        f"Return ONLY a JSON array (no markdown) with up to {_MAX_RESULTS} items, "
        'each with keys: "title", "authors", "year", "abstract", "url". '
        "Prefer patent documents. Be concise in abstracts (2-3 sentences max)."
    )

    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"Find prior art for: {query}"},
        ],
        "max_tokens": 3000,
        "return_citations": True,
    }

    headers = {
        "Authorization": f"Bearer {_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    req = urllib.request.Request(
        _ENDPOINT,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        logger.error("Perplexity API error %s: %s", exc.code, body)
        raise RuntimeError(f"Perplexity API returned HTTP {exc.code}: {body}") from exc

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "[]").strip()

    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        results = json.loads(content)
        if not isinstance(results, list):
            results = []
    except json.JSONDecodeError:
        logger.warning("Could not parse Perplexity response as JSON, returning empty list")
        results = []

    # Fall back to Perplexity's native citations if model didn't return structured JSON
    citations = data.get("citations", [])
    if citations and not results:
        results = [
            {"title": c, "abstract": "", "url": c, "authors": [], "year": ""}
            for c in citations[:_MAX_RESULTS]
        ]

    return results[:_MAX_RESULTS]


# # ── Mock (for local dev / testing) ───────────────────────────────────────────
#
# def _mock_results(query: str) -> list[dict]:
#     """Return deterministic fake results for local testing."""
#     return [
#         {
#             "title": "US10123456B2 – Adaptive Neural Interface with Closed-Loop Feedback",
#             "authors": ["Smith, J.", "Doe, A."],
#             "year": "2021",
#             "abstract": (
#                 "A neural interface system comprising electrode arrays, signal conditioning "
#                 "circuits, and a closed-loop feedback controller for real-time neural modulation. "
#                 "The system adapts stimulation parameters based on recorded biomarkers."
#             ),
#             "url": "https://patents.google.com/patent/US10123456B2",
#         },
#         {
#             "title": "WO2022/098765A1 – Implantable Biosensor Array with Wireless Telemetry",
#             "authors": ["Chen, L.", "Patel, R.", "Kim, S."],
#             "year": "2022",
#             "abstract": (
#                 "An implantable biosensor system with multi-channel electrodes, low-power "
#                 "signal processing ASIC, and inductive wireless telemetry for continuous "
#                 "physiological monitoring."
#             ),
#             "url": "https://patents.google.com/patent/WO2022098765A1",
#         },
#         {
#             "title": "Cortical Stimulation Systems: A Review of Prior Art",
#             "authors": ["Brown, T.", "Garcia, M."],
#             "year": "2020",
#             "abstract": (
#                 "Comprehensive review of cortical stimulation architectures including "
#                 "microelectrode arrays, current-steering circuits, and safety compliance "
#                 "subsystems used in clinical neural interface devices."
#             ),
#             "url": "https://doi.org/10.1016/j.neuroscience.2020.01.001",
#         },
#         {
#             "title": "US9876543B1 – Low-Power Bioelectronic Implant with Energy Harvesting",
#             "authors": ["Wang, X."],
#             "year": "2019",
#             "abstract": (
#                 "A bioelectronic implant that harvests energy from body heat and motion, "
#                 "incorporating a rectifier, energy storage, and a duty-cycled microcontroller "
#                 "for chronic neural recording applications."
#             ),
#             "url": "https://patents.google.com/patent/US9876543B1",
#         },
#         {
#             "title": "Closed-Loop Neuromodulation: State of the Art and Future Directions",
#             "authors": ["Johnson, P.", "Lee, H.", "Martinez, C."],
#             "year": "2023",
#             "abstract": (
#                 "Survey of closed-loop neuromodulation systems emphasizing real-time biomarker "
#                 "detection algorithms, adaptive stimulation protocols, and safety interlock mechanisms."
#             ),
#             "url": "https://doi.org/10.1038/s41551-023-00001-1",
#         },
#     ]