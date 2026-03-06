/* app.js — Frontend logic for Disease Predictor */

(function () {
  "use strict";

  // ── State ──────────────────────────────────────────────────────────────────
  let allSymptoms = [];          // [{ value, label }]
  let selected = new Set();      // set of symptom values (raw underscore form)

  // ── DOM refs ───────────────────────────────────────────────────────────────
  const searchInput     = document.getElementById("symptomSearch");
  const symptomList     = document.getElementById("symptomList");
  const chipContainer   = document.getElementById("selectedChips");
  const predictBtn      = document.getElementById("predictBtn");
  const clearBtn        = document.getElementById("clearBtn");
  const resultSection   = document.getElementById("resultSection");
  const loader          = document.getElementById("loader");
  const errorBox        = document.getElementById("errorBox");

  const diseaseName       = document.getElementById("diseaseName");
  const diseaseDesc       = document.getElementById("diseaseDescription");
  const precautionsList   = document.getElementById("precautionsList");
  const top3Container     = document.getElementById("top3Container");

  // ── Boot: load symptom list from API ──────────────────────────────────────
  async function loadSymptoms() {
    try {
      const res = await fetch("/api/symptoms");
      if (!res.ok) throw new Error("Failed to load symptoms.");
      allSymptoms = await res.json();
      renderDropdown("");
    } catch (err) {
      showError("Could not load symptoms from server: " + err.message);
    }
  }

  // ── Render dropdown ────────────────────────────────────────────────────────
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

  // ── Toggle symptom selection ───────────────────────────────────────────────
  function toggleSymptom(sym) {
    if (selected.has(sym.value)) {
      selected.delete(sym.value);
    } else {
      selected.add(sym.value);
    }
    renderChips();
    renderDropdown(searchInput.value);
    predictBtn.disabled = selected.size === 0;
    hideError();
    resultSection.classList.add("hidden");
  }

  // ── Render selected chips ─────────────────────────────────────────────────
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

  // ── Predict ────────────────────────────────────────────────────────────────
  async function predict() {
    if (selected.size === 0) return;

    hideError();
    resultSection.classList.add("hidden");
    loader.classList.remove("hidden");

    try {
      const res = await fetch("/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symptoms: Array.from(selected) }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || data.message || "Prediction failed.");
      }

      renderResult(data);
    } catch (err) {
      showError("Error: " + err.message);
    } finally {
      loader.classList.add("hidden");
    }
  }

  // ── Render result ──────────────────────────────────────────────────────────
  function renderResult(data) {
    // Disease + description
    diseaseName.textContent = data.disease;
    diseaseDesc.textContent = data.description;

    // Precautions
    precautionsList.innerHTML = "";
    (data.precautions || []).forEach(p => {
      const li = document.createElement("li");
      li.textContent = capitalise(p);
      precautionsList.appendChild(li);
    });
    if (!data.precautions || data.precautions.length === 0) {
      const li = document.createElement("li");
      li.textContent = "No specific precautions listed.";
      precautionsList.appendChild(li);
    }

    // Top-3 bar chart
    top3Container.innerHTML = "";
    (data.top3 || []).forEach(item => {
      const div = document.createElement("div");
      div.className = "top3-item";
      div.innerHTML = `
        <div class="top3-label">
          <span>${escapeHtml(item.disease)}</span>
          <span>${item.probability.toFixed(1)}%</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill" style="width: 0%"
               data-target="${item.probability}"></div>
        </div>`;
      top3Container.appendChild(div);
    });

    resultSection.classList.remove("hidden");
    resultSection.scrollIntoView({ behavior: "smooth", block: "start" });

    // Animate bars after paint
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.querySelectorAll(".bar-fill").forEach(bar => {
          bar.style.width = bar.dataset.target + "%";
        });
      });
    });
  }

  // ── Clear ──────────────────────────────────────────────────────────────────
  function clearAll() {
    selected.clear();
    renderChips();
    renderDropdown(searchInput.value);
    predictBtn.disabled = true;
    resultSection.classList.add("hidden");
    hideError();
    searchInput.value = "";
    renderDropdown("");
  }

  // ── Error helpers ──────────────────────────────────────────────────────────
  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.remove("hidden");
  }
  function hideError() {
    errorBox.classList.add("hidden");
  }

  // ── Utility ────────────────────────────────────────────────────────────────
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function capitalise(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  // ── Event listeners ────────────────────────────────────────────────────────
  searchInput.addEventListener("input", () => renderDropdown(searchInput.value));
  predictBtn.addEventListener("click", predict);
  clearBtn.addEventListener("click", clearAll);

  // Close dropdown when clicking outside
  document.addEventListener("click", e => {
    if (!symptomList.contains(e.target) && e.target !== searchInput) {
      if (searchInput.value === "" ) renderDropdown("");
    }
  });

  // Keyboard: Enter on search triggers predict
  searchInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && selected.size > 0) predict();
  });

  // ── Init ───────────────────────────────────────────────────────────────────
  loadSymptoms();
})();
