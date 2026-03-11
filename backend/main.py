from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import traceback
import os

from backend.test_generator import generate_test_cases
from backend.test_runner import run_tests
from backend.ai_engine import analyze_page, generate_ai_test_cases, analyze_failures

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


class TestRequest(BaseModel):
    url: str


@app.post("/run-tests")
def run_tests_api(request: TestRequest):

    try:
        # Step 1: Analyze page
        print(f"[TestGenAI] Analyzing page: {request.url}")
        page_info = analyze_page(request.url)

        # Step 2: AI generates recommended test cases
        print(f"[TestGenAI] Generating AI test cases...")
        ai_test_cases = generate_ai_test_cases(page_info)
        print(f"[TestGenAI] AI recommended {len(ai_test_cases)} test cases")

        # Step 3: Generate executable test cases (existing logic)
        print(f"[TestGenAI] Generating executable test cases...")
        test_cases = generate_test_cases(request.url)
        print(f"[TestGenAI] Generated {len(test_cases)} executable tests")

        # Step 4: Run Selenium tests (both standard + AI-generated)
        print(f"[TestGenAI] Running Selenium tests...")
        report = run_tests(request.url, test_cases, ai_test_cases=ai_test_cases)
        print(f"[TestGenAI] Tests complete: {report.get('passed', 0)} passed, {report.get('failed', 0)} failed")

        # Step 5: AI analyzes failures
        print(f"[TestGenAI] Running AI failure analysis...")
        failure_analysis = analyze_failures(report.get("details", []), page_info)

        # Add AI sections to report
        report["ai_test_cases"] = ai_test_cases
        report["ai_failure_analysis"] = failure_analysis
        report["page_info"] = {
            "title": page_info.get("title", ""),
            "elements": page_info.get("elements", {}),
        }

        print(f"[TestGenAI] Report ready with AI analysis")
        return report

    except Exception as e:
        print(f"[TestGenAI] ERROR: {traceback.format_exc()}")
        return {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "execution_time": 0,
            "details": [],
            "ai_test_cases": [],
            "ai_failure_analysis": [],
            "error": str(e)
        }