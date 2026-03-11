// =============================================
// TestPilot QA — Frontend Logic
// =============================================

var recentTests = JSON.parse(localStorage.getItem("testpilot_recent") || "[]")

// ---- Init ----
document.addEventListener("DOMContentLoaded", function() {
    renderRecentTests()
})

// ---- Run Tests ----
async function runTests() {
    var urlInput = document.getElementById("urlInput")
    var url = urlInput.value.trim()
    var btn = document.getElementById("runBtn")

    if (!url) {
        urlInput.focus()
        urlInput.style.borderColor = "#EF4444"
        setTimeout(function(){ urlInput.style.borderColor = "" }, 1500)
        return
    }

    // Ensure URL has protocol
    if (!url.startsWith("http://") && !url.startsWith("https://")) {
        url = "https://" + url
        urlInput.value = url
    }

    // Show loading
    showSection("loadingSection")
    hideSection("resultsSection")
    btn.disabled = true
    btn.textContent = "Testing..."

    // Animate loading steps
    animateLoadingSteps()

    try {
        var response = await fetch("/run-tests", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: url })
        })

        var text = await response.text()
        var data

        try {
            data = JSON.parse(text)
        } catch(e) {
            showError("Server returned invalid response")
            return
        }

        // Save to recent
        saveRecent(url, data)

        // Render results
        renderResults(data)

    } catch(error) {
        showError("Connection failed: " + error.message)
    } finally {
        btn.disabled = false
        btn.textContent = "Run Test"
        hideSection("loadingSection")
    }
}

// ---- Loading Animation ----
function animateLoadingSteps() {
    var steps = document.querySelectorAll(".loading-steps li")
    var delays = [0, 2000, 5000, 10000]

    steps.forEach(function(step, i) {
        step.className = ""
        setTimeout(function() {
            // Mark previous as done
            for (var j = 0; j < i; j++) {
                steps[j].className = "done"
                steps[j].querySelector(".step-icon").textContent = "✓"
            }
            step.className = "active"
            step.querySelector(".step-icon").textContent = "●"
        }, delays[i])
    })
}

// ---- Render Results ----
function renderResults(data) {
    showSection("resultsSection")

    // Report header with website name
    var testedUrl = document.getElementById("urlInput").value
    var hostname = testedUrl.replace(/^https?:\/\//, "").replace(/\/.*$/, "")
    var now = new Date().toLocaleString()
    document.getElementById("reportHeader").innerHTML =
        '<h2>QA Report — ' + hostname + '</h2>' +
        '<div class="report-url">' + testedUrl + '</div>' +
        '<div class="report-timestamp">Generated on ' + now + '</div>'

    // Summary cards
    document.getElementById("totalCount").textContent = data.total_tests || 0
    document.getElementById("passedCount").textContent = data.passed || 0
    document.getElementById("failedCount").textContent = data.failed || 0
    document.getElementById("timeCount").textContent = (data.execution_time || 0) + "s"

    // Test results list
    var listEl = document.getElementById("testList")
    listEl.innerHTML = ""

    if (data.details) {
        data.details.forEach(function(test) {
            var isAI = String(test.test_id).startsWith("TC_")
            var statusClass = test.status === "PASS" ? "pass" : test.status === "FAIL" ? "fail" : "skip"
            var icon = test.status === "PASS" ? "✓" : test.status === "FAIL" ? "✗" : "⚠"

            var reason = test.details || test.error || ""
            var screenshotHtml = ""
            if (test.screenshot) {
                screenshotHtml = '<div class="test-detail">📸 ' + test.screenshot + '</div>'
            }

            var aiBadge = isAI ? ' <span class="test-badge ai">AI</span>' : ""

            listEl.innerHTML += '<div class="test-row fade-in">' +
                '<div class="test-icon ' + statusClass + '">' + icon + '</div>' +
                '<div class="test-content">' +
                    '<div class="test-header">' +
                        '<span class="test-name">Test ' + test.test_id + '</span>' +
                        '<span class="test-badge ' + statusClass + '">' + test.status + '</span>' +
                        aiBadge +
                    '</div>' +
                    (reason ? '<div class="test-detail">' + reason + '</div>' : '') +
                    screenshotHtml +
                '</div>' +
            '</div>'
        })
    }

    // Screenshots
    renderScreenshots(data.details || [])

    // AI Test Cases
    var aiSection = document.getElementById("aiTestCasesSection")
    var aiList = document.getElementById("aiTestCasesList")
    aiList.innerHTML = ""

    if (data.ai_test_cases && data.ai_test_cases.length > 0) {
        aiSection.classList.remove("hidden")
        data.ai_test_cases.forEach(function(tc) {
            aiList.innerHTML += '<div class="ai-card fade-in">' +
                '<div class="ai-card-title">' + tc.test_id + ' — ' + tc.test_name + '</div>' +
                '<div class="ai-card-body">' +
                    '<em>Description:</em> ' + tc.description + '<br>' +
                    '<em>Expected:</em> ' + tc.expected_result +
                '</div>' +
            '</div>'
        })
    } else {
        aiSection.classList.add("hidden")
    }

    // AI Failure Analysis
    var analysisSection = document.getElementById("aiAnalysisSection")
    var analysisList = document.getElementById("aiAnalysisList")
    analysisList.innerHTML = ""

    if (data.ai_failure_analysis && data.ai_failure_analysis.length > 0) {
        analysisSection.classList.remove("hidden")
        data.ai_failure_analysis.forEach(function(a) {
            var isFailure = a.failure && a.failure !== "None"
            var cls = isFailure ? "ai-card failure" : "ai-card"

            analysisList.innerHTML += '<div class="' + cls + ' fade-in">' +
                '<div class="ai-card-title">Test: ' + a.test_id + '</div>' +
                '<div class="ai-card-body">' +
                    '<em>Failure:</em> ' + a.failure + '<br>' +
                    '<em>Explanation:</em> ' + a.explanation + '<br>' +
                    '<em>Possible Cause:</em> ' + a.possible_cause + '<br>' +
                    '<em>Recommendation:</em> ' + a.recommendation +
                '</div>' +
            '</div>'
        })
    } else {
        analysisSection.classList.add("hidden")
    }

    // Scroll to results
    document.getElementById("resultsSection").scrollIntoView({ behavior: "smooth", block: "start" })
}

// ---- Screenshots ----
function renderScreenshots(details) {
    var section = document.getElementById("screenshotSection")
    var grid = document.getElementById("screenshotGrid")
    grid.innerHTML = ""

    var screenshots = details.filter(function(t) { return t.screenshot && t.screenshot !== "Screenshot failed" })

    if (screenshots.length > 0) {
        section.classList.remove("hidden")
        screenshots.forEach(function(t) {
            grid.innerHTML += '<div class="screenshot-card fade-in">' +
                '<img src="/static/' + t.screenshot + '" alt="Screenshot" onerror="this.style.display=\'none\'">' +
                '<div class="screenshot-info">' +
                    '<div class="test-name">Test ' + t.test_id + '</div>' +
                    '<div class="test-detail">' + (t.details || t.error || "Failed") + '</div>' +
                '</div>' +
            '</div>'
        })
    } else {
        section.classList.add("hidden")
    }
}

// ---- Recent Tests ----
function saveRecent(url, data) {
    var entry = {
        url: url,
        total: data.total_tests || 0,
        passed: data.passed || 0,
        failed: data.failed || 0,
        time: new Date().toLocaleString()
    }

    // Remove duplicate
    recentTests = recentTests.filter(function(r) { return r.url !== url })
    recentTests.unshift(entry)
    recentTests = recentTests.slice(0, 10)

    localStorage.setItem("testpilot_recent", JSON.stringify(recentTests))
    renderRecentTests()
}

function renderRecentTests() {
    var section = document.getElementById("recentSection")
    var list = document.getElementById("recentList")
    list.innerHTML = ""

    if (recentTests.length === 0) {
        section.classList.add("hidden")
        return
    }

    section.classList.remove("hidden")

    recentTests.forEach(function(r) {
        var hasFail = r.failed > 0
        var badgeClass = hasFail ? "fail" : "pass"
        var badgeText = hasFail ? r.failed + " failed" : "All passed"

        list.innerHTML += '<div class="recent-item" onclick="rerunTest(\'' + r.url + '\')">' +
            '<span class="recent-url">' + r.url + '</span>' +
            '<div class="recent-meta">' +
                '<span>' + r.total + ' tests</span>' +
                '<span class="recent-badge ' + badgeClass + '">' + badgeText + '</span>' +
                '<span>' + r.time + '</span>' +
            '</div>' +
        '</div>'
    })
}

function rerunTest(url) {
    document.getElementById("urlInput").value = url
    runTests()
}

// ---- Helpers ----
function showSection(id) {
    document.getElementById(id).classList.remove("hidden")
}

function hideSection(id) {
    document.getElementById(id).classList.add("hidden")
}

function showError(msg) {
    hideSection("loadingSection")
    showSection("resultsSection")
    document.getElementById("totalCount").textContent = "0"
    document.getElementById("passedCount").textContent = "0"
    document.getElementById("failedCount").textContent = "0"
    document.getElementById("timeCount").textContent = "—"
    document.getElementById("testList").innerHTML =
        '<div class="test-row"><div class="test-icon fail">✗</div>' +
        '<div class="test-content"><div class="test-name">Error</div>' +
        '<div class="test-detail">' + msg + '</div></div></div>'
}

// ---- Keyboard shortcut ----
document.addEventListener("keydown", function(e) {
    if (e.key === "Enter" && document.activeElement.id === "urlInput") {
        e.preventDefault()
        runTests()
    }
})