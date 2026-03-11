def generate_report(results):

    total_tests = len(results)

    passed = sum(1 for r in results if r["status"] == "PASS")

    failed = total_tests - passed

    return {
        "total_tests": total_tests,
        "passed": passed,
        "failed": failed,
        "details": results
    }