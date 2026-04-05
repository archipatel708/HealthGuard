/* app.js — HealthGuard Frontend with Auth, ABHA & Data Persistence */

(function () {
  "use strict";

  // ── API CONFIG ──────────────────────────────────────────────────────────────
  const API_BASE = "/api";
  let accessToken = localStorage.getItem("accessToken");
  let refreshToken = localStorage.getItem("refreshToken");
  let currentUser = null;

  // ── STATE ───────────────────────────────────────────────────────────────────
  let interpretedSymptoms = [];

  // ── DOM REFS ────────────────────────────────────────────────────────────────
  // Auth
  const loginSection = document.getElementById("loginSection");
  const appSection = document.getElementById("appSection");
  const emailInput = document.getElementById("emailInput");
  const requestOtpBtn = document.getElementById("requestOtpBtn");
  const otpSection = document.getElementById("otpSection");
  const otpInput = document.getElementById("otpInput");
  const verifyOtpBtn = document.getElementById("verifyOtpBtn");
  const resendOtpBtn = document.getElementById("resendOtpBtn");

  // App
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  // Prediction
  const symptomNarrative = document.getElementById("symptomNarrative");
  const predictionGenderInputs = document.querySelectorAll('input[name="predictionGender"]');
  const interpretedSymptomsWrap = document.getElementById("interpretedSymptomsWrap");
  const interpretedChips = document.getElementById("interpretedChips");
  const predictBtn = document.getElementById("predictBtn");
  const clearNarrativeBtn = document.getElementById("clearNarrativeBtn");
  const resultSection = document.getElementById("resultSection");
  const diseaseName = document.getElementById("diseaseName");
  const diseaseDesc = document.getElementById("diseaseDescription");
  const precautionsList = document.getElementById("precautionsList");
  const top3Container = document.getElementById("top3Container");
  const confidenceScore = document.getElementById("confidenceScore");

  // Health data
  const bloodPressure = document.getElementById("bloodPressure");
  const temperature = document.getElementById("temperature");
  const heartRate = document.getElementById("heartRate");

  // Profile
  const firstName = document.getElementById("firstName");
  const lastName = document.getElementById("lastName");
  const age = document.getElementById("age");
  const gender = document.getElementById("gender");
  const phone = document.getElementById("phone");
  const updateProfileBtn = document.getElementById("updateProfileBtn");
  const healthRecordsList = document.getElementById("healthRecordsList");

  // History
  const historyTableBody = document.getElementById("historyTableBody");
  const historyEmptyState = document.getElementById("historyEmptyState");

  // ABHA
  const linkAbhaBtn = document.getElementById("linkAbhaBtn");
  const unlinkAbhaBtn = document.getElementById("unlinkAbhaBtn");
  const abhaStatusText = document.getElementById("abhaStatusText");
  const abhaStatus = document.getElementById("abhaStatus");
  const abhaDataSection = document.getElementById("abhaDataSection");
  const abhaData = document.getElementById("abhaData");
  const abhaRequestType = document.getElementById("abhaRequestType");
  const abhaMobileGroup = document.getElementById("abhaMobileGroup");
  const abhaHealthIdGroup = document.getElementById("abhaHealthIdGroup");
  const abhaMobileInput = document.getElementById("abhaMobileInput");
  const abhaHealthIdInput = document.getElementById("abhaHealthIdInput");
  const abhaRequestBtn = document.getElementById("abhaRequestBtn");
  const abhaRequestOutput = document.getElementById("abhaRequestOutput");

  // Global
  const loader = document.getElementById("loader");
  const errorBox = document.getElementById("errorBox");
  const profileBtn = document.getElementById("profileBtn");
  const historyBtn = document.getElementById("historyBtn");
  const logoutBtn = document.getElementById("logoutBtn");
  const navMenu = document.getElementById("navMenu");
  const terminalLog = document.getElementById("terminalLog");

  // ── INIT ────────────────────────────────────────────────────────────────────
  function init() {
    logSystem("Client boot sequence started", "info");
    if (accessToken) {
      showApp();
      loadProfile();
      logSystem("Session token found, loading workspace", "success");
    } else {
      showLogin();
      logSystem("No active session, waiting for OTP login", "info");
    }

    setupEventListeners();
  }

  function setupEventListeners() {
    // Auth
    requestOtpBtn.addEventListener("click", handleRequestOtp);
    verifyOtpBtn.addEventListener("click", handleVerifyOtp);
    resendOtpBtn.addEventListener("click", handleRequestOtp);

    // Tabs
    tabBtns.forEach(btn => {
      btn.addEventListener("click", (e) => switchTab(e.target.dataset.tab));
    });

    // Prediction
    predictBtn.addEventListener("click", handlePredict);
    clearNarrativeBtn.addEventListener("click", handleClearSymptoms);

    // Profile
    updateProfileBtn.addEventListener("click", handleUpdateProfile);

    // ABHA
    linkAbhaBtn.addEventListener("click", handleLinkAbha);
    unlinkAbhaBtn.addEventListener("click", handleUnlinkAbha);
    abhaRequestBtn.addEventListener("click", handleAbhaRequest);
    abhaRequestType.addEventListener("change", handleAbhaRequestTypeChange);

    // Global
    if (profileBtn) {
      profileBtn.addEventListener("click", () => switchTab("profile"));
    }
    if (historyBtn) {
      historyBtn.addEventListener("click", () => switchTab("history"));
    }
    logoutBtn.addEventListener("click", handleLogout);
  }

  // ╔════════════════════════════════════════════════════════════════════════════╗
  // ║                    AUTHENTICATION FLOW                                     ║
  // ╚════════════════════════════════════════════════════════════════════════════╝

  async function handleRequestOtp() {
    const email = emailInput.value.trim().toLowerCase();
    
    if (!email || !email.includes("@")) {
      showError("Please enter a valid email address");
      return;
    }

    setButtonLoading(requestOtpBtn, true, "Sending OTP...");
    showLoader(true);
    showError("Requesting OTP...", "info");
    logSystem("OTP request initiated", "info");
    try {
      const res = await fetch(`${API_BASE}/auth/request-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email })
      });

      const data = await safeParseJson(res);
      showLoader(false);

      if (!res.ok) {
        showError(data.error || "Failed to request OTP");
        return;
      }

      showError(""); // Clear errors
      otpSection.classList.remove("hidden");
      otpInput.focus();
      showError(data.message || "OTP sent successfully", "success");
      logSystem("OTP dispatched successfully", "success");
    } catch (err) {
      showLoader(false);
      showError("Network error: " + err.message);
      logSystem("OTP request failed", "error");
    } finally {
      setButtonLoading(requestOtpBtn, false, "Request OTP");
    }
  }

  async function handleVerifyOtp() {
    const email = emailInput.value.trim().toLowerCase();
    const otp = otpInput.value.trim();

    if (!otp || otp.length !== 6) {
      showError("Please enter a valid 6-digit OTP");
      return;
    }

    setButtonLoading(verifyOtpBtn, true, "Verifying...");
    showLoader(true);
    showError("Verifying OTP...", "info");
    logSystem("OTP verification started", "info");
    try {
      const res = await fetch(`${API_BASE}/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, otp })
      });

      const data = await safeParseJson(res);
      showLoader(false);

      if (!res.ok) {
        showError(data.error || "Invalid OTP");
        return;
      }

      // Store tokens
      accessToken = data.access_token;
      refreshToken = data.refresh_token;
      currentUser = data.user;

      localStorage.setItem("accessToken", accessToken);
      localStorage.setItem("refreshToken", refreshToken);
      localStorage.setItem("currentUser", JSON.stringify(currentUser));

      showError("Login successful", "success");
      showApp();
      loadProfile();
      logSystem("Authentication successful", "success");
    } catch (err) {
      showLoader(false);
      showError("Network error: " + err.message);
      logSystem("Authentication failed", "error");
    } finally {
      setButtonLoading(verifyOtpBtn, false, "Verify OTP");
    }
  }

  function handleLogout() {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("currentUser");
    
    accessToken = null;
    refreshToken = null;
    currentUser = null;

    emailInput.value = "";
    otpInput.value = "";
    otpSection.classList.add("hidden");

    showLogin();
    logSystem("Session terminated", "info");
  }

  // ╔════════════════════════════════════════════════════════════════════════════╗
  // ║                    PREDICTION FLOW                                         ║
  // ╚════════════════════════════════════════════════════════════════════════════╝

  function renderInterpretedSymptoms() {
    interpretedChips.innerHTML = "";
    if (!interpretedSymptoms.length) {
      interpretedSymptomsWrap.classList.add("hidden");
      return;
    }

    interpretedSymptomsWrap.classList.remove("hidden");
    interpretedSymptoms.forEach(symptom => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.innerHTML = `<span>${escapeHtml(symptom.replace(/_/g, " "))}</span>`;
      interpretedChips.appendChild(chip);
    });
  }

  function handleClearSymptoms() {
    symptomNarrative.value = "";
    interpretedSymptoms = [];
    renderInterpretedSymptoms();
    resultSection.classList.add("hidden");
    logSystem("Symptom narrative cleared", "info");
  }

  async function handlePredict() {
    const profileGender = (currentUser?.gender || "").toUpperCase();
    const predictionGender = getSelectedPredictionGender() || profileGender;
    if (!["M", "F"].includes(predictionGender)) {
      showError("Please select prediction gender (Male/Female) or update your profile gender.");
      logSystem("Prediction blocked: gender input missing", "error");
      return;
    }

    const symptomText = symptomNarrative.value.trim();
    if (!symptomText) {
      showError("Please describe your symptoms before prediction");
      return;
    }

    const healthData = {};
    if (bloodPressure.value) healthData.blood_pressure = bloodPressure.value;
    if (temperature.value) healthData.temperature = parseFloat(temperature.value);
    if (heartRate.value) healthData.heart_rate = parseInt(heartRate.value);

    showLoader(true);
    logSystem("Prediction request queued", "info");
    try {
      const res = await apiFetch(`${API_BASE}/predict`, {
        method: "POST",
        body: JSON.stringify({
          prediction_gender: predictionGender,
          symptom_text: symptomText,
          health_data: Object.keys(healthData).length > 0 ? healthData : null
        })
      });

      const payload = await safeParseJson(res);
      if (!res.ok) {
        throw new Error(extractErrorMessage(payload, "Prediction failed"));
      }

      const data = payload;
      showLoader(false);

      displayPrediction(data);
      logSystem(`Prediction completed: ${data.disease || "unknown"}`, "success");
    } catch (err) {
      showLoader(false);
      showError("Prediction error: " + err.message);
      logSystem("Prediction failed", "error");
    }
  }

  function displayPrediction(data) {
    interpretedSymptoms = data.symptoms_used || [];
    renderInterpretedSymptoms();

    diseaseName.textContent = data.disease;
    diseaseDesc.textContent = data.description;
    const aiReview = data.ai_review || {};
    const aiLabel = aiReview.used ? " (AI-reviewed)" : "";
    confidenceScore.textContent = `Confidence: ${data.confidence_score}%${aiLabel}`;

    if (aiReview.used && aiReview.rationale) {
      diseaseDesc.textContent = `${data.description}\n\nAI Review: ${aiReview.rationale}`;
    }

    precautionsList.innerHTML = "";
    (data.precautions || []).forEach(prec => {
      const li = document.createElement("li");
      li.textContent = prec;
      precautionsList.appendChild(li);
    });

    top3Container.innerHTML = "";
    (data.top3 || []).forEach(pred => {
      const div = document.createElement("div");
      div.className = "top3-item";
      div.innerHTML = `
        <div class="top3-disease">${escapeHtml(pred.disease)}</div>
        <div class="top3-bar">
          <div class="top3-fill" style="width: ${pred.probability}%"></div>
        </div>
        <div class="top3-percentage">${pred.probability}%</div>
      `;
      top3Container.appendChild(div);
    });

    resultSection.classList.remove("hidden");
    resultSection.scrollIntoView({ behavior: "smooth" });
  }

  // ╔════════════════════════════════════════════════════════════════════════════╗
  // ║                    USER PROFILE MANAGEMENT                                 ║
  // ╚════════════════════════════════════════════════════════════════════════════╝

  async function loadProfile() {
    try {
      const res = await apiFetch(`${API_BASE}/user/profile`);
      if (!res.ok) throw new Error("Failed to load profile");
      const user = await res.json();
      currentUser = user;

      firstName.value = user.first_name || "";
      lastName.value = user.last_name || "";
      age.value = user.age || "";
      gender.value = user.gender || "";
      phone.value = user.phone || "";
      syncPredictionGenderFromProfile(user.gender);

      await loadHealthRecords();
      updateAbhaStatus(user);
    } catch (err) {
      console.error("Error loading profile:", err);
    }
  }

  async function handleUpdateProfile() {
    const profileData = {
      first_name: firstName.value,
      last_name: lastName.value,
      age: age.value ? parseInt(age.value) : null,
      gender: gender.value,
      phone: phone.value
    };

    showLoader(true);
    try {
      const res = await apiFetch(`${API_BASE}/user/profile`, {
        method: "PUT",
        body: JSON.stringify(profileData)
      });

      if (!res.ok) throw new Error("Failed to update profile");
      showLoader(false);
      showError("Profile updated successfully!", "success");
      await loadProfile();
      logSystem("Profile update persisted", "success");
    } catch (err) {
      showLoader(false);
      showError("Update error: " + err.message);
      logSystem("Profile update failed", "error");
    }
  }

  async function loadHealthRecords() {
    try {
      const res = await apiFetch(`${API_BASE}/user/health-records`);
      if (!res.ok) throw new Error("Failed to load health records");
      const data = await res.json();

      healthRecordsList.innerHTML = "";
      if (data.records && data.records.length > 0) {
        data.records.forEach(record => {
          const pastIssues = Array.isArray(record.past_illnesses) ? record.past_illnesses : [];
          const pastIssueSummary = pastIssues.length
            ? pastIssues
                .map(item => {
                  if (item && typeof item === "object") return item.condition || item.details;
                  return item;
                })
                .filter(Boolean)
                .join(", ")
            : "N/A";

          const div = document.createElement("div");
          div.className = "health-record-item";
          div.innerHTML = `
            <p><strong>Date:</strong> ${new Date(record.created_at).toLocaleDateString()}</p>
            <p><strong>BP:</strong> ${record.blood_pressure || "N/A"}</p>
            <p><strong>Temp:</strong> ${record.temperature || "N/A"}°C</p>
            <p><strong>HR:</strong> ${record.heart_rate || "N/A"} bpm</p>
            <p><strong>Past Issues:</strong> ${escapeHtml(pastIssueSummary)}</p>
          `;
          healthRecordsList.appendChild(div);
        });
      } else {
        healthRecordsList.innerHTML = "<p style='color: #999;'>No health records yet</p>";
      }
    } catch (err) {
      console.error("Error loading health records:", err);
    }
  }

  // ╔════════════════════════════════════════════════════════════════════════════╗
  // ║                    PREDICTION HISTORY                                      ║
  // ╚════════════════════════════════════════════════════════════════════════════╝

  async function loadPredictionHistory() {
    try {
      const res = await apiFetch(`${API_BASE}/predictions/history?limit=20`);
      if (!res.ok) throw new Error("Failed to load history");
      const data = await res.json();

      historyTableBody.innerHTML = "";
      if (data.predictions && data.predictions.length > 0) {
        historyEmptyState.classList.add("hidden");
        data.predictions.forEach(pred => {
          const row = document.createElement("tr");
          row.innerHTML = `
            <td>${new Date(pred.created_at).toLocaleDateString()}</td>
            <td class="history-disease">${escapeHtml(pred.predicted_disease)}</td>
            <td>${pred.confidence_score}%</td>
            <td class="history-symptoms">${escapeHtml((pred.symptoms || []).join(", "))}</td>
          `;
          historyTableBody.appendChild(row);
        });
      } else {
        historyEmptyState.classList.remove("hidden");
      }
    } catch (err) {
      console.error("Error loading history:", err);
      showError("Failed to load history");
    }
  }

  // ╔════════════════════════════════════════════════════════════════════════════╗
  // ║                    ABHA INTEGRATION                                        ║
  // ╚════════════════════════════════════════════════════════════════════════════╝

  function updateAbhaStatus(user) {
    if (user.abha_id) {
      abhaStatusText.textContent = `Linked: ${user.abha_id}`;
      linkAbhaBtn.classList.add("hidden");
      unlinkAbhaBtn.classList.remove("hidden");
    } else {
      abhaStatusText.textContent = "Not linked";
      linkAbhaBtn.classList.remove("hidden");
      unlinkAbhaBtn.classList.add("hidden");
    }
  }

  async function handleLinkAbha() {
    showLoader(true);
    try {
      const res = await apiFetch(`${API_BASE}/abha/link-dummy`, {
        method: "POST"
      });
      if (!res.ok) {
        const payload = await safeParseJson(res);
        throw new Error(extractErrorMessage(payload, "Failed to link dummy ABHA data"));
      }
      const data = await res.json();

      abhaDataSection.classList.remove("hidden");
      abhaData.textContent = JSON.stringify({
        abha_id: data.abha_id,
        past_illnesses: data.past_illnesses
      }, null, 2);

      showError("Dummy ABHA data linked and imported", "success");
      logSystem("Dummy ABHA history imported for prediction context", "success");
      await loadProfile();
      showLoader(false);
    } catch (err) {
      showLoader(false);
      showError("ABHA linking error: " + err.message);
      logSystem("Dummy ABHA link failed", "error");
    }
  }

  async function handleUnlinkAbha() {
    if (!confirm("Are you sure you want to unlink your ABHA account?")) return;

    showLoader(true);
    try {
      const res = await apiFetch(`${API_BASE}/abha/unlink`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to unlink ABHA");
      showLoader(false);
      showError("ABHA account unlinked", "success");
      await loadProfile();
    } catch (err) {
      showLoader(false);
      showError("Unlink error: " + err.message);
    }
  }

  function handleAbhaRequestTypeChange() {
    const mode = abhaRequestType.value;
    abhaMobileGroup.classList.toggle("hidden", mode !== "mobile");
    abhaHealthIdGroup.classList.toggle("hidden", mode !== "health_id");
  }

  async function handleAbhaRequest() {
    const mode = abhaRequestType.value;
    let operation = "";
    let payload = {};

    if (mode === "mobile") {
      const rawMobile = abhaMobileInput.value.trim();
      const digitsOnly = rawMobile.replace(/\D/g, "");
      if (!digitsOnly || digitsOnly.length < 10) {
        showError("Please enter a valid mobile number (at least 10 digits)");
        return;
      }

      // Send a normalized mobile value; backend will try compatible variants.
      const mobile = digitsOnly.length > 10 ? digitsOnly.slice(-10) : digitsOnly;
      operation = "forgot.health_id.mobile.generate_otp";
      payload = { mobile };
    } else if (mode === "health_id") {
      const healthId = abhaHealthIdInput.value.trim();
      if (!healthId) {
        showError("Please enter a health ID / ABHA address");
        return;
      }
      operation = "search.by_health_id";
      payload = { healthId };
    } else {
      operation = "account.profile.get";
      payload = {};
    }

    setButtonLoading(abhaRequestBtn, true, "Requesting...");
    showLoader(true);
    try {
      const res = await apiFetch(`${API_BASE}/abha/execute`, {
        method: "POST",
        body: JSON.stringify({ operation, payload })
      });

      const data = await safeParseJson(res);
      if (!res.ok) {
        throw new Error(extractErrorMessage(data, `ABHA request failed (${res.status})`));
      }

      abhaRequestOutput.textContent = JSON.stringify(data, null, 2);
      showError("ABHA request completed", "success");
      logSystem(`ABHA operation succeeded: ${operation}`, "success");
    } catch (err) {
      showError("ABHA request error: " + err.message);
      abhaRequestOutput.textContent = `Error: ${err.message}`;
      logSystem(`ABHA operation failed: ${operation || "unknown"}`, "error");
    } finally {
      showLoader(false);
      setButtonLoading(abhaRequestBtn, false, "Request via ABHA API");
    }
  }

  // ╔════════════════════════════════════════════════════════════════════════════╗
  // ║                    UI HELPERS                                              ║
  // ╚════════════════════════════════════════════════════════════════════════════╝

  function showLogin() {
    loginSection.classList.remove("hidden");
    appSection.classList.add("hidden");
    navMenu.style.display = "none";
  }

  function showApp() {
    loginSection.classList.add("hidden");
    appSection.classList.remove("hidden");
    navMenu.style.display = "flex";
  }

  function switchTab(tabName) {
    tabBtns.forEach(btn => btn.classList.remove("active"));
    tabContents.forEach(content => {
      content.classList.remove("active");
      content.classList.add("hidden");
    });

    document.querySelector(`[data-tab="${tabName}"]`).classList.add("active");
    const activeTabContent = document.getElementById(`${tabName}Tab`);
    activeTabContent.classList.remove("hidden");
    activeTabContent.classList.add("active");

    if (tabName === "history") loadPredictionHistory();
    if (tabName === "profile") loadProfile();
    if (tabName === "abha") handleAbhaRequestTypeChange();
  }

  function showLoader(show) {
    loader.classList.toggle("hidden", !show);
  }

  function showError(msg, type = "error") {
    errorBox.textContent = msg;
    errorBox.className = `error-box ${type === "success" ? "success" : type === "info" ? "info" : ""}`;
    errorBox.classList.toggle("hidden", !msg);

    if (msg) {
      setTimeout(() => showError(""), 3000);
    }
  }

  function setButtonLoading(button, isLoading, loadingText) {
    if (!button) return;
    if (!button.dataset.defaultLabel) {
      button.dataset.defaultLabel = button.textContent;
    }
    button.disabled = isLoading;
    button.textContent = isLoading ? loadingText : button.dataset.defaultLabel;
  }

  function getSelectedPredictionGender() {
    const selectedInput = Array.from(predictionGenderInputs).find(input => input.checked);
    return selectedInput ? String(selectedInput.value).toUpperCase() : "";
  }

  function syncPredictionGenderFromProfile(profileGender) {
    const normalized = String(profileGender || "").trim().toUpperCase();
    if (!["M", "F"].includes(normalized)) {
      return;
    }

    predictionGenderInputs.forEach(input => {
      input.checked = String(input.value).toUpperCase() === normalized;
    });
  }

  function logSystem(message, level = "info") {
    if (!terminalLog) return;

    const line = document.createElement("p");
    line.className = "terminal-line";

    const stamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    let prefix = "SYSTEM";
    if (level === "success") prefix = "OK";
    if (level === "error") prefix = "ERR";

    line.textContent = `[${stamp}] [${prefix}] ${message}`;
    terminalLog.appendChild(line);

    while (terminalLog.children.length > 12) {
      terminalLog.removeChild(terminalLog.firstChild);
    }
    terminalLog.scrollTop = terminalLog.scrollHeight;
  }

  async function safeParseJson(response) {
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      return {};
    }
    try {
      return await response.json();
    } catch {
      return {};
    }
  }

  function extractErrorMessage(payload, fallback = "Request failed") {
    if (!payload) return fallback;
    if (typeof payload === "string") return payload;

    // Surface structured LLM gating details from /api/predict 503 responses.
    if (payload.ai_review && typeof payload.ai_review === "object") {
      const reason = typeof payload.ai_review.reason === "string" ? payload.ai_review.reason : "";
      const base = typeof payload.error === "string" ? payload.error : fallback;
      if (reason) {
        return `${base} (${reason})`;
      }
    }

    if (payload.required_action === "configure_or_enable_llm") {
      const base = typeof payload.error === "string" ? payload.error : fallback;
      const confidence = Number(payload.confidence_score);
      const threshold = Number(payload.force_llm_threshold);
      if (!Number.isNaN(confidence) && !Number.isNaN(threshold)) {
        return `${base} (confidence ${confidence}% is below forced LLM threshold ${threshold}%)`;
      }
      return base;
    }

    const primary = payload.error || payload.message;
    if (typeof primary === "string") return primary;

    // For nested API errors (e.g., { error: { status_code, response } }).
    if (primary && typeof primary === "object") {
      if (typeof primary.response === "string") return primary.response;
      if (primary.response && typeof primary.response === "object") {
        return JSON.stringify(primary.response);
      }
      return JSON.stringify(primary);
    }

    try {
      return JSON.stringify(payload);
    } catch {
      return fallback;
    }
  }

  function escapeHtml(text) {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return text.replace(/[&<>"']/g, m => map[m]);
  }

  // ╔════════════════════════════════════════════════════════════════════════════╗
  // ║                    API HELPER WITH TOKEN REFRESH                           ║
  // ╚════════════════════════════════════════════════════════════════════════════╝

  async function apiFetch(url, options = {}) {
    const headers = options.headers || {};
    headers["Content-Type"] = "application/json";

    if (accessToken) {
      headers["Authorization"] = `Bearer ${accessToken}`;
    }

    let response = await fetch(url, { ...options, headers });

    // If token is invalid/expired, try refreshing token.
    if ((response.status === 401 || response.status === 422) && refreshToken) {
      try {
        const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${refreshToken}`
          }
        });

        if (refreshRes.ok) {
          const data = await refreshRes.json();
          accessToken = data.access_token;
          localStorage.setItem("accessToken", accessToken);

          // Retry original request
          headers["Authorization"] = `Bearer ${accessToken}`;
          response = await fetch(url, { ...options, headers });
        } else {
          handleLogout();
        }
      } catch (err) {
        handleLogout();
      }
    }

    return response;
  }

  // ── BOOT ────────────────────────────────────────────────────────────────────
  init();
})();
