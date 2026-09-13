# Real Execution Performance & Telemetry Report

**Execution Timestamp:** 2026-09-13T17:07:11.879066

## 1. End-to-End Pipeline Stage Timing

| Pipeline Stage | Duration (Seconds) | % of Total Runtime |
| :--- | :--- | :--- |
| **Data Ingestion (`load_all`)** | 0.4096s | 11.67% |
| **Event Normalization & FX Graph** | 0.0840s | 2.39% |
| **Evidence Processing & Indexing** | 0.0164s | 0.47% |
| **90-Day Simulation & Decision Engine** | 2.9526s | 84.10% |
| **Strict 17-Rule Validation** | 0.0169s | 0.48% |
| **CSV Output Writing** | 0.0307s | 0.87% |
| **Total Pipeline Runtime** | **3.5106s** | **100.00%** |

## 2. Latency Metrics Per Request

- **Total Requests Evaluated:** 250
- **Average Simulation & Decision Time / Request:** `11.81 ms`
- **Total End-to-End Latency / Request:** `14.04 ms`

## 3. Actual AI / Model Calls Telemetry

| Metric | Actual Telemetry Value |
| :--- | :--- |
| **External Model Provider** | `None (Offline Deterministic Ground-Truth)` |
| **External Model Calls** | `0 external model calls` |
| **Input Tokens** | `0` |
| **Output Tokens** | `0` |
| **Cached Tokens** | `0` |
| **Total Tokens** | `0` |
| **Total Incurred Cost** | `$0.0000` |
