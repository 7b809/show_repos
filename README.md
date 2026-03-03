# Vercel GitHub CRUD (Flask + Jinja)

A minimal Flask app deployed on Vercel to **browse, view, edit, create, and delete** files in your GitHub repositories using a **Personal Access Token (PAT)**.

## Features
- List repositories for the authenticated user (left column)
- Browse directories and open files (right column)
- Edit and save changes (creates commits)
- Delete files

## Setup
1. **Create a GitHub PAT** with access to repository contents (read/write).
2. **Set the environment variable** `GITHUB_TOKEN` in your Vercel Project Settings (recommended) or locally in a `.env` file for development:
   ```env
   GITHUB_TOKEN=ghp_xxx
   ```

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export FLASK_ENV=development   # Windows: set FLASK_ENV=development
python app.py
# open http://localhost:3000
```

## Deploy to Vercel
1. Push this folder to a GitHub repository.
2. Import the repo into Vercel and set the **Environment Variable** `GITHUB_TOKEN`.
3. Deploy. Flask will be detected automatically.

> Note: On Vercel, static files should live in the `public/` directory (already set up). 

## Notes
- The app uses GitHub's Contents API which expects/returns Base64 for file bodies.
- To create a folder, create a file with a path like `folder/newfile.txt`.
- Optional: specify a branch in the UI to read/write on that ref; otherwise the repo default branch is used by GitHub when omitted.
