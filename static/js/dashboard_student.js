/* ========== UTIL: Toast Notification ========== */
function showToast(msg) {
    let toast = document.createElement("div");
    toast.className = "toast show";
    toast.innerText = msg;

    document.body.appendChild(toast);
    setTimeout(() => toast.classList.remove("show"), 2000);
    setTimeout(() => toast.remove(), 2600);
}

/* ========== ELEMENTS ========== */
const modalBG = document.getElementById("modal-bg");
const joinBtn = document.getElementById("join-class-btn");
const cancelBtn = document.getElementById("cancel-join");
const confirmJoin = document.getElementById("confirm-join");
const classCodeInput = document.getElementById("class-code-input");

/* ========== OPEN MODAL ========== */
joinBtn.onclick = () => {
    modalBG.classList.add("active");
    classCodeInput.focus();
};

/* ========== CLOSE MODAL ========== */
function closeModal() {
    modalBG.classList.remove("active");
    classCodeInput.value = "";
    classCodeInput.classList.remove("input-error");
}

cancelBtn.onclick = closeModal;

window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
});

/* ========== JOIN CLASS ACTION ========== */
confirmJoin.onclick = handleJoinClass;
classCodeInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleJoinClass();
});

function handleJoinClass() {
    let code = classCodeInput.value.trim();

    if (!code) {
        classCodeInput.classList.add("input-error");
        showToast("Class code required.");
        return;
    }

    classCodeInput.classList.remove("input-error");

    confirmJoin.disabled = true;
    confirmJoin.innerText = "Joining...";

    setTimeout(() => {
        showToast("Successfully joined class!");
        closeModal();

        confirmJoin.disabled = false;
        confirmJoin.innerText = "Join";
    }, 1200);
}

/* Click outside closes modal */
modalBG.addEventListener("click", (e) => {
    if (e.target === modalBG) closeModal();
});
