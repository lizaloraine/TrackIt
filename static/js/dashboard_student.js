document.addEventListener("DOMContentLoaded", () => {
    console.log("Student Dashboard JS Loaded");

    const joinBtn = document.getElementById("join-class-btn");
    const modalBg = document.getElementById("modal-bg");
    const cancelJoin = document.getElementById("cancel-join");
    const confirmJoin = document.getElementById("confirm-join");
    const classCodeInput = document.getElementById("class-code-input");
    const sectionSelect = document.getElementById("class-section-select");

    // SAFE CHECK — Prevent JS crashes
    function exists(el, name) {
        if (!el) {
            console.error("Missing element:", name);
            return false;
        }
        return true;
    }

    // --------------------------
    //  OPEN JOIN MODAL
    // --------------------------
    if (exists(joinBtn, "join-class-btn") && exists(modalBg, "modal-bg")) {
        joinBtn.addEventListener("click", () => {
            console.log("Opening Join Modal");
            modalBg.classList.add("active");
        });
    }

    // --------------------------
    //  CLOSE JOIN MODAL
    // --------------------------
    if (exists(cancelJoin, "cancel-join") && exists(modalBg, "modal-bg")) {
        cancelJoin.addEventListener("click", () => {
            console.log("Closing Join Modal");
            modalBg.classList.remove("active");
            modalBg.style.display = "none";
            classCodeInput.value = "";
            sectionSelect.innerHTML = `<option value="">Select a section…</option>`;
        });
    }

    // Clicking outside modal closes it
    modalBg.addEventListener("click", (event) => {
        if (event.target === modalBg) {
            modalBg.classList.remove("active");
        }

    // --------------------------
    //  AUTO LOAD SECTIONS
    // --------------------------
    if (exists(classCodeInput, "class-code-input") && exists(sectionSelect, "class-section-select")) {
        classCodeInput.addEventListener("input", async () => {
            const code = classCodeInput.value.trim().toUpperCase();
            if (!code) return;

            console.log("Fetching sections:", code);

            try {
                const res = await fetch(`/api/class/${code}/sections`);
                const data = await res.json();

                sectionSelect.innerHTML = `<option value="">Select a section…</option>`;

                data.sections.forEach(sec => {
                    let opt = document.createElement("option");
                    opt.value = sec;
                    opt.textContent = sec;
                    sectionSelect.appendChild(opt);
                });

            } catch (err) {
                console.error("Section fetch error:", err);
            }
        });
    }

    // --------------------------
    //  JOIN CLASS ACTION
    // --------------------------
    if (exists(confirmJoin, "confirm-join")) {
        confirmJoin.addEventListener("click", async () => {
            const classCode = classCodeInput.value.trim().toUpperCase();
            const section = sectionSelect.value.trim();

            if (!classCode || !section) {
                alert("Please fill all fields.");
                return;
            }

            console.log("Joining class:", classCode, section);

            const formData = new FormData();
            formData.append("action", "join_class");
            formData.append("class_code", classCode);
            formData.append("section", section);

            try {
                const res = await fetch("/dashboard", {
                    method: "POST",
                    body: formData
                });

                // Flask returns redirect
                if (res.redirected) {
                    window.location.href = res.url;
                } else {
                    window.location.reload();
                }

            } catch (err) {
                console.error("JOIN ERROR:", err);
            }
        });
    }
});
});
