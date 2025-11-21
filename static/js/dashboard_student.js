/* dashboard_student.js — improved UX, toasts, modal, chart, filtering, accessible */

document.addEventListener("DOMContentLoaded", () => {
  initElements();
  initSkeletonLoading();
  initModal();
  initNotifications();
  initClasses();
  initFilters();
  initAttendanceChart();
});

/* ------------------------- ELEMENTS ------------------------- */
let EL = {};
function initElements() {
  EL.joinBtn = document.getElementById("join-class-btn");
  EL.modalBg = document.getElementById("modal-bg");
  EL.cancelJoin = document.getElementById("cancel-join");
  EL.confirmJoin = document.getElementById("confirm-join");
  EL.classCodeInput = document.getElementById("class-code-input");
  EL.classSectionSelect = document.getElementById("class-section-select");
  EL.notificationsList = document.getElementById("notifications-list");
  EL.markReadBtn = document.getElementById("mark-read");
  EL.classesContainer = document.getElementById("classes-cards");
  EL.searchInput = document.getElementById("search-classes");
  EL.filterStatus = document.getElementById("filter-status");
  EL.sortSelect = document.getElementById("sort-classes");
  EL.classDetail = document.getElementById("class-detail-content");
  EL.attendanceCanvas = document.getElementById("attendanceChart");

  for (const k in EL) if (!EL[k]) EL[k] = null;
}

/* ------------------------- TOAST ------------------------- */
function showToast(msg, ms = 2200) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.setAttribute("role", "status");
  toast.setAttribute("aria-live", "polite");
  toast.innerText = msg;
  document.body.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("show"));
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 280);
  }, ms);
}

/* ------------------------- SKELETON → DATA ------------------------- */
function initSkeletonLoading() {
  setTimeout(() => {
    if (EL.notificationsList) {
      EL.notificationsList.innerHTML = "";
      // sample notifications
      const sample = [
        { id: 1, text: "Welcome! Your semester starts next week." },
        { id: 2, text: "Math quiz scheduled for Friday." }
      ];
      sample.forEach(n => {
        const item = document.createElement("div");
        item.className = "notification-item";
        item.innerText = n.text;
        EL.notificationsList.appendChild(item);
      });
    }

    if (EL.classesContainer) {
      EL.classesContainer.innerHTML = "";
      const sampleClasses = [
        { id: 1, subject: "CSE 402", section: "A", attendance: 87 },
        { id: 2, subject: "CSE 401", section: "B", attendance: 62 },
        { id: 3, subject: "MATH 408", section: "C", attendance: 74 }
      ];
      renderClassCards(sampleClasses);
      window._SAMPLE_CLASSES = sampleClasses;
    }
  }, 700);
}

/* ------------------------- MODAL/UI ------------------------- */
function initModal() {
  if (!EL.joinBtn || !EL.modalBg) return;

  EL.joinBtn.addEventListener("click", () => {
    EL.modalBg.classList.add("active");
    setTimeout(() => EL.classCodeInput?.focus(), 120);
  });

  function close() {
    EL.modalBg.classList.remove("active");
    if (EL.classCodeInput) {
      EL.classCodeInput.value = "";
      EL.classCodeInput.classList.remove("input-error");
    }
    if (EL.confirmJoin) {
      EL.confirmJoin.disabled = false;
      EL.confirmJoin.innerText = "Join";
    }
  }

  EL.cancelJoin?.addEventListener("click", close);
  EL.modalBg?.addEventListener("click", (e) => { if (e.target === EL.modalBg) close(); });

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
    if (e.key === "Enter" && document.activeElement === EL.classCodeInput) {
      e.preventDefault();
      handleJoinClass();
    }
  });

  EL.confirmJoin?.addEventListener("click", handleJoinClass);
}

/* ------------------------- FETCH CLASS SECTIONS ------------------------- */
async function fetchClassSections(code) {
  if (!code) return;

  try {
    const resp = await fetch(`/api/class/${code}/sections`);
    const data = await resp.json();

    EL.classSectionSelect.innerHTML = "";

    if (!data.sections || data.sections.length === 0) {
      EL.classSectionSelect.innerHTML =
        `<option value="">No sections found</option>`;
      return;
    }

    data.sections.forEach(sec => {
      const opt = document.createElement("option");
      opt.value = sec;
      opt.innerText = sec;
      EL.classSectionSelect.appendChild(opt);
    });

  } catch (err) {
    EL.classSectionSelect.innerHTML =
      `<option value="">Error loading</option>`;
  }
}

EL.classCodeInput?.addEventListener("input", () => {
  const code = EL.classCodeInput.value.trim().toUpperCase();
  fetchClassSections(code);
});

/* ------------------------- JOIN CLASS ------------------------- */
async function handleJoinClass() {
  if (!EL.classCodeInput) return;

  const code = EL.classCodeInput.value.trim();
  if (!code) {
    EL.classCodeInput.classList.add("input-error");
    showToast("Please enter the class code.");
    EL.classCodeInput.focus();
    return;
  }

  const section = EL.classSectionSelect.value;
  if (!section) {
    showToast("Please select a section.");
    return;
  }

  if (EL.confirmJoin) {
    EL.confirmJoin.disabled = true;
    EL.confirmJoin.innerText = "Joining…";
  }

  try {
    const resp = await fetch("/student/join_class", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ class_code: code, section })
    });

    let data;
    try { data = await resp.json(); } 
    catch { showToast("Server error. Try again."); return; }

    if (data.success) {
      showToast(data.message || "Joined class successfully!");
      if (window._SAMPLE_CLASSES && Array.isArray(window._SAMPLE_CLASSES)) {
        window._SAMPLE_CLASSES.push({ id: Date.now(), subject: `New Class ${code}`, section, attendance: 100 });
        renderClassCards(window._SAMPLE_CLASSES);
      }
      setTimeout(() => EL.modalBg.classList.remove("active"), 500);
    } else {
      showToast(data.message || "Could not join class.", 3000);
      EL.classCodeInput.classList.add("input-error");
    }
  } catch (err) {
    console.error(err);
    showToast("Network error. Try again.", 3000);
  } finally {
    if (EL.confirmJoin) {
      EL.confirmJoin.disabled = false;
      EL.confirmJoin.innerText = "Join";
    }
  }
}

/* ------------------------- NOTIFICATIONS ------------------------- */
function initNotifications() {
  EL.markReadBtn?.addEventListener("click", () => {
    EL.notificationsList?.querySelectorAll(".notification-item").forEach(n => n.style.opacity = "0.6");
    showToast("All notifications marked read");
  });
}

/* ------------------------- CLASSES RENDER & DETAIL ------------------------- */
function renderClassCards(classes = []) {
  if (!EL.classesContainer) return;
  EL.classesContainer.innerHTML = "";
  classes.forEach(c => {
    const card = document.createElement("div");
    card.className = "class-card";
    card.dataset.attendance = String(c.attendance);
    card.dataset.subject = c.subject;
    card.innerHTML = `
      <div class="card-top">
        <div>
          <div class="subject">${escapeHTML(c.subject)}</div>
          <div class="section">${escapeHTML(c.section)}</div>
        </div>
        <div class="stat">${c.attendance}%</div>
      </div>
      <div class="class-details">Click to open class details</div>
    `;
    card.addEventListener("click", () => showClassDetail(c));
    EL.classesContainer.appendChild(card);
  });
}

function showClassDetail(c) {
  if (!EL.classDetail) return;
  EL.classDetail.innerHTML = `
    <h4 style="margin-bottom:8px;color:var(--primary);">${escapeHTML(c.subject)} — Section ${escapeHTML(c.section)}</h4>
    <p><strong>Attendance:</strong> ${c.attendance}%</p>
    <p class="muted">Topics: Example topics will appear here.</p>
    <div style="margin-top:12px;display:flex;gap:8px;">
      <button class="action-btn primary" onclick="downloadReport('${escapeJS(c.subject)}')">Download Report</button>
      <button class="action-btn" onclick="showToast('Opening attendance calendar (demo)')">Open Calendar</button>
    </div>
  `;
}

function escapeHTML(str = "") {
  return String(str).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}
function escapeJS(s=""){ return String(s).replace(/'/g, "\\'"); }
function downloadReport(subject) { showToast(`Preparing ${subject} report...`); }

/* ------------------------- FILTERS ------------------------- */
function initFilters() {
  if (!EL.classesContainer) return;
  const handler = () => {
    const search = EL.searchInput?.value?.toLowerCase?.() || "";
    const status = EL.filterStatus?.value || "";
    const sort = EL.sortSelect?.value || "";

    const cards = Array.from(EL.classesContainer.querySelectorAll(".class-card"));
    let visible = cards.filter(card => {
      const subj = (card.dataset.subject || "").toLowerCase();
      const att = Number(card.dataset.attendance || 0);
      if (search && !subj.includes(search)) return false;
      if (status === "low-attendance" && att >= 60) return false;
      if (status === "high-absent" && att >= 50) return false;
      return true;
    });

    if (sort === "alpha") visible.sort((a,b) => a.dataset.subject.localeCompare(b.dataset.subject));
    if (sort === "most-absent") visible.sort((a,b) => Number(a.dataset.attendance) - Number(b.dataset.attendance));
    if (sort === "attendance-desc") visible.sort((a,b) => Number(b.dataset.attendance) - Number(a.dataset.attendance));

    EL.classesContainer.innerHTML = "";
    visible.forEach(n => EL.classesContainer.appendChild(n));
  };

  EL.searchInput?.addEventListener("input", handler);
  EL.filterStatus?.addEventListener("change", handler);
  EL.sortSelect?.addEventListener("change", handler);
}

/* ------------------------- CHART.JS ------------------------- */
let attendanceChart = null;
function initAttendanceChart() {
  if (!EL.attendanceCanvas) return;
  const sample = (window._SAMPLE_CLASSES && window._SAMPLE_CLASSES.length) ? window._SAMPLE_CLASSES : [
    { subject: "Mathematics", attendance: 87 },
    { subject: "Science", attendance: 62 },
    { subject: "History", attendance: 74 }
  ];

  const labels = sample.map(s => s.subject);
  const data = sample.map(s => s.attendance);

  const ctx = EL.attendanceCanvas.getContext("2d");
  attendanceChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Attendance %",
        data,
        backgroundColor: labels.map((_,i) => i % 2 === 0 ? "#8B0000" : "#d40000")
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero:true, max: 100 } }
    }
  });

  const stats = document.getElementById("attendance-stats");
  if (stats) {
    stats.innerHTML = sample.map(s => `<div class="stat-item">${escapeHTML(s.subject)}<br><strong>${String(s.attendance)}%</strong></div>`).join("");
  }
}

/* ------------------------- UTIL / EXPORTS ------------------------- */
window.showToast = showToast;
