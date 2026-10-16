"""Every end-to-end proof fixture must certify complete optimization equivalence."""
def assert_rules_checked(test, report):
    test.assertEqual(report.get("status"), "VERIFIED", report)
    if "parts" in report:
        for part in report["parts"]:
            assert_rules_checked(test, part)
    else:
        test.assertEqual(report.get("guarantee"), "MI_OPT", report)
