/* app.js — HealthGuard Frontend with Auth, ABHA & Data Persistence */

(function () {
  "use strict";

  // ── API CONFIG ──────────────────────────────────────────────────────────────
  const API_BASE = "/api";
  let accessToken = localStorage.getItem("accessToken");
  let refreshToken = localStorage.getItem("refreshToken");
  let currentUser = null;

  // ── STATE ───────────────────────────────────────────────────────────────────
  let allSymptoms = [];
  let selected = new Set();

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
  const searchInput = document.getElementById("symptomSearch");
  const symptomList = document.getElementById("symptomList");
  const chipContainer = document.getElementById("selectedChips");
  const predictBtn = document.getElementById("predictBtn");
  const clearBtn = document.getElementById("clearBtn");
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
  const logoutBtn = document.getElementById("logoutBtn");
  const navMenu = document.getElementById("navMenu");

  // ── INIT ────────────────────────────────────────────────────────────────────
  function init() {
    if (accessToken) {
      showApp();
      loadSymptoms();
      loadProfile();
    } else {
      showLogin();
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
    searchInput.addEventListener("input", (e) => renderDropdown(e.target.value));
    predictBtn.addEventListener("click", handlePredict);
    clearBtn.addEventListener("click", handleClearSymptoms);

    // Profile
    updateProfileBtn.addEventListener("click", handleUpdateProfile);

    // ABHA
    linkAbhaBtn.addEventListener("click", handleLinkAbha);
    unlinkAbhaBtn.addEventListener("click", handleUnlinkAbha);
    abhaRequestBtn.addEventListener("click", handleAbhaRequest);
    abhaRequestType.addEventListener("change", handleAbhaRequestTypeChange);

    // Global
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
    } catch (err) {
      showLoader(false);
      showError("Network error: " + err.message);
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
      loadSymptoms();
      loadProfile();
    } catch (err) {
      showLoader(false);
      showError("Network error: " + err.message);
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
  }

  // ╔════════════════════════════════════════════════════════════════════════════╗
  // ║                    PREDICTION FLOW                                         ║
  // ╚════════════════════════════════════════════════════════════════════════════╝

  async function loadSymptoms() {
    try {
      const res = await fetch(`${API_BASE}/symptoms`);
      if (!res.ok) throw new Error("Failed to load symptoms");
      allSymptoms = await res.json();
      renderDropdown("");
    } catch (err) {
      showError("Could not load symptoms: " + err.message);
    }
  }

  function renderDropdown(filter) {
    const q = filter.trim().toLowerCase();
    const filtered = q
      ? allSymptoms.filter(s =>
          s.label.toLowerCase().includes(q) || s.value.includes(q)
        )
      : allSymptoms;

    symptomList.innerHTML = "";

    filtered.slice(0, 80).forEach(sym => {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", selected.has(sym.value));
      if (selected.has(sym.value)) li.classList.add("selected");

      li.innerHTML =
        `<span class="check-icon">${selected.has(sym.value) ? "✔" : ""}</span>` +
        `<span>${escapeHtml(sym.label)}</span>`;

      li.addEventListener("click", () => toggleSymptom(sym));
      symptomList.appendChild(li);
    });

    if (filtered.length === 0) {
      const li = document.createElement("li");
      li.style.color = "var(--clr-muted)";
      li.style.cursor = "default";
      li.textContent = "No matching symptoms found.";
      symptomList.appendChild(li);
    }
  }

  function toggleSymptom(sym) {
    if (selected.has(sym.value)) {
      selected.delete(sym.value);
    } else {
      selected.add(sym.value);
    }
    renderChips();
    renderDropdown(searchInput.value);
    predictBtn.disabled = selected.size === 0;
    showError("");
    resultSection.classList.add("hidden");
  }

  function renderChips() {
    chipContainer.innerHTML = "";
    selected.forEach(val => {
      const sym = allSymptoms.find(s => s.value === val);
      const label = sym ? sym.label : val;

      const chip = document.createElement("span");
      chip.className = "chip";
      chip.setAttribute("title", "Click to remove");
      chip.innerHTML =
        `<span>${escapeHtml(label)}</span>` +
        `<span class="remove" aria-hidden="true">×</span>`;
      chip.addEventListener("click", () => toggleSymptom({ value: val }));
      chipContainer.appendChild(chip);
    });
  }

  function handleClearSymptoms() {
    selected.clear();
    renderChips();
    renderDropdown("");
    predictBtn.disabled = true;
    resultSection.classList.add("hidden");
  }

  async function handlePredict() {
    const symptoms = Array.from(selected);
    if (symptoms.length === 0) {
      showError("Please select at least one symptom");
      return;
    }

    const healthData = {};
    if (bloodPressure.value) healthData.blood_pressure = bloodPressure.value;
    if (temperature.value) healthData.temperature = parseFloat(temperature.value);
    if (heartRate.value) healthData.heart_rate = parseInt(heartRate.value);

    showLoader(true);
    try {
      const res = await apiFetch(`${API_BASE}/predict`, {
        method: "POST",
        body: JSON.stringify({
          symptoms,
          health_data: Object.keys(healthData).length > 0 ? healthData : null
        })
      });

      if (!res.ok) throw new Error("Prediction failed");
      const data = await res.json();
      showLoader(false);

      displayPrediction(data);
    } catch (err) {
      showLoader(false);
      showError("Prediction error: " + err.message);
    }
  }

  function displayPrediction(data) {
    diseaseName.textContent = data.disease;
    diseaseDesc.textContent = data.description;
    confidenceScore.textContent = `Confidence: ${data.confidence_score}%`;

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
    } catch (err) {
      showLoader(false);
      showError("Update error: " + err.message);
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
          const div = document.createElement("div");
          div.className = "health-record-item";
          div.innerHTML = `
            <p><strong>Date:</strong> ${new Date(record.created_at).toLocaleDateString()}</p>
            <p><strong>BP:</strong> ${record.blood_pressure || "N/A"}</p>
            <p><strong>Temp:</strong> ${record.temperature || "N/A"}°C</p>
            <p><strong>HR:</strong> ${record.heart_rate || "N/A"} bpm</p>
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
      const res = await apiFetch(`${API_BASE}/abha/authorization-url`);
      if (!res.ok) throw new Error("Failed to get auth URL");
      const data = await res.json();

      // In a real app, this would redirect to ABHA OAuth
      // For now, show a message
      showError("ABHA linking not fully configured. Please set ABHA_CLIENT_ID and ABHA_CLIENT_SECRET in .env file", "info");
      showLoader(false);
    } catch (err) {
      showLoader(false);
      showError("ABHA linking error: " + err.message);
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
    } catch (err) {
      showError("ABHA request error: " + err.message);
      abhaRequestOutput.textContent = `Error: ${err.message}`;
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
