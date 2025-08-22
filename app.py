import os, urllib.parse
from flask import Flask, request, jsonify, Response
import requests

app = Flask(__name__)

# Περιμένουμε να βάλεις αυτά τα "μυστικά" στο Render (θα σου πω πιο κάτω)
ELS_API_KEY   = os.getenv("ELS_API_KEY")        # Scopus API key
ELS_INSTTOKEN = os.getenv("ELS_INSTTOKEN", "")  # προαιρετικό institutional token (αν έχεις)
UPSTREAM_PROXY = os.getenv("UPSTREAM_PROXY")     # π.χ. http://proxy.uoa.gr:8080 ή http://USER:PASS@proxy.uoa.gr:8080
PROXY_KEY = os.getenv("PROXY_KEY")               # μυστικό που θα στέλνει το GPT (X-Proxy-Key)

# Βασικοί έλεγχοι
if not ELS_API_KEY:
    raise RuntimeError("Set ELS_API_KEY")
if not UPSTREAM_PROXY:
    raise RuntimeError("Set UPSTREAM_PROXY (e.g. http://proxy.uoa.gr:8080)")
if not PROXY_KEY:
    raise RuntimeError("Set PROXY_KEY")

# Όλες οι κλήσεις θα περνούν μέσα από τον πανεπιστημιακό proxy
PROXIES = {"http": UPSTREAM_PROXY, "https": UPSTREAM_PROXY}
ELSEVIER_BASE = "https://api.elsevier.com"

# Δεκτό είτε header X-Proxy-Key είτε query ?key=... (για να μπορείς να δοκιμάζεις από browser)
def _authorized(req):
    header_key = req.headers.get("X-Proxy-Key")
    query_key = req.args.get("key")
    return (header_key == PROXY_KEY) or (query_key == PROXY_KEY)

def _els_headers():
    h = {"X-ELS-APIKey": ELS_API_KEY, "Accept": "application/json"}
    if ELS_INSTTOKEN:
        h["X-ELS-Insttoken"] = ELS_INSTTOKEN
    return h

@app.before_request
def guard():
    # Το health είναι ελεύθερο για να το δεις από browser
    if request.path == "/scopus/health":
        return
    if not _authorized(request):
        return jsonify({"error": "Unauthorized"}), 401

@app.get("/scopus/health")
def health():
    return {"status": "ok"}

@app.get("/scopus/search")
def search_scopus():
    # Επιτρέπουμε βασικές παραμέτρους αναζήτησης
    allowed = {"query", "start", "count", "sort", "view", "field", "cursor", "cursorMax"}
    qp = {k: v for k, v in request.args.items() if k in allowed and v is not None}
    # Κλήση προς Elsevier
    r = requests.get(f"{ELSEVIER_BASE}/content/search/scopus",
                     headers=_els_headers(), params=qp, proxies=PROXIES, timeout=60)
    return Response(r.content, status=r.status_code,
                    content_type=r.headers.get("Content-Type", "application/json"))

@app.get("/scopus/abstract/<scopus_id>")
def get_abstract(scopus_id):
    qp = {k: v for k, v in request.args.items() if k in {"view", "field"} and v is not None}
    r = requests.get(f"{ELSEVIER_BASE}/content/abstract/scopus_id/{urllib.parse.quote(scopus_id)}",
                     headers=_els_headers(), params=qp, proxies=PROXIES, timeout=60)
    return Response(r.content, status=r.status_code,
                    content_type=r.headers.get("Content-Type", "application/json"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
