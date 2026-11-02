// ==========================================
// DOM ELEMENTS
// ==========================================

const chat = document.getElementById("chat");
const form = document.getElementById("chatForm");
const question = document.getElementById("question");
const trace = document.getElementById("trace");
const sourceUsed = document.getElementById("sourceUsed");


// ==========================================
// HTML ESCAPE
// ==========================================

function escapeHtml(text = "") {
    return String(text).replace(/[&<>'"]/g, (char) => {
        const entities = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            "'": "&#39;",
            '"': "&quot;"
        };

        return entities[char];
    });
}


// ==========================================
// FORMAT MESSAGE
// ==========================================

function formatText(text = "") {
    return escapeHtml(text).replace(/\n/g, "<br>");
}


// ==========================================
// ADD CHAT MESSAGE
// ==========================================

function addMessage(role, text, source = "", citations = []) {

    const wrap = document.createElement("div");

    wrap.className = `message ${role}`;

    const citeHtml = citations.length
        ? `
            <div class="citations">
                <strong>Sources</strong>
                <br>
                ${citations.map((citation) => {

                    const title = escapeHtml(
                        citation.title || "Source"
                    );

                    if (citation.url) {

                        return `
                            <a
                                href="${escapeHtml(citation.url)}"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                ${title}
                            </a>
                        `;
                    }

                    return title;

                }).join("<br>")}
            </div>
        `
        : "";

    wrap.innerHTML = `
        <div class="avatar">
            ${role === "user" ? "You" : "AI"}
        </div>

        <div class="bubble">

            ${formatText(text)}

            ${
                source
                    ? `
                        <div class="answer-source">
                            Source: ${escapeHtml(source)}
                        </div>
                    `
                    : ""
            }

            ${citeHtml}

        </div>
    `;

    chat.appendChild(wrap);

    chat.scrollTop = chat.scrollHeight;
}


// ==========================================
// RENDER AGENT TRACE
// ==========================================

function renderTrace(items = []) {

    if (!items.length) {

        trace.innerHTML = `
            <div class="empty">
                No trace.
            </div>
        `;

        return;
    }

    trace.innerHTML = items.map((item) => {

        return `
            <div class="trace-item">
                ${escapeHtml(item)}
            </div>
        `;

    }).join("");
}


// ==========================================
// CHAT API
// ==========================================

async function askAgent(userQuestion) {

    if (!userQuestion.trim()) {
        return;
    }

    addMessage("user", userQuestion);

    question.value = "";

    renderTrace([
        "Starting LangGraph workflow...",
        "Processing user question..."
    ]);

    sourceUsed.textContent = "Running";

    const button = form.querySelector(
        'button[type="submit"]'
    );

    button.disabled = true;

    try {

        const response = await fetch("/api/chat", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                question: userQuestion
            })

        });

        const data = await response.json();

        if (!response.ok) {

            throw new Error(
                data.detail || "Request failed"
            );
        }

        // Display AI answer
        addMessage(
            "assistant",
            data.answer || "No answer received.",
            data.source_used || "",
            data.citations || []
        );

        // Display agent workflow trace
        renderTrace(data.trace || []);

        // Display final source
        sourceUsed.textContent =
            data.source_used || "Unknown";

    }

    catch (error) {

        addMessage(
            "assistant",
            `Error: ${error.message}`
        );

        renderTrace([
            "Request failed",
            error.message
        ]);

        sourceUsed.textContent = "Error";

    }

    finally {

        button.disabled = false;

    }
}


// ==========================================
// CHAT FORM SUBMISSION
// ==========================================

form.addEventListener("submit", (event) => {

    event.preventDefault();

    const userQuestion = question.value.trim();

    if (userQuestion) {
        askAgent(userQuestion);
    }

});


// ==========================================
// EXAMPLE QUESTIONS
// ==========================================

document.querySelectorAll(".example").forEach((button) => {

    button.addEventListener("click", () => {

        const exampleQuestion = button.textContent.trim();

        askAgent(exampleQuestion);

    });

});


// ==========================================
// DOCUMENT UPLOAD MODAL
// ==========================================

const modal = document.getElementById("uploadModal");

const openUpload = document.getElementById("openUpload");

const closeUpload = document.getElementById("closeUpload");


// Open modal
openUpload.addEventListener("click", () => {

    modal.classList.remove("hidden");

});


// Close modal
closeUpload.addEventListener("click", () => {

    modal.classList.add("hidden");

});


// Close modal when clicking outside
modal.addEventListener("click", (event) => {

    if (event.target === modal) {

        modal.classList.add("hidden");

    }

});


// ==========================================
// DOCUMENT INGESTION
// ==========================================

const uploadButton = document.getElementById("uploadBtn");

uploadButton.addEventListener("click", async () => {

    const fileInput = document.getElementById("fileInput");

    const adminKey = document.getElementById("adminKey");

    const status = document.getElementById("uploadStatus");

    const file = fileInput.files[0];

    const key = adminKey.value.trim();


    // Validate file
    if (!file) {

        status.textContent = "Choose a file first.";

        return;
    }


    // Validate admin key
    if (!key) {

        status.textContent = "Enter admin API key.";

        return;
    }


    status.textContent = "Uploading and indexing document...";

    uploadButton.disabled = true;


    const formData = new FormData();

    formData.append("file", file);


    try {

        const response = await fetch("/api/ingest", {

            method: "POST",

            headers: {
                "X-Admin-Key": key
            },

            body: formData

        });


        const data = await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail || "Document upload failed"
            );

        }


        status.textContent =
            `Successfully indexed ${data.file}: ${data.chunks} chunks.`;


        // Clear uploaded file
        fileInput.value = "";

    }

    catch (error) {

        status.textContent =
            `Error: ${error.message}`;

    }

    finally {

        uploadButton.disabled = false;

    }

});


// ==========================================
// INITIAL APPLICATION STATE
// ==========================================

renderTrace([]);

sourceUsed.textContent = "—";