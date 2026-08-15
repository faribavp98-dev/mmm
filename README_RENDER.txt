DEPLOY ON RENDER - FREE DEMO

1) Create a GitHub repository.
2) Upload ALL files in this folder to the repository root.
3) Open Render and sign in with GitHub.
4) New -> Web Service.
5) Select the repository.
6) Choose Free plan.
7) Build command:
   pip install -r requirements.txt
8) Start command:
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
9) Deploy.

After deployment Render gives you an https://....onrender.com address.

IMPORTANT:
This demo uses SQLite. Render Free Web Services have ephemeral filesystems,
so database changes can be lost after restart/redeploy/spin-down. This is
acceptable for a test/demo only. For a real team system, use PostgreSQL.

No Telegram token is needed for this web-only demo.
