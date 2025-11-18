document.addEventListener("DOMContentLoaded", () => {
  initNotifications();
  initClassCards();
  initFilters();
  initModal();
  initAttendanceChart();
});

/* ---------------- NOTIFICATIONS ---------------- */
function initNotifications() {
  const markReadBtn = document.getElementById("mark-read");
  const notificationsList = document.getElementById("notifications-list");

  markReadBtn?.addEventListener("click", () => {
    notificationsList.querySelectorAll(".notification-item").forEach(n => n.remove());
    showToast("All notifications marked as read");
  });

  // Example: dynamically add notification
  setTimeout(() => {
    notificationsList.innerHTML = `
      <div class="notification-item">Math class updated.</div>
      <div class="notification-item">Science project deadline approaching.</div>
    `;
  }, 800);
}

/* ---------------- CLASS CARDS ---------------- */
function initClassCards() {
  const cardsContainer = document.getElementById("classes-cards");
  const classDetail = document.getElementById("class-detail-content");

  // Example classes
  const classes = [
    { subject: "Math", section: "A", attendance: "78%" },
    { subject: "Science", section: "B", attendance: "65%" },
    { subject: "History", section: "C", attendance: "92%" },
  ];

  cardsContainer.innerHTML = classes.map(c => `
    <div class="class-card" data-subject="${c.subject}" data-section="${c.section}" data-attendance="${c.attendance}">
      <div class="card-header">
        <span class="subject">${c.subject}</span>
        <span class="section">${c.section}</span>
      </div>
      <div class="stat">${c.attendance} attendance</div>
    </div>
  `).join("");

  cardsContainer.querySelectorAll(".class-card").forEach(card => {
    card.addEventListener("click", () => {
      const subject = card.dataset.subject;
      const section = card.dataset.section;
      const attendance = card.dataset.attendance;

      classDetail.innerHTML = `
        <p><strong>${subject} - Section ${section}</strong></p>
        <p>Attendance: ${attendance}</p>
        <p>Topics covered, calendar, and download report here...</p>
      `;
    });
  });
}

/* ---------------- FILTERS ---------------- */
function initFilters() {
  const searchInput = document.getElementById("search-classes");
  const statusFilter = document.getElementById("filter-status");
  const sortFilter = document.getElementById("sort-classes");
  const cardsContainer = document.getElementById("classes-cards");

  function filterAndSort() {
    const search = searchInput.value.toLowerCase();
    const status = statusFilter.value;
    const sort = sortFilter.value;

    const cards = Array.from(cardsContainer.querySelectorAll(".class-card"));

    let filtered = cards.filter(card => {
      const subj = card.dataset.subject.toLowerCase();
      const att = parseInt(card.dataset.attendance);
      if (search && !subj.includes(search)) return false;
      if (status === "low-attendance" && att >= 60) return false;
      if (status === "high-absent" && att >= 50) return false;
      return true;
    });

    if (sort === "alpha") filtered.sort((a,b) => a.dataset.subject.localeCompare(b.dataset.subject));
    if (sort === "attendance-desc") filtered.sort((a,b) => parseInt(b.dataset.attendance) - parseInt(a.dataset.attendance));

    cardsContainer.innerHTML = "";
    filtered.forEach(c => cardsContainer.appendChild(c));
  }

  searchInput.addEventListener("input", filterAndSort);
  statusFilter.addEventListener("change", filterAndSort);
  sortFilter.addEventListener("change", filterAndSort);
}

/* ---------------- MODAL ---------------- */
function initModal() {
  const modal = document.getElementById("join-modal");
  const closeBtns = modal.querySelectorAll("[data-close]");

  closeBtns.forEach(btn => btn.addEventListener("click", () => modal.style.display = "none"));

  document.querySelectorAll(".join-btn").forEach(btn => {
    btn.addEventListener("click", () => modal.style.display = "flex");
  });
}

/* ---------------- ATTENDANCE CHART ---------------- */
function initAttendanceChart() {
  const ctx = document.getElementById("attendanceChart").getContext("2d");
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Math", "Science", "History"],
      datasets: [{
        label: "Attendance %",
        data: [78, 65, 92],
        backgroundColor: "#8B0000"
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, max: 100 } }
    }
  });
}

/* ---------------- TOAST ---------------- */
function showToast(message, type="success") {
  const toast = document.createElement("div");
  toast.className = `custom-toast ${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.classList.add("show"), 50);
  setTimeout(() => toast.classList.remove("show"), 2500);
  setTimeout(() => toast.remove(), 3000);
}
