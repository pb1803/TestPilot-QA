import requests
from bs4 import BeautifulSoup


def generate_test_cases(url):

    test_cases = []

    try:

        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        buttons = soup.find_all("button")
        inputs = soup.find_all("input")
        forms = soup.find_all("form")
        links = soup.find_all("a")
        images = soup.find_all("img")

        test_id = 1

        # =========================
        # Page Load Test
        # =========================
        test_cases.append({
            "id": test_id,
            "description": "Verify homepage loads successfully"
        })
        test_id += 1

        # =========================
        # Button Tests
        # =========================
        for button in buttons[:5]:   # limit to 5
            test_cases.append({
                "id": test_id,
                "description": "Verify button is clickable"
            })
            test_id += 1

        # =========================
        # Input Field Tests
        # =========================
        for input_field in inputs[:5]:
            test_cases.append({
                "id": test_id,
                "description": "Verify input field accepts user input"
            })
            test_id += 1

        # =========================
        # Form Tests
        # =========================
        for form in forms[:3]:
            test_cases.append({
                "id": test_id,
                "description": "Verify form submission works"
            })
            test_id += 1

        # =========================
        # Link Tests
        # =========================
        for link in links[:5]:
            test_cases.append({
                "id": test_id,
                "description": "Verify navigation link works"
            })
            test_id += 1

        # =========================
        # Image Tests
        # =========================
        for image in images[:5]:
            test_cases.append({
                "id": test_id,
                "description": "Verify image loads correctly"
            })
            test_id += 1

    except Exception:

        # fallback test
        test_cases.append({
            "id": 1,
            "description": "Verify website is reachable"
        })

    return test_cases