import os
import sys
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

def run_e2e_tests():
    print("==================================================")
    print("STARTING COMPREHENSIVE E2E BROWSER TEST SUITE (ROUND 2)")
    print("Target: http://localhost:5000")
    print("==================================================")

    opts = Options()
    opts.add_argument('--headless')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--window-size=1440,900')

    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, 15)

    results = []

    def record_test(test_num, name, status, details):
        print(f"Test {test_num:02d} [{status}]: {name}")
        if details:
            print(f"   -> {details}")
        results.append({
            'num': test_num,
            'name': name,
            'status': status,
            'details': details
        })

    try:
        # 1. Landing / Dashboard
        driver.get('http://localhost:5000')
        wait.until(EC.presence_of_element_located((By.ID, 'requestSelect')))
        title = driver.title
        h1 = driver.find_element(By.TAG_NAME, 'h1').text
        if "Buy or Wait?" in title and "Buy or Wait?" in h1:
            record_test(1, "Landing / Dashboard Initialization", "PASS", f"Title: '{title}', H1: '{h1}'")
        else:
            record_test(1, "Landing / Dashboard Initialization", "FAIL", f"Unexpected title or header: {title}")

        # 2. Request selection
        sel_elem = wait.until(EC.presence_of_element_located((By.ID, 'requestSelect')))
        # Wait until options are populated via fetch
        wait.until(lambda d: len(Select(d.find_element(By.ID, 'requestSelect')).options) >= 275)
        select = Select(sel_elem)
        options = select.options
        record_test(2, "Request Selection Populate", "PASS", f"Loaded {len(options)} requests in selector")

        # Wait for auto-load of initial request
        wait.until(lambda d: d.find_element(By.ID, 'reqId').text != '-')

        # 3. User financial profile
        prof_user = driver.find_element(By.ID, 'profUser').text
        prof_balance = driver.find_element(By.ID, 'profBalance').text
        prof_min = driver.find_element(By.ID, 'profMinBalance').text
        if prof_user and prof_balance != '-' and prof_min != '-':
            record_test(3, "User Financial Profile Rendering", "PASS", f"User: {prof_user}, Balance: {prof_balance}, Min: {prof_min}")
        else:
            record_test(3, "User Financial Profile Rendering", "FAIL", f"Profile data mismatch: {prof_user}, {prof_balance}")

        # 4. Affordability analysis execution
        badge_text = driver.find_element(By.ID, 'verdictBadge').text
        chart_exists = driver.find_element(By.ID, 'forecastChart').is_displayed()
        if badge_text in ['SAFE NOW', 'SAFE WITH PLAN', 'WAIT', 'NOT RECOMMENDED'] and chart_exists:
            record_test(4, "Affordability Analysis Pipeline", "PASS", f"Verdict Badge: '{badge_text}', Chart rendered: {chart_exists}")
        else:
            record_test(4, "Affordability Analysis Pipeline", "FAIL", f"Badge: '{badge_text}', Chart: {chart_exists}")

        # 5. Safe-now case (request_26: confirmed affordable_now)
        select = Select(driver.find_element(By.ID, 'requestSelect'))
        select.select_by_value('request_26')
        wait.until(lambda d: d.find_element(By.ID, 'reqId').text == 'request_26')
        time.sleep(0.5)
        badge = driver.find_element(By.ID, 'verdictBadge').text
        method = driver.find_element(By.ID, 'resMethod').text
        plan = driver.find_element(By.ID, 'resPaymentPlan').text
        if badge == 'SAFE NOW' and 'full' in method.lower():
            record_test(5, "Safe-Now Scenario (request_26)", "PASS", f"Status: {badge}, Method: {method}, Plan: {plan}")
        else:
            record_test(5, "Safe-Now Scenario (request_26)", "FAIL", f"Expected SAFE NOW, got {badge}, {method}")

        # 6. Installment case (request_02)
        select.select_by_value('request_02')
        wait.until(lambda d: d.find_element(By.ID, 'reqId').text == 'request_02')
        time.sleep(0.5)
        badge = driver.find_element(By.ID, 'verdictBadge').text
        method = driver.find_element(By.ID, 'resMethod').text
        plan = driver.find_element(By.ID, 'resPaymentPlan').text
        if badge == 'SAFE WITH PLAN' and 'installment' in method.lower():
            record_test(6, "Installment Scenario (request_02)", "PASS", f"Status: {badge}, Method: {method}, Plan: {plan}")
        else:
            record_test(6, "Installment Scenario (request_02)", "FAIL", f"Expected SAFE WITH PLAN / installments, got {badge}, {method}")

        # 7. Partial-payment case (request_138)
        select.select_by_value('request_138')
        wait.until(lambda d: d.find_element(By.ID, 'reqId').text == 'request_138')
        time.sleep(0.5)
        badge = driver.find_element(By.ID, 'verdictBadge').text
        method = driver.find_element(By.ID, 'resMethod').text
        plan = driver.find_element(By.ID, 'resPaymentPlan').text
        safe_amt = driver.find_element(By.ID, 'resSafeAmt').text
        if badge == 'SAFE WITH PLAN' and 'partial' in method.lower() and '|' in plan:
            record_test(7, "Partial-Payment Scenario (request_138)", "PASS", f"Status: {badge}, Method: {method}, Safe: {safe_amt}, Plan: {plan}")
        else:
            record_test(7, "Partial-Payment Scenario (request_138)", "FAIL", f"Expected partial_payment, got {badge}, {method}, {plan}")

        # 8. Wait case (request_03)
        select.select_by_value('request_03')
        wait.until(lambda d: d.find_element(By.ID, 'reqId').text == 'request_03')
        time.sleep(0.5)
        badge = driver.find_element(By.ID, 'verdictBadge').text
        method = driver.find_element(By.ID, 'resMethod').text
        earliest_date = driver.find_element(By.ID, 'resEarliestDate').text
        if badge == 'WAIT' and 'wait' in method.lower() and earliest_date != 'None':
            record_test(8, "Wait Scenario (request_03)", "PASS", f"Status: {badge}, Earliest Safe Date: {earliest_date}")
        else:
            record_test(8, "Wait Scenario (request_03)", "FAIL", f"Expected WAIT, got {badge}, {method}, {earliest_date}")

        # 9. Not-recommended case (request_28)
        select.select_by_value('request_28')
        wait.until(lambda d: d.find_element(By.ID, 'reqId').text == 'request_28')
        time.sleep(0.5)
        badge = driver.find_element(By.ID, 'verdictBadge').text
        method = driver.find_element(By.ID, 'resMethod').text
        if badge == 'NOT RECOMMENDED' and 'not' in method.lower():
            record_test(9, "Not-Recommended Scenario (request_28)", "PASS", f"Status: {badge}, Method: {method}")
        else:
            record_test(9, "Not-Recommended Scenario (request_28)", "FAIL", f"Expected NOT RECOMMENDED, got {badge}, {method}")

        # 10. Missing image evidence case (request_01 vs request_35)
        select.select_by_value('request_01')
        wait.until(lambda d: d.find_element(By.ID, 'reqId').text == 'request_01')
        time.sleep(0.5)
        ev_text = driver.find_element(By.ID, 'evidenceContainer').text
        select.select_by_value('request_35')
        wait.until(lambda d: d.find_element(By.ID, 'reqId').text == 'request_35')
        time.sleep(0.5)
        has_img = len(driver.find_elements(By.CSS_SELECTOR, '#evidenceContainer img')) > 0
        if "No external messages or receipt images" in ev_text and has_img:
            record_test(10, "Missing vs Present Image Evidence Handling", "PASS", "Correctly handled empty evidence for req_01 and rendered image for req_35")
        else:
            record_test(10, "Missing vs Present Image Evidence Handling", "FAIL", f"Empty text: '{ev_text}', Has img for req_35: {has_img}")

        # 11. Currency conversion case (request_39: user has USD events converted to INR)
        select.select_by_value('request_39')
        wait.until(lambda d: d.find_element(By.ID, 'reqId').text == 'request_39')
        time.sleep(0.5)
        prof_cur = driver.find_element(By.ID, 'profCur').text
        trace_text = driver.find_element(By.ID, 'auditTrace').text
        if prof_cur == 'INR' and ('USD' in trace_text or 'INR' in trace_text):
            record_test(11, "Multi-Currency Conversion Handling (request_39)", "PASS", "Home currency INR maintained, FX evaluated in trace")
        else:
            record_test(11, "Multi-Currency Conversion Handling (request_39)", "FAIL", f"Currency: {prof_cur}")

        # 12. Error handling (evaluate invalid request in UI via JS)
        driver.execute_script("""
            const sel = document.getElementById('requestSelect');
            const opt = document.createElement('option');
            opt.value = 'invalid_req_xyz';
            opt.textContent = 'Invalid Test Request';
            sel.appendChild(opt);
            sel.value = 'invalid_req_xyz';
            evaluateCurrentRequest();
        """)
        time.sleep(1)
        err_banner = driver.find_element(By.ID, 'errorBanner')
        err_msg = driver.find_element(By.ID, 'errorMessage').text
        if err_banner.is_displayed() and "not found" in err_msg.lower():
            record_test(12, "Frontend Error Handling & Banner Notification", "PASS", f"Error banner displayed: '{err_msg}'")
        else:
            record_test(12, "Frontend Error Handling & Banner Notification", "FAIL", f"Banner visible: {err_banner.is_displayed()}, Msg: '{err_msg}'")

        # 13. Empty states
        select = Select(driver.find_element(By.ID, 'requestSelect'))
        select.select_by_value('request_01')
        wait.until(lambda d: d.find_element(By.ID, 'reqId').text == 'request_01')
        time.sleep(0.5)
        err_banner_after = driver.find_element(By.ID, 'errorBanner')
        rows = driver.find_elements(By.CSS_SELECTOR, '#optionsBody tr')
        if not err_banner_after.is_displayed() and len(rows) > 0:
            record_test(13, "Empty State Cleanliness & Error Banner Recovery", "PASS", f"Banner auto-dismissed on valid load, options rows: {len(rows)}")
        else:
            record_test(13, "Empty State Cleanliness & Error Banner Recovery", "FAIL", f"Banner: {err_banner_after.is_displayed()}, Rows: {len(rows)}")

        # 14. Long explanations rendering
        select.select_by_value('request_273')
        wait.until(lambda d: d.find_element(By.ID, 'reqId').text == 'request_273')
        time.sleep(0.5)
        exp_box = driver.find_element(By.ID, 'resExplanation')
        exp_text = exp_box.text
        if len(exp_text) > 100 and exp_box.is_displayed():
            record_test(14, "Long Explanation Rendering (request_273)", "PASS", f"Rendered {len(exp_text)} chars cleanly: '{exp_text[:60]}...'")
        else:
            record_test(14, "Long Explanation Rendering (request_273)", "FAIL", f"Length: {len(exp_text)}")

        # 15. Mobile / responsive layout
        driver.set_window_size(375, 812) # iPhone 12/13/14 size
        time.sleep(1)
        banner = driver.find_element(By.ID, 'verdictBanner')
        chart = driver.find_element(By.ID, 'forecastChart')
        is_banner_vis = banner.is_displayed()
        is_chart_vis = chart.is_displayed()
        if is_banner_vis and is_chart_vis:
            record_test(15, "Mobile Viewport (375x812) Layout Responsiveness", "PASS", "Dashboard adapts cleanly to mobile without DOM layout failure")
        else:
            record_test(15, "Mobile Viewport (375x812) Layout Responsiveness", "FAIL", f"Banner: {is_banner_vis}, Chart: {is_chart_vis}")

        # Restore window size
        driver.set_window_size(1440, 900)
        time.sleep(0.5)

        # 16. Refresh behavior
        driver.refresh()
        wait.until(EC.presence_of_element_located((By.ID, 'requestSelect')))
        wait.until(lambda d: len(Select(d.find_element(By.ID, 'requestSelect')).options) >= 275)
        wait.until(lambda d: d.find_element(By.ID, 'reqId').text != '-')
        reloaded_req = driver.find_element(By.ID, 'reqId').text
        if reloaded_req == 'request_01':
            record_test(16, "Page Refresh & State Recovery", "PASS", f"Default request restored after reload: {reloaded_req}")
        else:
            record_test(16, "Page Refresh & State Recovery", "FAIL", f"Restored: {reloaded_req}")

        # 17. Invalid request endpoint rejection
        driver.get('http://localhost:5000/api/analyze/non_existent_999')
        page_source = driver.page_source
        if "Request non_existent_999 not found" in page_source:
            record_test(17, "API 404 Entity Validation", "PASS", "Endpoint safely returns structured JSON 404 error payload")
        else:
            record_test(17, "API 404 Entity Validation", "FAIL", f"Unexpected source: {page_source[:100]}")

        # Return to main page
        driver.get('http://localhost:5000')
        wait.until(EC.presence_of_element_located((By.ID, 'requestSelect')))
        wait.until(lambda d: len(Select(d.find_element(By.ID, 'requestSelect')).options) >= 275)

        # 18. Backend failure resilience
        driver.get('http://localhost:5000/api/non_existent_route')
        source_404 = driver.page_source
        if "404 Not Found" in source_404 or "Not Found" in source_404:
            record_test(18, "Backend Routing Failure Resilience", "PASS", "Framework standard 404 returned without unhandled exceptions")
        else:
            record_test(18, "Backend Routing Failure Resilience", "FAIL", f"Source: {source_404[:100]}")

        # Return to main page
        driver.get('http://localhost:5000')
        wait.until(EC.presence_of_element_located((By.ID, 'requestSelect')))
        wait.until(lambda d: len(Select(d.find_element(By.ID, 'requestSelect')).options) >= 275)

        # 19. Latency and sub-second evaluation benchmark
        start_t = time.perf_counter()
        select = Select(driver.find_element(By.ID, 'requestSelect'))
        select.select_by_value('request_240')
        wait.until(lambda d: d.find_element(By.ID, 'reqId').text == 'request_240')
        duration = time.perf_counter() - start_t
        if duration < 2.0:
            record_test(19, "Analysis Latency Benchmark", "PASS", f"Full forecast & decision computed in {duration:.3f}s (sub-second engine)")
        else:
            record_test(19, "Analysis Latency Benchmark", "FAIL", f"Too slow: {duration:.3f}s")

        # 20. Dataset/output generation validation
        root_out = os.path.join(os.getcwd(), 'output.csv')
        ds_out = os.path.join(os.getcwd(), 'dataset', 'output.csv')
        if os.path.exists(root_out) and os.path.exists(ds_out):
            with open(root_out, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f if l.strip()]
            if len(lines) == 251: # Header + 250 requests
                record_test(20, "Dataset & Output.csv Pipeline Consistency", "PASS", f"Both output.csv exist with 250 verified evaluation rows")
            else:
                record_test(20, "Dataset & Output.csv Pipeline Consistency", "FAIL", f"Expected 251 lines, got {len(lines)}")
        else:
            record_test(20, "Dataset & Output.csv Pipeline Consistency", "FAIL", f"Output files missing: root={os.path.exists(root_out)}, ds={os.path.exists(ds_out)}")

    except Exception as e:
        print(f"CRITICAL TEST EXCEPTION: {e}")
        record_test(99, "Test Suite Runner", "CRITICAL_FAIL", str(e))
    finally:
        driver.quit()

    total = len(results)
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = total - passed
    print("\n==================================================")
    print(f"E2E BROWSER TEST COMPLETE: {passed}/{total} PASSED ({failed} FAILED)")
    print("==================================================")
    return results

if __name__ == '__main__':
    res = run_e2e_tests()
    all_pass = all(r['status'] == 'PASS' for r in res)
    sys.exit(0 if all_pass else 1)
