function setBanner(targetId, message) {
  const node = document.getElementById(targetId);
  if (node) {
    node.textContent = message;
  }
}

async function jsonRequest(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    credentials: "include",
  });
  const raw = await res.text();
  let data = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch (_err) {
    data = {};
  }
  if (!res.ok) {
    throw new Error(data.error || data.message || `Request failed (${res.status})`);
  }
  return data;
}

function renderPrediction(data) {
  const diseaseNode = document.getElementById("predicted-disease");
  const confidenceNode = document.getElementById("predicted-confidence");
  const noteNode = document.getElementById("prediction-note");
  if (!diseaseNode || !confidenceNode || !noteNode) {
    return;
  }
  diseaseNode.textContent = data.disease || "Unknown";
  if (data.llm_used) {
    confidenceNode.textContent = "Confidence: AI - generated";
  } else {
    confidenceNode.textContent = `Confidence: ${data.confidence_label || `${data.confidence ?? "--"}%`}`;
  }
  noteNode.textContent = data.reasoning_note || "Model confidence is stable. No secondary reasoning needed.";
}

function renderHistory(history = []) {
  const list = document.getElementById("history-list");
  if (!list) {
    return;
  }
  if (!history.length) {
    list.textContent = "No predictions yet.";
    return;
  }
  list.innerHTML = history
    .map((item) => {
      const disease = item.prediction?.disease || "Unknown";
      return `<div class="history-item"><strong>${disease}</strong> (${item.confidence}%)\n${item.created_at}\nInput: ${item.input_text}</div>`;
    })
    .join("");
}

function renderAbha(records = []) {
  const box = document.getElementById("abha-records");
  if (!box) {
    return;
  }
  if (!records.length) {
    box.textContent = "No ABHA records linked.";
    return;
  }
  box.innerHTML = records
    .map(
      (record) =>
        `<div class="history-item"><strong>${record.condition}</strong>\n${record.record_id} | ${record.medication}\nLast visit: ${record.last_visit}</div>`
    )
    .join("");
}

function bindTabs() {
  const tabButtons = document.querySelectorAll(".tab-btn");
  const panels = document.querySelectorAll(".tab-panel");
  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const tab = button.dataset.tab;
      tabButtons.forEach((btn) => btn.classList.remove("active"));
      panels.forEach((panel) => panel.classList.remove("active"));
      button.classList.add("active");
      document.getElementById(`tab-${tab}`)?.classList.add("active");
    });
  });
}

async function loadProfile() {
  try {
    const me = await jsonRequest("/api/auth/me");
    document.getElementById("profile-name").value = me.user.name || "";
    document.getElementById("profile-email").value = me.user.email || "";
    document.getElementById("profile-phone").value = me.user.phone || "";
    const genderSelect = document.getElementById("profile-gender");
    if (genderSelect) {
      genderSelect.value = me.user.gender || "unspecified";
    }
  } catch (err) {
    setBanner("app-message", `Profile load failed: ${err.message}`);
  }
}

function bindAuthPage() {
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const showLoginBtn = document.getElementById("show-login-btn");
  const showRegisterBtn = document.getElementById("show-register-btn");
  const loginCard = document.getElementById("login-card");
  const registerCard = document.getElementById("register-card");

  function showAuthPane(mode) {
    if (!loginCard || !registerCard || !showLoginBtn || !showRegisterBtn) {
      return;
    }
    const loginMode = mode === "login";
    loginCard.classList.toggle("hidden", !loginMode);
    registerCard.classList.toggle("hidden", loginMode);
    showLoginBtn.classList.toggle("active", loginMode);
    showRegisterBtn.classList.toggle("active", !loginMode);
  }

  showLoginBtn?.addEventListener("click", () => showAuthPane("login"));
  showRegisterBtn?.addEventListener("click", () => showAuthPane("register"));

  loginForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    setBanner("auth-message", "Authenticating...");
    try {
      await jsonRequest("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setBanner("auth-message", "Login successful. Redirecting...");
      window.location.href = "/app";
    } catch (err) {
      setBanner("auth-message", `Login failed: ${err.message}`);
    }
  });

  registerForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = document.getElementById("register-name").value.trim();
    const email = document.getElementById("register-email").value.trim();
    const password = document.getElementById("register-password").value;
    setBanner("auth-message", "Creating account...");
    try {
      await jsonRequest("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ name, email, password }),
      });
      setBanner("auth-message", "Account created. Redirecting...");
      window.location.href = "/app";
    } catch (err) {
      setBanner("auth-message", `Registration failed: ${err.message}`);
    }
  });
}

function bindDashboardPage() {
  bindTabs();
  loadProfile();

  const predictBtn = document.getElementById("predict-btn");
  const abhaBtn = document.getElementById("abha-link-btn");
  const refreshHistoryBtn = document.getElementById("refresh-history-btn");
  const profileForm = document.getElementById("profile-form");
  const logoutBtn = document.getElementById("logout-btn");

  predictBtn?.addEventListener("click", async () => {
    const text = document.getElementById("symptom-text").value.trim();
    if (!text) {
      setBanner("app-message", "Enter symptoms before running prediction.");
      return;
    }
    predictBtn.disabled = true;
    setBanner("app-message", "Running prediction...");
    try {
      const data = await jsonRequest("/api/predict", {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      renderPrediction(data);
      setBanner("app-message", "Prediction completed.");
    } catch (err) {
      setBanner("app-message", `Prediction failed: ${err.message}`);
    } finally {
      predictBtn.disabled = false;
    }
  });

  refreshHistoryBtn?.addEventListener("click", async () => {
    setBanner("app-message", "Loading history...");
    try {
      const data = await jsonRequest("/api/history");
      renderHistory(data.history || []);
      setBanner("app-message", `Loaded ${data.history?.length || 0} records.`);
    } catch (err) {
      setBanner("app-message", `History load failed: ${err.message}`);
    }
  });

  abhaBtn?.addEventListener("click", async () => {
    setBanner("app-message", "Linking ABHA records...");
    try {
      const data = await jsonRequest("/api/abha/link", { method: "POST" });
      renderAbha(data.abha_records || []);
      setBanner("app-message", `ABHA linked successfully (${data.records_linked} records).`);
    } catch (err) {
      setBanner("app-message", `ABHA link failed: ${err.message}`);
    }
  });

  profileForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = document.getElementById("profile-name").value;
    const email = document.getElementById("profile-email").value;
    const phone = document.getElementById("profile-phone").value;
    const gender = document.getElementById("profile-gender")?.value || "unspecified";
    setBanner("app-message", "Updating profile...");
    try {
      await jsonRequest("/api/profile", {
        method: "PATCH",
        body: JSON.stringify({ name, email, phone, gender }),
      });
      setBanner("app-message", "Profile updated.");
    } catch (err) {
      setBanner("app-message", `Profile update failed: ${err.message}`);
    }
  });

  logoutBtn?.addEventListener("click", async () => {
    try {
      await jsonRequest("/api/auth/logout", { method: "POST" });
    } finally {
      window.location.href = "/";
    }
  });
}

if (document.getElementById("login-form")) {
  bindAuthPage();
}

if (document.querySelector(".tab-nav")) {
  bindDashboardPage();
}
