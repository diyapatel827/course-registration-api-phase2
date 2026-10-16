# Student Academic History API

## Run locally

```bash
python -m venv venv
# Windows PowerShell:
venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://127.0.0.1:8000/docs to try the API.

## Quick local checks

Import an HTML transcript:
```bash
curl -F "file=@student-example.html" http://127.0.0.1:8000/api/v1/students/111/history/import
```

Read the profile:
```bash
curl http://127.0.0.1:8000/api/v1/students/111/profile
```

Save a plan:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/students/111/plan ^
  -H "Content-Type: application/json" ^
  -d "{\"planned_courses\":[{\"course_code\":\"COSC-3506\",\"term\":\"26F\"}]}"
```

## Render

Create a GitHub repository containing `main.py` and `requirements.txt`. In Render, create a Web Service connected to that repository.

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

After deployment, open the service root URL once to wake it up. Put only the base URL (no trailing slash and no path) in `api_url.txt`.

## Important limitations / checks

- Storage is in memory as the assignment suggests; a restart clears records.
- Review `parse_transcript()` against the supplied sample and the course self-test. HTML tables can vary in subtle ways; run the provided self-test before deployment.
- This starter is AI-assisted. In the VPL Comments control, disclose ChatGPT assistance accurately and summarize what you reviewed or changed.
