/* dashboard_student.js
   Handles:
   - Join modal
   - Loading attendance summary (Chart.js)
   - Loading classes summary (API)
   - Ripple/bubble animation on class cards (originates from click point)
   - Fetching class details from Flask API with optional Firestore fallback
*/

document.addEventListener("DOMContentLoaded", () => {
  console.log("Student Dashboard JS Loaded");

  // Elements
  const joinBtn = document.getElementById("join-class-btn");
  const modalBg = document.getElementById("modal-bg");
  const cancelJoin = document.getElementById("cancel-join");
  const confirmJoin = document.getElementById("confirm-join");
  const classCodeInput = document.getElementById("class-code-input");
  const sectionSelect = document.getElementById("class-section-select");
  const classesContainer = document.getElementById("classes-cards");
  const detailPanel = document.getElementById("class-detail-content");
  const toastEl = createToastElement();

  function exists(el){ return el !== null && typeof el !== "undefined"; }

  // ------------------------
  // Join modal controls
  // ------------------------
  if (exists(joinBtn)) {
    joinBtn.addEventListener("click", () => {
      modalBg.classList.add("active");
      modalBg.style.display = "flex";
      classCodeInput.focus();
    });
  }

  function closeModal() {
    modalBg.classList.remove("active");
    modalBg.style.display = "none";
    classCodeInput.value = "";
    sectionSelect.innerHTML = `<option value="">Select a section…</option>`;
  }

  if (exists(cancelJoin)) {
    cancelJoin.addEventListener("click", closeModal);
  }

  if (exists(modalBg)) {
    modalBg.addEventListener("click", (ev) => {
      if (ev.target === modalBg) closeModal();
    });
  }

  // ------------------------
  // Auto-load sections for join modal via API
  // ------------------------
  if (exists(classCodeInput)) {
    let lastQuery = "";
    classCodeInput.addEventListener("input", async () => {
      const code = classCodeInput.value.trim().toUpperCase();
      if (!code || code === lastQuery) return;
      lastQuery = code;

      try {
        const res = await fetch(`/api/class/${encodeURIComponent(code)}/sections`);
        if (!res.ok) throw new Error("No sections");
        const data = await res.json();
        sectionSelect.innerHTML = `<option value="">Select a section…</option>`;
        (data.sections || []).forEach(sec => {
          const opt = document.createElement("option");
          opt.value = sec;
          opt.textContent = sec;
          sectionSelect.appendChild(opt);
        });
      } catch (err) {
        sectionSelect.innerHTML = `<option value="">No sections found</option>`;
      }
    });
  }

  // ------------------------
  // Confirm join action
  // ------------------------
  if (exists(confirmJoin)) {
    confirmJoin.addEventListener("click", async () => {
      const classCode = classCodeInput.value.trim().toUpperCase();
      const section = sectionSelect.value.trim();
      if (!classCode || !section) {
        showToast("Please enter class code and select a section.", 3000);
        return;
      }

      const formData = new FormData();
      formData.append("action", "join_class");
      formData.append("class_code", classCode);
      formData.append("section", section);

      try {
        const res = await fetch("/dashboard", { method: 'POST', body: formData });
        if (!res.ok) throw new Error("Join failed");
        showToast("Successfully requested to join. Reloading…", 1800);
        setTimeout(() => window.location.reload(), 900);
      } catch (err) {
        console.error(err);
        showToast("Unable to join class. Please try again.", 3000);
      }
    });
  }

  // ------------------------
  // Attendance summary (Chart)
  // ------------------------
  async function loadAttendanceSummary() {
    const canvas = document.getElementById("attendanceChart");
    if (!exists(canvas)) return;

    try {
      const res = await fetch("/api/student/attendance-summary");
      if (!res.ok) throw new Error("Attendance summary fetch failed");
      const data = await res.json();

      new Chart(canvas, {
        type: "doughnut",
        data: {
          labels: ["Present", "Absent", "Excused"],
          datasets: [{
            data: [data.present || 0, data.absent || 0, data.excused || 0]
          }]
        },
        options: { responsive: true, maintainAspectRatio: false }
      });

      document.getElementById("attendance-stats").innerHTML = `
        <div class="stat-item">Present: ${data.present || 0}</div>
        <div class="stat-item">Absent: ${data.absent || 0}</div>
        <div class="stat-item">Excused: ${data.excused || 0}</div>
      `;
    } catch (err) {
      console.error(err);
      document.getElementById("attendance-stats").innerHTML = `<p class="muted">Unable to load attendance summary.</p>`;
    }
  }

  loadAttendanceSummary();

  // ------------------------
  // Load joined classes (cards)
  // ------------------------
  async function loadClassesSummary() {
    if (!exists(classesContainer)) return;
    classesContainer.innerHTML = `
      <div class="skeleton-card"></div>
      <div class="skeleton-card"></div>
      <div class="skeleton-card"></div>
    `;

    try {
      const res = await fetch("/api/student/joined-classes-summary");
      if (!res.ok) throw new Error("Joined classes fetch failed");
      const classes = await res.json();

      if (!Array.isArray(classes) || classes.length === 0) {
        classesContainer.innerHTML = `<p class="muted no-classes">You haven't joined any classes yet.</p>`;
        return;
      }

      classesContainer.innerHTML = classes.map(c => `
        <div class="class-card"
             data-class-id="${escapeHtml(c.class_code || c.class_id || '')}"
             data-class-name="${escapeHtml(c.subjectName || c.class_name || '')}"
             data-section="${escapeHtml(c.section || '')}"
             data-teacher="${escapeHtml(c.teacher_name || '')}">
          <div class="card-top">
            <div>
              <div class="subject">${escapeHtml(c.subjectName || c.class_name || '')}</div>
              <div class="section">${escapeHtml(c.section || '')}</div>
            </div>
            <div class="stat">T: ${escapeHtml(c.teacher_name || '')}</div>
          </div>
          <div class="card-bottom">
            <p class="muted small">Click to view details</p>
          </div>
        </div>
      `).join("");

      attachClassCardClick();
    } catch (err) {
      console.error(err);
      classesContainer.innerHTML = `<p class="muted">Unable to load classes.</p>`;
    }
  }

  loadClassesSummary();

  // ------------------------
  // Ripple helper
  // ------------------------
  function createRipple(card, clientX, clientY) {
    // remove old ripples
    const old = card.querySelector(".ripple");
    if (old) old.remove();

    const rect = card.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2;
    const ripple = document.createElement("span");
    ripple.className = "ripple";
    ripple.style.width = ripple.style.height = `${size}px`;

    // position center on click
    const left = clientX - rect.left - size / 2;
    const top = clientY - rect.top - size / 2;
    ripple.style.left = `${left}px`;
    ripple.style.top = `${top}px`;
    ripple.style.opacity = "0.95";
    ripple.style.transform = "scale(0)";

    card.appendChild(ripple);

    // start animation (scale up)
    requestAnimationFrame(() => {
      ripple.style.transform = "scale(1)";
      ripple.style.opacity = "0.0";
    });

    // cleanup after animation
    setTimeout(() => {
      ripple.remove();
    }, 600);
  }

  // ------------------------
  // Attach click handlers to class cards (ripple + fetch details)
  // ------------------------
  function attachClassCardClick() {
    const cards = document.querySelectorAll(".class-card");
    cards.forEach(card => {
      // guard: avoid adding twice
      if (card.__listenerAdded) return;
      card.__listenerAdded = true;

      card.addEventListener("click", async (ev) => {
        const clientX = ev.clientX || (ev.touches && ev.touches[0] && ev.touches[0].clientX) || (card.getBoundingClientRect().left + card.offsetWidth/2);
        const clientY = ev.clientY || (ev.touches && ev.touches[0] && ev.touches[0].clientY) || (card.getBoundingClientRect().top + card.offsetHeight/2);

        createRipple(card, clientX, clientY);

        // read dataset
        const classCode = card.dataset.classId;
        const section = card.dataset.section;
        const teacher = card.dataset.teacher || "";

        // skeleton loading state
        detailPanel.innerHTML = `
          <p class="muted">Loading class details…</p>
          <div class="skeleton-item" style="height:18px; margin-top:6px;"></div>
          <div class="skeleton-item" style="height:18px; margin-top:6px;"></div>
          <div class="skeleton-item" style="height:18px; margin-top:6px;"></div>
        `;

        // attempt fetch from Flask API first
        try {
          const res = await fetch(`/api/student/class-details/${encodeURIComponent(classCode)}/${encodeURIComponent(section)}`);
          if (!res.ok) throw new Error("API fetch failed");
          const info = await res.json();
          renderClassDetails(info, teacher);
          return;
        } catch (err) {
          console.warn("API fetch failed, attempting Firestore fallback if available.", err);
        }

        // If FIREBASE_CONFIG is defined globally, try Firestore fallback
        if (window.FIREBASE_CONFIG) {
          try {
            if (!window.firebaseAppInitialized) {
              await initFirebaseSdk(window.FIREBASE_CONFIG);
              window.firebaseAppInitialized = true;
            }
            // generic Firestore layout: collection 'classes' -> doc classCode
            const firestore = window.firebase.firestore();
            const docRef = firestore.collection("classes").doc(classCode);
            const snap = await docRef.get();
            if (!snap.exists) throw new Error("Class not found in Firestore");
            const payload = snap.data();

            // derive section data if available
            const info = {
              classCode: classCode,
              subjectName: payload.subjectName || payload.name || "",
              section: section,
              teacher: payload.teacher || teacher,
              attendance: []
            };

            // if there is an 'attendance' field organized by section
            if (payload.attendance && payload.attendance[section]) {
              info.attendance = payload.attendance[section];
            } else if (payload.attendance) {
              // try to read attendance entries array
              if (Array.isArray(payload.attendance)) info.attendance = payload.attendance;
            }

            renderClassDetails(info, teacher);
            return;
          } catch (err) {
            console.error("Firestore fallback failed:", err);
            detailPanel.innerHTML = `<p class="muted">Unable to load class details at this time.</p>`;
          }
        } else {
          // no firebase config and API failed
          detailPanel.innerHTML = `<p class="muted">Unable to load class details at this time.</p>`;
        }
      });
    });
  }

  // render details into the right panel
  function renderClassDetails(info = {}, teacher = "") {
    const attendance = Array.isArray(info.attendance) ? info.attendance : (info.attendanceRecords || []);
    const attendanceHtml = attendance.length > 0 ? attendance.map(a => `<li>${escapeHtml(a.date || a.day || a.key || '')} – ${escapeHtml((a.records && a.records.length) || a.count || 0)} checked</li>`).join("") : "<p class='muted'>No attendance records yet.</p>";

    detailPanel.innerHTML = `
      <h4>${escapeHtml(info.subjectName || info.classCode || '')} ${info.classCode ? `(${escapeHtml(info.classCode)})` : ''}</h4>
      <p class="muted">Section: ${escapeHtml(info.section || '')}</p>
      ${ teacher ? `<p class="muted">Teacher: ${escapeHtml(teacher)}</p>` : '' }

      <h5>Attendance Records</h5>
      <ul>${attendanceHtml}</ul>
    `;
  }

  // ------------------------
  // Utilities
  // ------------------------
  function escapeHtml(str) {
    if (typeof str !== "string") return "";
    return str.replace(/[&<>"']/g, m => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' })[m]);
  }

  function createToastElement(){
    const t = document.createElement("div");
    t.className = "toast";
    document.body.appendChild(t);
    return t;
  }

  function showToast(msg, ms = 2500){
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    setTimeout(()=> toastEl.classList.remove("show"), ms);
  }

  // ------------------------
  // Optional: Firebase SDK loader (if FIREBASE_CONFIG provided)
  // ------------------------
  async function initFirebaseSdk(config) {
    return new Promise((resolve, reject) => {
      if (window.firebase && window.firebase.apps && window.firebase.apps.length) {
        // firebase already loaded
        resolve();
        return;
      }

      // Dynamically add scripts
      const scripts = [
        "https://www.gstatic.com/firebasejs/9.22.0/firebase-app-compat.js",
        "https://www.gstatic.com/firebasejs/9.22.0/firebase-firestore-compat.js",
      ];

      let loaded = 0;
      scripts.forEach(src => {
        const s = document.createElement("script");
        s.src = src;
        s.onload = () => {
          loaded++;
          if (loaded === scripts.length) {
            try {
              window.firebase.initializeApp(config);
              resolve();
            } catch (err) {
              reject(err);
            }
          }
        };
        s.onerror = (e) => reject(e);
        document.head.appendChild(s);
      });
    });
  }

});
