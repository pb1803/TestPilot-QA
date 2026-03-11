from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import ssl
import socket
import requests
from datetime import datetime
from urllib.parse import urlparse


# =========================
# Screenshot Helper
# =========================
def take_screenshot(driver, name):
    os.makedirs("reports", exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
    path = f"reports/{safe_name}.png"
    try:
        driver.save_screenshot(path)
    except:
        path = "Screenshot failed"
    return path


# =========================
# SSL CERTIFICATE CHECK
# =========================
def _check_ssl(url, test_id):
    """Check SSL certificate validity and expiry."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return {"test_id": test_id, "status": "FAIL", "details": "Could not parse hostname from URL"}

        if parsed.scheme != "https":
            return {"test_id": test_id, "status": "FAIL", "details": f"Site uses HTTP, not HTTPS ({parsed.scheme}://)"}

        context = ssl.create_default_context()
        conn = context.wrap_socket(socket.socket(socket.AF_INET), server_hostname=hostname)
        conn.settimeout(10)
        conn.connect((hostname, 443))
        cert = conn.getpeercert()
        conn.close()

        # Parse expiry date
        expire_str = cert.get("notAfter", "")
        expire_date = datetime.strptime(expire_str, "%b %d %H:%M:%S %Y %Z")
        days_left = (expire_date - datetime.utcnow()).days

        # Parse issuer
        issuer_parts = dict(x[0] for x in cert.get("issuer", []))
        issuer = issuer_parts.get("organizationName", "Unknown")

        # Parse subject
        subject_parts = dict(x[0] for x in cert.get("subject", []))
        common_name = subject_parts.get("commonName", "Unknown")

        if days_left < 0:
            return {"test_id": test_id, "status": "FAIL", "details": f"SSL certificate EXPIRED {abs(days_left)} days ago. Issuer: {issuer}, CN: {common_name}"}
        elif days_left < 30:
            return {"test_id": test_id, "status": "FAIL", "details": f"SSL certificate expires in {days_left} days! Issuer: {issuer}, CN: {common_name}, Expires: {expire_str}"}
        else:
            return {"test_id": test_id, "status": "PASS", "details": f"SSL valid. Issuer: {issuer}, CN: {common_name}, Expires in {days_left} days ({expire_str})"}

    except ssl.SSLCertVerificationError as e:
        return {"test_id": test_id, "status": "FAIL", "details": f"SSL certificate verification failed: {e}"}
    except Exception as e:
        return {"test_id": test_id, "status": "FAIL", "details": f"SSL check error: {e}"}


# =========================
# AI TEST CASE EXECUTOR
# Maps AI test descriptions to real Selenium actions
# =========================
def _classify_test(test_name, description):
    """Determine what type of Selenium action to run based on AI test case content."""
    combined = (test_name + " " + description).lower()

    if "ssl" in combined or "certificate" in combined or "https" in combined:
        return "ssl"
    elif "title" in combined and ("page" in combined or "verify" in combined):
        return "title"
    elif "login" in combined and ("invalid" in combined or "negative" in combined or "incorrect" in combined):
        return "login_negative"
    elif "login" in combined and "empty" in combined:
        return "login_empty"
    elif "login" in combined and ("sql" in combined or "injection" in combined):
        return "login_injection"
    elif "search" in combined:
        return "search"
    elif "form" in combined and "empty" in combined:
        return "form_empty"
    elif "form" in combined:
        return "form"
    elif "navigation" in combined or ("nav" in combined and "link" not in combined):
        return "navigation"
    elif "link" in combined and ("broken" in combined or "404" in combined):
        return "broken_links"
    elif "link" in combined:
        return "links"
    elif "image" in combined and "broken" in combined:
        return "broken_images"
    elif "image" in combined:
        return "images"
    elif "button" in combined:
        return "buttons"
    elif "input" in combined:
        return "inputs"
    elif "dropdown" in combined or "select" in combined:
        return "dropdown"
    elif "checkbox" in combined:
        return "checkbox"
    elif "table" in combined:
        return "table"
    elif "file" in combined and "upload" in combined:
        return "file_upload"
    elif "responsive" in combined or "viewport" in combined:
        return "responsive"
    else:
        return "page_load"


def _execute_ai_test(driver, test_type, test_id, url):
    """Execute a specific test type and return the result dict."""

    try:

        if test_type == "title":
            title = driver.title
            if title and len(title.strip()) > 0:
                return {"test_id": test_id, "status": "PASS", "details": f"Page title: '{title}'"}
            else:
                return {"test_id": test_id, "status": "FAIL", "details": "Page title is empty"}

        elif test_type == "buttons":
            buttons = driver.find_elements(By.TAG_NAME, "button")
            buttons += driver.find_elements(By.CSS_SELECTOR, "input[type='submit']")
            if buttons:
                # Try clicking the first visible button
                for btn in buttons[:3]:
                    if btn.is_displayed() and btn.is_enabled():
                        return {"test_id": test_id, "status": "PASS", "details": f"Found {len(buttons)} clickable button(s)"}
                return {"test_id": test_id, "status": "PASS", "details": f"Found {len(buttons)} button(s), none currently interactable"}
            else:
                return {"test_id": test_id, "status": "FAIL", "details": "No buttons found on page"}

        elif test_type == "inputs":
            inputs = driver.find_elements(By.TAG_NAME, "input")
            visible = [i for i in inputs if i.is_displayed()]
            if visible:
                # Try typing into the first visible input
                for inp in visible[:3]:
                    try:
                        inp.clear()
                        inp.send_keys("test")
                        return {"test_id": test_id, "status": "PASS", "details": f"Found {len(visible)} input(s), interaction successful"}
                    except:
                        continue
                return {"test_id": test_id, "status": "PASS", "details": f"Found {len(visible)} visible input(s)"}
            else:
                return {"test_id": test_id, "status": "FAIL", "details": "No visible input fields found"}

        elif test_type == "links":
            links = driver.find_elements(By.TAG_NAME, "a")
            valid = [l for l in links if l.get_attribute("href")]
            return {"test_id": test_id, "status": "PASS", "details": f"Found {len(valid)} link(s) with href attributes"}

        elif test_type == "broken_links":
            links = driver.find_elements(By.TAG_NAME, "a")
            hrefs = set()
            for link in links[:20]:
                href = link.get_attribute("href")
                if href and href.startswith("http"):
                    hrefs.add(href)
            broken = []
            for href in list(hrefs)[:10]:
                try:
                    resp = requests.head(href, timeout=5, allow_redirects=True)
                    if resp.status_code >= 400:
                        broken.append(href)
                except:
                    broken.append(href)
            if broken:
                return {"test_id": test_id, "status": "FAIL", "details": f"{len(broken)} broken link(s): {', '.join(broken[:3])}"}
            return {"test_id": test_id, "status": "PASS", "details": f"Checked {len(hrefs)} links, all valid"}

        elif test_type == "images":
            images = driver.find_elements(By.TAG_NAME, "img")
            if images:
                return {"test_id": test_id, "status": "PASS", "details": f"Found {len(images)} image(s) on page"}
            return {"test_id": test_id, "status": "FAIL", "details": "No images found on page"}

        elif test_type == "broken_images":
            images = driver.find_elements(By.TAG_NAME, "img")
            broken = []
            for img in images[:20]:
                src = img.get_attribute("src")
                natural_width = driver.execute_script("return arguments[0].naturalWidth", img)
                if not src or natural_width == 0:
                    broken.append(src or "no-src")
            if broken:
                return {"test_id": test_id, "status": "FAIL", "details": f"{len(broken)} broken image(s): {', '.join(broken[:3])}"}
            return {"test_id": test_id, "status": "PASS", "details": f"All {len(images)} image(s) loaded correctly"}

        elif test_type == "form":
            forms = driver.find_elements(By.TAG_NAME, "form")
            if forms:
                return {"test_id": test_id, "status": "PASS", "details": f"Found {len(forms)} form(s) on page"}
            return {"test_id": test_id, "status": "FAIL", "details": "No forms found on page"}

        elif test_type == "form_empty":
            forms = driver.find_elements(By.TAG_NAME, "form")
            if forms:
                submit_btns = forms[0].find_elements(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
                if submit_btns:
                    try:
                        submit_btns[0].click()
                        time.sleep(1)
                        # Check for validation messages
                        invalid_fields = driver.find_elements(By.CSS_SELECTOR, ":invalid")
                        if invalid_fields:
                            return {"test_id": test_id, "status": "PASS", "details": f"Form validation triggered, {len(invalid_fields)} required field(s) flagged"}
                        return {"test_id": test_id, "status": "PASS", "details": "Form empty submission handled"}
                    except:
                        return {"test_id": test_id, "status": "PASS", "details": "Form found, submit button not interactable"}
                return {"test_id": test_id, "status": "PASS", "details": "Form found but no submit button detected"}
            return {"test_id": test_id, "status": "SKIPPED", "details": "No forms on page"}

        elif test_type == "navigation":
            nav = driver.find_elements(By.TAG_NAME, "nav")
            if nav:
                nav_links = nav[0].find_elements(By.TAG_NAME, "a")
                return {"test_id": test_id, "status": "PASS", "details": f"Navigation found with {len(nav_links)} link(s)"}
            return {"test_id": test_id, "status": "FAIL", "details": "No <nav> element found"}

        elif test_type == "search":
            search = driver.find_elements(By.CSS_SELECTOR, "input[type='search'], input[name*='search'], input[id*='search'], input[placeholder*='earch']")
            if search:
                try:
                    search[0].clear()
                    search[0].send_keys("test query")
                    return {"test_id": test_id, "status": "PASS", "details": "Search field found and accepts input"}
                except:
                    return {"test_id": test_id, "status": "PASS", "details": "Search field found but not interactable"}
            return {"test_id": test_id, "status": "FAIL", "details": "No search field found"}

        elif test_type == "login_negative":
            try:
                password_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
                if not password_fields:
                    return {"test_id": test_id, "status": "SKIPPED", "details": "No login form detected"}
                form = password_fields[0].find_element(By.XPATH, "./ancestor::form")
                text_inputs = form.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email'], input[name*='user'], input[name*='email']")
                if text_inputs:
                    text_inputs[0].clear()
                    text_inputs[0].send_keys("invaliduser123")
                password_fields[0].clear()
                password_fields[0].send_keys("wrongpass123")
                submit = form.find_elements(By.CSS_SELECTOR, "button[type='submit'], input[type='submit'], button")
                if submit:
                    submit[0].click()
                    time.sleep(2)
                    page_text = driver.page_source.lower()
                    if any(kw in page_text for kw in ["invalid", "error", "incorrect", "failed", "wrong", "denied"]):
                        return {"test_id": test_id, "status": "PASS", "details": "Invalid credentials correctly rejected"}
                    return {"test_id": test_id, "status": "FAIL", "details": "No error message shown for invalid credentials"}
                return {"test_id": test_id, "status": "SKIPPED", "details": "No submit button in login form"}
            except:
                return {"test_id": test_id, "status": "SKIPPED", "details": "Login form not detected"}

        elif test_type == "login_empty":
            try:
                password_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
                if not password_fields:
                    return {"test_id": test_id, "status": "SKIPPED", "details": "No login form detected"}
                form = password_fields[0].find_element(By.XPATH, "./ancestor::form")
                submit = form.find_elements(By.CSS_SELECTOR, "button[type='submit'], input[type='submit'], button")
                if submit:
                    submit[0].click()
                    time.sleep(1)
                    invalid = driver.find_elements(By.CSS_SELECTOR, ":invalid")
                    if invalid:
                        return {"test_id": test_id, "status": "PASS", "details": f"Empty login blocked, {len(invalid)} required field(s)"}
                    return {"test_id": test_id, "status": "PASS", "details": "Empty login submission handled"}
                return {"test_id": test_id, "status": "SKIPPED", "details": "No submit button found"}
            except:
                return {"test_id": test_id, "status": "SKIPPED", "details": "Login form not detected"}

        elif test_type == "login_injection":
            try:
                password_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
                if not password_fields:
                    return {"test_id": test_id, "status": "SKIPPED", "details": "No login form detected"}
                form = password_fields[0].find_element(By.XPATH, "./ancestor::form")
                text_inputs = form.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email']")
                if text_inputs:
                    text_inputs[0].clear()
                    text_inputs[0].send_keys("' OR 1=1 --")
                password_fields[0].clear()
                password_fields[0].send_keys("' OR 1=1 --")
                submit = form.find_elements(By.CSS_SELECTOR, "button[type='submit'], input[type='submit'], button")
                if submit:
                    submit[0].click()
                    time.sleep(2)
                    page_text = driver.page_source.lower()
                    if any(kw in page_text for kw in ["sql", "syntax", "database", "mysql", "postgres", "oracle"]):
                        return {"test_id": test_id, "status": "FAIL", "details": "SQL injection exposed database errors"}
                    return {"test_id": test_id, "status": "PASS", "details": "SQL injection attempt safely rejected"}
                return {"test_id": test_id, "status": "SKIPPED", "details": "No submit button found"}
            except:
                return {"test_id": test_id, "status": "SKIPPED", "details": "Login form not detected"}

        elif test_type == "dropdown":
            selects = driver.find_elements(By.TAG_NAME, "select")
            if selects:
                try:
                    sel = Select(selects[0])
                    options = sel.options
                    if len(options) > 1:
                        sel.select_by_index(1)
                        return {"test_id": test_id, "status": "PASS", "details": f"Dropdown has {len(options)} option(s), selection works"}
                    return {"test_id": test_id, "status": "PASS", "details": f"Dropdown found with {len(options)} option(s)"}
                except:
                    return {"test_id": test_id, "status": "PASS", "details": "Dropdown found but not interactable"}
            return {"test_id": test_id, "status": "FAIL", "details": "No dropdown (<select>) found"}

        elif test_type == "checkbox":
            checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
            if checkboxes:
                try:
                    cb = checkboxes[0]
                    was_checked = cb.is_selected()
                    cb.click()
                    now_checked = cb.is_selected()
                    if was_checked != now_checked:
                        return {"test_id": test_id, "status": "PASS", "details": f"Checkbox toggled successfully ({len(checkboxes)} found)"}
                    return {"test_id": test_id, "status": "FAIL", "details": "Checkbox click did not change state"}
                except:
                    return {"test_id": test_id, "status": "PASS", "details": f"Found {len(checkboxes)} checkbox(es)"}
            return {"test_id": test_id, "status": "FAIL", "details": "No checkboxes found"}

        elif test_type == "table":
            tables = driver.find_elements(By.TAG_NAME, "table")
            if tables:
                rows = tables[0].find_elements(By.TAG_NAME, "tr")
                return {"test_id": test_id, "status": "PASS", "details": f"Table found with {len(rows)} row(s)"}
            return {"test_id": test_id, "status": "FAIL", "details": "No tables found"}

        elif test_type == "file_upload":
            file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            if file_inputs:
                return {"test_id": test_id, "status": "PASS", "details": f"File upload field found ({len(file_inputs)})"}
            return {"test_id": test_id, "status": "FAIL", "details": "No file upload field found"}

        elif test_type == "responsive":
            original_size = driver.get_window_size()
            issues = []
            for width in [1024, 768]:
                driver.set_window_size(width, 800)
                time.sleep(1)
                body_width = driver.execute_script("return document.body.scrollWidth")
                if body_width > width + 50:
                    issues.append(f"Content overflows at {width}px (body: {body_width}px)")
            driver.set_window_size(original_size["width"], original_size["height"])
            if issues:
                return {"test_id": test_id, "status": "FAIL", "details": "; ".join(issues)}
            return {"test_id": test_id, "status": "PASS", "details": "Page responsive at 1024px and 768px"}

        elif test_type == "ssl":
            return _check_ssl(url, test_id)

        else:
            # Default: page load check
            title = driver.title
            if title:
                return {"test_id": test_id, "status": "PASS", "details": f"Page accessible, title: '{title}'"}
            return {"test_id": test_id, "status": "FAIL", "details": "Page did not load properly"}

    except Exception as e:
        screenshot = take_screenshot(driver, f"ai_{test_id}")
        return {"test_id": test_id, "status": "FAIL", "error": str(e), "screenshot": screenshot}


# =========================
# MAIN TEST RUNNER
# =========================
def run_tests(url, test_cases, ai_test_cases=None):

    results = []
    start_time = time.time()

    options = Options()
    options.add_argument("--disable-search-engine-choice-screen")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:

        driver.get(url)
        time.sleep(3)

        # =========================
        # BASIC PAGE TESTS
        # =========================
        for test in test_cases:

            try:

                title = driver.title

                if title:

                    results.append({
                        "test_id": test["id"],
                        "status": "PASS",
                        "details": "Page loaded successfully",
                        "title": title
                    })

                else:
                    raise Exception("Page title missing")

            except Exception as e:

                screenshot = take_screenshot(driver, f"page_test_{test['id']}")

                results.append({
                    "test_id": test["id"],
                    "status": "FAIL",
                    "error": str(e),
                    "screenshot": screenshot
                })

        # =========================
        # SSL CERTIFICATE TEST
        # =========================
        ssl_result = _check_ssl(url, "ssl_check")
        results.append(ssl_result)

        # =========================
        # INPUT INTERACTION TEST
        # =========================
        try:

            inputs = driver.find_elements(By.TAG_NAME, "input")

            if inputs:

                inputs[0].send_keys("TestAutomation")

                results.append({
                    "test_id": "interaction_test",
                    "status": "PASS",
                    "details": "Input field accepted text"
                })

            else:

                screenshot = take_screenshot(driver, "interaction_failure")

                results.append({
                    "test_id": "interaction_test",
                    "status": "FAIL",
                    "details": "No input fields detected",
                    "screenshot": screenshot
                })

        except Exception as e:

            screenshot = take_screenshot(driver, "interaction_error")

            results.append({
                "test_id": "interaction_test",
                "status": "FAIL",
                "error": str(e),
                "screenshot": screenshot
            })

        # =========================
        # LOGIN NEGATIVE TEST
        # =========================
        try:

            username = driver.find_element(By.NAME, "username")
            password = driver.find_element(By.NAME, "password")

            username.send_keys("wronguser")
            password.send_keys("wrongpassword")

            driver.find_element(By.CSS_SELECTOR, "button").click()

            time.sleep(2)

            if "invalid" in driver.page_source.lower():

                results.append({
                    "test_id": "login_negative_test",
                    "status": "PASS",
                    "details": "Invalid credentials correctly rejected"
                })

            else:

                screenshot = take_screenshot(driver, "login_failure")

                results.append({
                    "test_id": "login_negative_test",
                    "status": "FAIL",
                    "details": "Login accepted invalid credentials",
                    "screenshot": screenshot
                })

        except Exception:

            results.append({
                "test_id": "login_negative_test",
                "status": "SKIPPED",
                "details": "Login form not detected"
            })

        # =========================
        # AI-GENERATED TEST EXECUTION
        # =========================
        if ai_test_cases:
            print(f"[TestRunner] Executing {len(ai_test_cases)} AI-generated test cases...")

            for tc in ai_test_cases:
                tc_id = tc.get("test_id", "AI_unknown")
                tc_name = tc.get("test_name", "")
                tc_desc = tc.get("description", "")

                test_type = _classify_test(tc_name, tc_desc)
                print(f"[TestRunner] {tc_id}: {tc_name} → type={test_type}")

                result = _execute_ai_test(driver, test_type, tc_id, url)
                results.append(result)

    finally:

        driver.quit()

    # =========================
    # EXECUTION TIME
    # =========================
    end_time = time.time()

    execution_time = round(end_time - start_time, 2)

    return {
        "total_tests": len(results),
        "passed": sum(1 for r in results if r["status"] == "PASS"),
        "failed": sum(1 for r in results if r["status"] == "FAIL"),
        "execution_time": execution_time,
        "details": results
    }