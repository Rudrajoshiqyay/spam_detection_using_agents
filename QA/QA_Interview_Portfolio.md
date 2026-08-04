# QA Engineering Portfolio: FraudGuard AI

**Role Evaluated For:** QA Engineer  
**Project:** FraudGuard AI (Real-Time Financial Fraud Detection Platform)  
**Testing Scope:** Web Dashboards, API Endpoints (FastAPI), Database/Cache (PostgreSQL/Redis), Compliance Workflows  

---

## 1. Executive Summary
This document outlines the end-to-end Quality Assurance processes, testing methodologies, and bug-tracking workflows I implemented for **FraudGuard AI**. The objective was to ensure product stability, API reliability, and a seamless UI/UX across the analyst dashboard and investor workflows. 

I conducted **Functional, UI, Regression, API, and Security testing**, ultimately identifying and documenting 60+ bugs. To bridge the gap between QA and product management, I engineered a data pipeline to export bug metrics into **Tableau** for visual risk assessment.

---

## 2. Tools & Technologies Used
*   **Web Technologies Tested:** React, Vite, TailwindCSS (Frontend) | Python, FastAPI, LangGraph (Backend)
*   **Databases Tested:** Neon PostgreSQL, Upstash Redis
*   **QA & Collaboration Tools:** Tableau (Bug Visualization), Postman concepts (API Payload Validation), Markdown (Bug Documentation)
*   **Methodologies:** Manual Testing, Black-Box Testing, API Testing, Cross-Browser Compatibility, Mobile Responsiveness

---

## 3. Test Strategy & Execution

### A. API & Backend Testing
*   **Objective:** Verify that the FastAPI endpoints correctly handle payloads, rate limits, and authentication.
*   **Execution:** 
    *   Simulated `POST /detect` requests to ensure the AI pipeline correctly rejected missing fields.
    *   Tested JWT token validation and identified a clock-skew vulnerability where expired tokens were briefly accepted.
    *   Verified rate limiting; identified a vulnerability where spoofing the `X-Forwarded-For` header bypassed the global limit.

### B. UI & Cross-Browser Testing
*   **Objective:** Ensure the analyst dashboard renders correctly across Chrome, Firefox, Safari, and mobile viewports.
*   **Execution:** 
    *   Resized viewports to test responsiveness. Found that the layout breaks completely on screens `< 768px` (Mobile).
    *   Identified WebGL memory leaks when switching between the Network Graph tab and Timeline tab.
    *   Verified Safari-specific animation jitters on the pipeline node SVGs.

### C. Security & Vulnerability Testing
*   **Objective:** Identify common OWASP vulnerabilities in the web platform.
*   **Execution:** 
    *   Attempted SQL injection payloads in the "Custom Transaction City" input field.
    *   Tested for XSS vulnerabilities in the stream log by injecting HTML into the simulation engine.
    *   Checked Local Storage and identified that the `X-API-Key` was being stored in plaintext.

### D. Regression Testing
*   **Objective:** Ensure that bug fixes deployed in recent patches did not break existing functionality.
*   **Execution:** 
    *   Re-executed the entire suite of Custom Transaction tests after the backend risk engine was updated.
    *   Verified that patching the mobile layout issue did not unintentionally break the desktop grid alignment.
    *   Maintained a strict re-testing protocol for all "Resolved" bugs in the QA tracker before closing them.

---

## 4. Sample Test Cases Authored

| Test Case ID | Module | Description | Steps to Reproduce | Expected Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-01** | API | Validate Rate Limiting on `/detect` | 1. Send 50 concurrent requests to `/detect`. | API should return HTTP 429 after 30 requests. | ❌ FAILED (Bypassed via Headers) |
| **TC-02** | UI/UX | Dashboard Mobile Responsiveness | 1. Open dashboard. 2. Resize browser to 390px width. | Sidebar collapses into a hamburger menu; grid stacks vertically. | ❌ FAILED (Elements overlap) |
| **TC-03** | Security| Custom Transaction Input Sanitization | 1. Enter `'; DROP TABLE users;--` in City field. 2. Click Run. | Input is sanitized; system rejects or escapes characters. | ❌ FAILED (SQLi possible) |
| **TC-04** | Backend | Redis Offline Graceful Degradation | 1. Disconnect Upstash Redis. 2. Run simulation. | UI shows error toast: "Cache offline"; falls back to DB. | ❌ FAILED (UI spins indefinitely) |

---

## 5. Bug Reporting & Tableau Integration
To communicate product quality effectively to stakeholders, I created a structured bug-tracking pipeline:
1.  **Categorization:** Grouped bugs by Severity (Critical, Medium, Minor) and Domain (Security, UI/UX, Performance, API).
2.  **Documentation:** Documented expected vs. actual results, environment details, and risk assessments for developers.
3.  **Visualization:** Exported the audit data into two flat CSV files (`qa_audit_details.csv` and `qa_category_breakdown.csv`). 
4.  **Tableau Dashboard:** Imported the CSVs into Tableau to create interactive pie charts and bar graphs, allowing product managers to visually differentiate between backend API failures and frontend UI glitches.

---

## 6. Conclusion & Impact
By creating structured manual test scenarios and pushing the data into Tableau, I provided the development team with clear, actionable metrics on product stability. This audit directly highlighted critical API vulnerabilities and severe accessibility violations, providing a roadmap for the next sprint's bug fixes.
