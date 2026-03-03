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
    return jsonify({
        "sha": data.get("sha"),
        "content": content,
        "encoding": data.get("encoding")
    })


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


# ==========================================================
# 🆕 CREATE REPOSITORY
# ==========================================================
@app.post("/api/create-repo")
def create_repo():
    payload = request.get_json(force=True)
    name = payload["name"]
    description = payload.get("description", "")
    private = payload.get("private", False)

    body = {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": True
    }

    r = requests.post(
        f"{GITHUB_API}/user/repos",
        headers=gh_headers(),
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    return jsonify(r.json()), r.status_code


# ==========================================================
# 🆕 CREATE FOLDER (via .gitkeep file)
# ==========================================================
@app.post("/api/create-folder")
def create_folder():
    payload = request.get_json(force=True)
    owner = payload["owner"]
    repo = payload["repo"]
    folder_path = payload["folder"]
    branch = payload.get("branch", "main")

    path = f"{folder_path}/.gitkeep"

    body = {
        "message": f"Create folder {folder_path}",
        "content": base64.b64encode(b"").decode("utf-8"),
        "branch": branch
    }

    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    r = requests.put(url, headers=gh_headers(), json=body, timeout=30)
    r.raise_for_status()
    return jsonify(r.json()), r.status_code


# ==========================================================
# 🆕 CREATE BRANCH
# ==========================================================
@app.post("/api/create-branch")
def create_branch():
    payload = request.get_json(force=True)
    owner = payload["owner"]
    repo = payload["repo"]
    new_branch = payload["new_branch"]
    from_branch = payload.get("from_branch", "main")

    # Get base branch SHA
    ref_url = f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{from_branch}"
    ref_resp = requests.get(ref_url, headers=gh_headers(), timeout=30)
    ref_resp.raise_for_status()
    sha = ref_resp.json()["object"]["sha"]

    body = {
        "ref": f"refs/heads/{new_branch}",
        "sha": sha
    }

    create_url = f"{GITHUB_API}/repos/{owner}/{repo}/git/refs"
    r = requests.post(create_url, headers=gh_headers(), json=body, timeout=30)
    r.raise_for_status()
    return jsonify(r.json()), r.status_code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)
