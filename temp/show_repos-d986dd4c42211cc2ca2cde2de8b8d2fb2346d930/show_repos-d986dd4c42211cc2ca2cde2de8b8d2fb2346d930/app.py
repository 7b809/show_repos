from flask import Flask, render_template, request, jsonify
import base64, os, requests, zipfile, io
from werkzeug.utils import secure_filename

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = Flask(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Configure upload folder
UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = {'zip'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

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

# --- Create new repository ---
@app.post("/api/create-repo")
def create_repo():
    payload = request.get_json(force=True)
    name = payload.get("name")
    description = payload.get("description", "")
    private = payload.get("private", False)
    auto_init = payload.get("auto_init", False)
    
    if not name:
        return jsonify({"error": "Repository name is required"}), 400
    
    body = {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": auto_init
    }
    
    r = requests.post(
        f"{GITHUB_API}/user/repos",
        headers=gh_headers(),
        json=body,
        timeout=30
    )
    
    if r.status_code == 201:
        return jsonify(r.json()), 201
    else:
        return jsonify({"error": r.text}), r.status_code

# --- Upload and extract zip file ---
@app.post("/api/upload-zip")
def upload_zip():
    if 'zipfile' not in request.files:
        return jsonify({"error": "No zip file provided"}), 400
    
    file = request.files['zipfile']
    owner = request.form.get('owner')
    repo = request.form.get('repo')
    branch = request.form.get('branch', 'main')
    commit_message = request.form.get('message', 'Upload zip contents')
    
    if not owner or not repo:
        return jsonify({"error": "Owner and repo required"}), 400
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not file.filename.endswith('.zip'):
        return jsonify({"error": "File must be a zip archive"}), 400
    
    try:
        # Read zip file
        zip_data = file.read()
        zip_file = zipfile.ZipFile(io.BytesIO(zip_data))
        
        results = {
            "success": [],
            "failed": [],
            "skipped": []
        }
        
        # Process each file in zip
        for zip_info in zip_file.infolist():
            # Skip directories
            if zip_info.filename.endswith('/'):
                continue
                
            # Clean path (remove leading/trailing slashes)
            file_path = zip_info.filename.strip('/')
            
            # Read file content
            with zip_file.open(zip_info) as f:
                content = f.read()
            
            # Check if file is text or binary
            try:
                content_text = content.decode('utf-8')
                content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            except UnicodeDecodeError:
                # Binary file - encode directly
                content_b64 = base64.b64encode(content).decode('utf-8')
            
            # Check if file already exists
            check_url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{file_path}"
            params = {"ref": branch}
            
            check_r = requests.get(check_url, headers=gh_headers(), params=params, timeout=30)
            
            body = {
                "message": f"Upload {file_path} via zip",
                "content": content_b64,
                "branch": branch
            }
            
            # If file exists, include sha for update
            if check_r.status_code == 200:
                existing = check_r.json()
                body["sha"] = existing.get("sha")
                body["message"] = f"Update {file_path} via zip"
            
            # Upload file
            upload_r = requests.put(check_url, headers=gh_headers(), json=body, timeout=30)
            
            if upload_r.status_code in [200, 201]:
                results["success"].append(file_path)
            else:
                results["failed"].append({
                    "path": file_path,
                    "error": upload_r.text
                })
        
        return jsonify({
            "message": f"Processed {len(results['success'])} files, {len(results['failed'])} failed",
            "results": results
        }), 200
        
    except zipfile.BadZipFile:
        return jsonify({"error": "Invalid zip file"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Upload single file to specific path ---
@app.post("/api/upload-file")
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    owner = request.form.get('owner')
    repo = request.form.get('repo')
    path = request.form.get('path', '')
    branch = request.form.get('branch', 'main')
    commit_message = request.form.get('message', f'Upload {file.filename}')
    
    if not owner or not repo:
        return jsonify({"error": "Owner and repo required"}), 400
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Construct full path
    if path:
        file_path = f"{path.strip('/')}/{secure_filename(file.filename)}"
    else:
        file_path = secure_filename(file.filename)
    
    # Read file content
    content = file.read()
    
    # Check if binary or text
    try:
        content_text = content.decode('utf-8')
        content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    except UnicodeDecodeError:
        content_b64 = base64.b64encode(content).decode('utf-8')
    
    # Check if file exists
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{file_path}"
    params = {"ref": branch}
    
    check_r = requests.get(url, headers=gh_headers(), params=params, timeout=30)
    
    body = {
        "message": commit_message,
        "content": content_b64,
        "branch": branch
    }
    
    if check_r.status_code == 200:
        existing = check_r.json()
        body["sha"] = existing.get("sha")
    
    # Upload file
    upload_r = requests.put(url, headers=gh_headers(), json=body, timeout=30)
    
    if upload_r.status_code in [200, 201]:
        return jsonify({
            "message": "File uploaded successfully",
            "path": file_path,
            "data": upload_r.json()
        }), upload_r.status_code
    else:
        return jsonify({"error": upload_r.text}), upload_r.status_code

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)