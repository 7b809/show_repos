from flask import Flask, render_template, request, jsonify
import base64, os, requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = Flask(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")


def gh_headers():
    if not GITHUB_TOKEN:
        # Helpful error for local dev if token isn't present
        raise RuntimeError("GITHUB_TOKEN environment variable is not set.")
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }


@app.route("/")
def home():
    return render_template("index.html")


# --- Repos (left column) ---
@app.get("/api/repos")
def list_repos():
    page = int(request.args.get("page", "1"))
    r = requests.get(
        f"{GITHUB_API}/user/repos",
        headers=gh_headers(),
        params={"per_page": 100, "page": page, "sort": "updated"},
        timeout=30,
    )
    r.raise_for_status()
    return jsonify(r.json())


# --- Directory listing & file fetch (right column) ---
@app.get("/api/contents")
def get_contents():
    owner = request.args["owner"]
    repo = request.args["repo"]
    path = request.args.get("path", "")
    ref = request.args.get("ref")
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    params = {"ref": ref} if ref else {}
    r = requests.get(url, headers=gh_headers(), params=params, timeout=30)
    r.raise_for_status()
    return jsonify(r.json())


@app.get("/api/file")
def get_file():
    owner = request.args["owner"]
    repo = request.args["repo"]
    path = request.args["path"]
    ref = request.args.get("ref")

    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    params = {"ref": ref} if ref else {}
    r = requests.get(url, headers=gh_headers(), params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    content_b64 = data.get("content", "")
    content = base64.b64decode(content_b64).decode("utf-8", errors="replace") if content_b64 else ""
    return jsonify({"sha": data.get("sha"), "content": content, "encoding": data.get("encoding")})


# --- Create/Update file (CRUD: C/U) ---
@app.post("/api/save")
def save_file():
    payload = request.get_json(force=True)
    owner = payload["owner"]
    repo = payload["repo"]
    path = payload["path"]
    message = payload.get("message", "Update via web editor")
    branch = payload.get("branch")
    sha = payload.get("sha")
    content_text = payload["content"]

    content_b64 = base64.b64encode(content_text.encode("utf-8")).decode("utf-8")
    body = {"message": message, "content": content_b64}
    if sha:
        body["sha"] = sha
    if branch:
        body["branch"] = branch

    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    r = requests.put(url, headers=gh_headers(), json=body, timeout=30)
    r.raise_for_status()
    return jsonify(r.json()), r.status_code


# --- Delete file (CRUD: D) ---
@app.post("/api/delete")
def delete_file():
    payload = request.get_json(force=True)
    owner = payload["owner"]
    repo = payload["repo"]
    path = payload["path"]
    sha = payload["sha"]
    message = payload.get("message", f"Delete {path} via web")

    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    body = {"message": message, "sha": sha}
    r = requests.delete(url, headers=gh_headers(), json=body, timeout=30)
    r.raise_for_status()
    return jsonify(r.json()), r.status_code


# --- Create a new folder (with optional .gitkeep file) ---
@app.post("/api/create-folder")
def create_folder():
    payload = request.get_json(force=True)
    owner = payload["owner"]
    repo = payload["repo"]
    folder_path = payload["path"]
    branch = payload.get("branch")
    message = payload.get("message", f"Create folder {folder_path}")
    
    # GitHub doesn't support empty folders, so we create a .gitkeep file
    gitkeep_path = f"{folder_path}/.gitkeep".replace('//', '/')
    content_b64 = base64.b64encode(b"".encode("utf-8")).decode("utf-8")
    
    body = {
        "message": message,
        "content": content_b64
    }
    if branch:
        body["branch"] = branch

    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{gitkeep_path}"
    r = requests.put(url, headers=gh_headers(), json=body, timeout=30)
    r.raise_for_status()
    return jsonify(r.json()), r.status_code


if __name__ == "__main__":
    # For local dev only
    app.run(host="0.0.0.0", port=3000, debug=True)