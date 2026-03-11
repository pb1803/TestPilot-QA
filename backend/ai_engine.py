import os
import json
import requests
from bs4 import BeautifulSoup

# =============================================
# OLLAMA CONFIG
# =============================================
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")


def _call_ollama(prompt):
    """Send a prompt to local Ollama and return the response text."""
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 2000
                }
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json().get("response", "")
    except Exception as e:
        print(f"[AI Engine] Ollama call failed: {e}")
        return None


def _extract_json(text):
    """Extract JSON array from LLM response text."""
    if not text:
        return None

    # Try to find JSON in code blocks
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            cleaned = part.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            if cleaned.startswith("["):
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    continue

    # Try to find raw JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return None


# =============================================
# PART 1 — AI TEST CASE GENERATION
# =============================================

def analyze_page(url):
    """Fetch page and extract element summary + HTML snippets for AI analysis."""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.title.string.strip() if soup.title and soup.title.string else "No title"

        elements = {
            "buttons": len(soup.find_all("button")),
            "inputs": len(soup.find_all("input")),
            "forms": len(soup.find_all("form")),
            "links": len(soup.find_all("a")),
            "images": len(soup.find_all("img")),
            "selects": len(soup.find_all("select")),
            "textareas": len(soup.find_all("textarea")),
        }

        has_login = bool(soup.find("input", {"type": "password"}))
        has_search = bool(soup.find("input", {"type": "search"})) or bool(
            soup.find("input", attrs={"name": lambda x: x and "search" in x.lower()}) if soup.find("input") else False
        )
        has_nav = bool(soup.find("nav"))
        has_table = bool(soup.find("table"))
        has_checkbox = bool(soup.find("input", {"type": "checkbox"}))
        has_dropdown = bool(soup.find("select"))
        has_file_upload = bool(soup.find("input", {"type": "file"}))

        # =============================================
        # EXTRACT HTML SNIPPETS FOR SMARTER AI PROMPTS
        # =============================================
        html_snippets = []

        # Forms — full structure (up to 3)
        for form in soup.find_all("form")[:3]:
            snippet = str(form)[:500]
            html_snippets.append(f"FORM: {snippet}")

        # Nav structure
        nav = soup.find("nav")
        if nav:
            snippet = str(nav)[:500]
            html_snippets.append(f"NAV: {snippet}")

        # Input fields with attributes
        for inp in soup.find_all("input")[:10]:
            attrs = {k: v for k, v in inp.attrs.items() if k in ["type", "name", "id", "placeholder", "required", "aria-label"]}
            html_snippets.append(f"INPUT: {json.dumps(attrs)}")

        # Buttons with text
        for btn in soup.find_all("button")[:5]:
            text = btn.get_text(strip=True)[:50]
            attrs = {k: v for k, v in btn.attrs.items() if k in ["type", "id", "class", "name"]}
            html_snippets.append(f"BUTTON: text='{text}' attrs={json.dumps(attrs)}")

        # Select dropdowns with options
        for sel in soup.find_all("select")[:3]:
            options = [opt.get_text(strip=True)[:30] for opt in sel.find_all("option")[:5]]
            html_snippets.append(f"SELECT: name='{sel.get('name', '')}' options={options}")

        # Links — sample first 10 with text and href
        for link in soup.find_all("a")[:10]:
            text = link.get_text(strip=True)[:40]
            href = link.get("href", "")[:80]
            html_snippets.append(f"LINK: text='{text}' href='{href}'")

        # Images — check src and alt
        for img in soup.find_all("img")[:5]:
            src = img.get("src", "")[:80]
            alt = img.get("alt", "")[:40]
            html_snippets.append(f"IMG: src='{src}' alt='{alt}'")

        # Meta tags
        for meta in soup.find_all("meta")[:5]:
            if meta.get("name") or meta.get("property"):
                html_snippets.append(f"META: {dict(meta.attrs)}")

        return {
            "url": url,
            "title": title,
            "elements": elements,
            "has_login": has_login,
            "has_search": has_search,
            "has_nav": has_nav,
            "has_table": has_table,
            "has_checkbox": has_checkbox,
            "has_dropdown": has_dropdown,
            "has_file_upload": has_file_upload,
            "html_snippets": html_snippets,
        }

    except Exception:
        return {
            "url": url,
            "title": "Unknown",
            "elements": {},
            "has_login": False,
            "has_search": False,
            "has_nav": False,
            "has_table": False,
            "has_checkbox": False,
            "has_dropdown": False,
            "has_file_upload": False,
            "html_snippets": [],
        }


def generate_ai_test_cases(page_info):
    """Generate test cases using local Ollama LLM, fallback to heuristics."""

    # Build HTML context for smarter prompts
    snippets_text = "\n".join(page_info.get("html_snippets", [])[:30])

    prompt = f"""You are an expert QA engineer. Analyze this website and generate test cases.

Website URL: {page_info['url']}
Page Title: {page_info['title']}
Detected Elements: {json.dumps(page_info['elements'])}
Has Login Form: {page_info['has_login']}
Has Search: {page_info['has_search']}
Has Navigation: {page_info['has_nav']}
Has Table: {page_info['has_table']}
Has Checkboxes: {page_info['has_checkbox']}
Has Dropdowns: {page_info['has_dropdown']}
Has File Upload: {page_info['has_file_upload']}

ACTUAL HTML ELEMENTS FOUND ON PAGE:
{snippets_text}

Based on the actual HTML elements above, generate 5-10 targeted QA test cases.
Focus on testing the specific elements you can see (forms, buttons, inputs, links, images, navigation).
Always include an SSL/HTTPS certificate check test.
Return ONLY a valid JSON array with no other text:
[{{"test_id": "TC_001", "test_name": "...", "description": "...", "expected_result": "..."}}]"""

    print(f"[AI Engine] Calling Ollama ({OLLAMA_MODEL}) for test case generation...")
    response_text = _call_ollama(prompt)

    if response_text:
        result = _extract_json(response_text)
        if result:
            print(f"[AI Engine] Ollama generated {len(result)} test cases")
            return result
        else:
            print(f"[AI Engine] Could not parse Ollama response, using heuristics")

    return _generate_with_heuristics(page_info)


def _generate_with_heuristics(page_info):
    """Smart heuristic-based test case generation based on detected page features."""

    test_cases = []
    tc_num = 1

    # Always test page load
    test_cases.append({
        "test_id": f"TC_{tc_num:03d}",
        "test_name": "Page Load Verification",
        "description": f"Verify that {page_info['url']} loads successfully with a valid page title",
        "expected_result": "Page loads within 5 seconds with a non-empty title"
    })
    tc_num += 1

    # Navigation tests
    if page_info.get("has_nav") or page_info["elements"].get("links", 0) > 0:
        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "Navigation Link Validation",
            "description": "Verify all navigation links are functional and do not return 404 errors",
            "expected_result": "All links respond with HTTP 200 and load valid pages"
        })
        tc_num += 1

    # Form validation tests
    if page_info["elements"].get("forms", 0) > 0:
        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "Form Submission - Empty Fields",
            "description": "Submit the form with all fields empty to test validation",
            "expected_result": "Form displays appropriate validation error messages"
        })
        tc_num += 1

        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "Form Submission - Valid Data",
            "description": "Submit the form with valid test data in all required fields",
            "expected_result": "Form submits successfully and shows confirmation"
        })
        tc_num += 1

    # Login tests
    if page_info.get("has_login"):
        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "Login - Invalid Credentials",
            "description": "Attempt login with incorrect username and password",
            "expected_result": "System displays error message rejecting invalid credentials"
        })
        tc_num += 1

        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "Login - Empty Fields",
            "description": "Click login button without entering any credentials",
            "expected_result": "System shows validation error for required fields"
        })
        tc_num += 1

        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "Login - SQL Injection Attempt",
            "description": "Enter SQL injection pattern (e.g., ' OR 1=1 --) in login fields",
            "expected_result": "System rejects input and does not expose database errors"
        })
        tc_num += 1

    # Search tests
    if page_info.get("has_search"):
        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "Search Functionality",
            "description": "Enter a search term and verify results are displayed",
            "expected_result": "Search returns relevant results or a no-results message"
        })
        tc_num += 1

    # Input interaction tests
    if page_info["elements"].get("inputs", 0) > 0:
        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "Input Field Interaction",
            "description": "Verify all input fields accept user text and are interactable",
            "expected_result": "Input fields accept text without errors"
        })
        tc_num += 1

    # Image tests
    if page_info["elements"].get("images", 0) > 0:
        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "Broken Image Detection",
            "description": "Verify all images on the page load correctly without broken references",
            "expected_result": "All images display properly with valid src attributes"
        })
        tc_num += 1

    # Button tests
    if page_info["elements"].get("buttons", 0) > 0:
        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "Button Clickability",
            "description": "Verify all buttons on the page are clickable and responsive",
            "expected_result": "Buttons respond to click events without JavaScript errors"
        })
        tc_num += 1

    # Dropdown tests
    if page_info.get("has_dropdown"):
        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "Dropdown Selection",
            "description": "Verify dropdown menus can be opened and options selected",
            "expected_result": "Dropdown displays options and selection is registered"
        })
        tc_num += 1

    # Checkbox tests
    if page_info.get("has_checkbox"):
        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "Checkbox Toggle",
            "description": "Verify checkboxes can be checked and unchecked",
            "expected_result": "Checkbox state toggles correctly on click"
        })
        tc_num += 1

    # File upload tests
    if page_info.get("has_file_upload"):
        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "File Upload Validation",
            "description": "Verify the file upload field accepts valid file types",
            "expected_result": "File is accepted and upload indicator appears"
        })
        tc_num += 1

    # Table tests
    if page_info.get("has_table"):
        test_cases.append({
            "test_id": f"TC_{tc_num:03d}",
            "test_name": "Table Data Rendering",
            "description": "Verify table displays data with proper rows and columns",
            "expected_result": "Table renders with visible headers and data rows"
        })
        tc_num += 1

    # Always add responsive design check
    test_cases.append({
        "test_id": f"TC_{tc_num:03d}",
        "test_name": "Page Responsiveness",
        "description": "Verify page elements are visible and not overlapping at different viewport sizes",
        "expected_result": "No content overflow or hidden elements at 1024px and 768px widths"
    })

    return test_cases


# =============================================
# PART 2 — AI FAILURE ANALYSIS
# =============================================

def analyze_failures(test_results, page_info):
    """Analyze failures using local Ollama LLM, fallback to heuristics."""

    # Build results summary
    results_text = ""
    for r in test_results:
        results_text += f"Test {r['test_id']} → {r['status']}\n"
        if r.get("details"):
            results_text += f"Reason: {r['details']}\n"
        if r.get("error"):
            results_text += f"Error: {r['error']}\n"
        results_text += "\n"

    prompt = f"""You are an expert QA engineer analyzing test results.

Website: {page_info['url']}
Page Title: {page_info['title']}

Test Results:
{results_text}

For each FAIL or SKIPPED test, provide analysis. Return ONLY a valid JSON array with no other text:
[{{"test_id": "...", "failure": "...", "explanation": "...", "possible_cause": "...", "recommendation": "..."}}]

If all tests passed, return: [{{"test_id": "all", "failure": "None", "explanation": "All tests passed successfully", "possible_cause": "N/A", "recommendation": "Continue monitoring"}}]"""

    print(f"[AI Engine] Calling Ollama ({OLLAMA_MODEL}) for failure analysis...")
    response_text = _call_ollama(prompt)

    if response_text:
        result = _extract_json(response_text)
        if result:
            print(f"[AI Engine] Ollama produced {len(result)} analysis entries")
            return result
        else:
            print(f"[AI Engine] Could not parse Ollama analysis, using heuristics")

    return _analyze_with_heuristics(test_results, page_info)


def _analyze_with_heuristics(test_results, page_info):
    """Smart heuristic-based failure analysis."""

    analysis = []

    failed_or_skipped = [r for r in test_results if r["status"] in ("FAIL", "SKIPPED")]

    if not failed_or_skipped:
        analysis.append({
            "test_id": "all",
            "failure": "None",
            "explanation": "All tests passed successfully. The website appears to be functioning correctly.",
            "possible_cause": "N/A",
            "recommendation": "Continue regular monitoring and consider adding more edge-case tests."
        })
        return analysis

    for result in failed_or_skipped:
        tid = str(result.get("test_id", "unknown"))
        status = result["status"]
        details = result.get("details", "")
        error = result.get("error", "")
        reason = details or error

        entry = {"test_id": tid}

        # Interaction test failure
        if "interaction" in tid.lower():
            entry["failure"] = "Input interaction test failed"
            if "no input" in reason.lower():
                entry["explanation"] = "The page does not contain any <input> HTML elements for the test to interact with."
                entry["possible_cause"] = "The page may use custom JavaScript components, contenteditable divs, or shadow DOM elements instead of standard HTML input fields."
                entry["recommendation"] = "Inspect the page for non-standard input mechanisms. Consider testing with contenteditable elements or JavaScript-rendered inputs."
            else:
                entry["explanation"] = f"Input interaction failed: {reason}"
                entry["possible_cause"] = "The input field may be disabled, hidden, or blocked by an overlay."
                entry["recommendation"] = "Check if input fields have disabled/readonly attributes or if modal overlays are present."

        # Login test
        elif "login" in tid.lower():
            if status == "SKIPPED":
                entry["failure"] = "Login test was skipped"
                entry["explanation"] = "No login form was detected on this page. The test requires <input> fields named 'username' and 'password'."
                entry["possible_cause"] = "This page may not have a login form, or the login page may be at a different URL path."
                entry["recommendation"] = "Verify the correct login page URL. Check if the form uses different field names (e.g., 'email' instead of 'username')."
            else:
                entry["failure"] = "Login negative test failed"
                entry["explanation"] = f"The login validation test failed: {reason}"
                entry["possible_cause"] = "The application may not display clear error messages for invalid credentials, or the error text differs from expected patterns."
                entry["recommendation"] = "Check the actual error message text. Update the test to match the application's specific error message format."

        # Page load failure
        elif "page" in reason.lower() or "title" in reason.lower() or "load" in reason.lower():
            entry["failure"] = "Page load verification failed"
            entry["explanation"] = f"The page failed to load properly: {reason}"
            entry["possible_cause"] = "The server may be slow, the URL may be incorrect, or the page may have JavaScript errors preventing rendering."
            entry["recommendation"] = "Verify the URL is correct and accessible. Check server response time. Look for JavaScript console errors."

        # Generic failure
        else:
            entry["failure"] = f"Test {tid} {status.lower()}"
            entry["explanation"] = reason if reason else "The test did not complete successfully."
            entry["possible_cause"] = "Element may not exist on the page, may be hidden, or page structure may have changed."
            entry["recommendation"] = "Review the page structure and ensure test selectors match current HTML elements."

        analysis.append(entry)

    return analysis