/**
 * GIGACHAD AI GATEKEEPER - CLIENT SCRIPT (Debug & Feature Complete)
 */

// --- Configuration ---
const API_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? "http://localhost:8000"
    : "https://gigachad-ai-gatekeeper-backend.onrender.com";

let currentUserToken = null;
let messages = []; // Chat History State

document.addEventListener("DOMContentLoaded", () => {
    console.log("✅ [INIT] DOM Fully Loaded.");
    initApp();
});

// --- Initialization ---
async function initApp() {
    try {
        console.log("📡 [INIT] Fetching Config...");
        const res = await fetch(`${API_URL}/config`);
        if (!res.ok) throw new Error("Config Fetch Failed");

        const firebaseConfig = await res.json();

        // Init Firebase
        if (!firebase.apps.length) {
            firebase.initializeApp(firebaseConfig);
            console.log("🔥 [FIREBASE] Initialized");
        }

        setupAuthListener();
        setupEventListeners();

        // Gate opening is now handled in setupAuthListener to ensure correct state is ready.
    } catch (error) {
        console.error("❌ [CRITICAL] System Init Failed:", error);
        alert("SYSTEM ERROR: Could not connect to Gatekeeper Core.");
    }
}

// --- Auth & State Management ---
function setupAuthListener() {
    firebase.auth().onAuthStateChanged((user) => {
        const loginSection = document.getElementById('login-section');
        const voidOverlay = document.getElementById('void-overlay');

        if (user) {
            console.log("👤 [AUTH] User Logged In:", user.email);
            user.getIdToken().then(async (token) => {
                currentUserToken = token;

                // Check with server if already submitted
                try {
                    const statusRes = await fetch(`${API_URL}/check-status`, {
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    const status = await statusRes.json();
                    console.log("📋 [STATUS] Server says:", status);

                    if (status.submitted) {
                        // User already submitted -> Show "Go Away" page
                        console.log("🚫 [STATE] Already Submitted -> Go Away");
                        loginSection.style.display = 'none';
                        voidOverlay.style.display = 'none';
                        document.getElementById('app-container').style.display = 'none';
                        document.getElementById('success-overlay').style.display = 'none';

                        const goAway = document.getElementById('submitted-overlay');
                        goAway.style.display = 'flex';
                        localStorage.setItem('GIGACHAD_ACCESS', 'true'); // Sync local
                        openTheGate();
                        return;
                    }
                } catch (e) {
                    console.warn("⚠️ Status check failed (using local):", e);
                }

                // Hide Login
                loginSection.style.display = 'none';

                // Check local storage as fallback
                if (localStorage.getItem('GIGACHAD_ACCESS') === 'true') {
                    console.log("🔓 [STATE] Already Submitted (local) -> Go Away");
                    document.getElementById('submitted-overlay').style.display = 'flex';
                } else {
                    console.log("🌌 [STATE] New User -> Show Void");
                    // Only show Void if we haven't entered it yet in this session
                    if (!sessionStorage.getItem('VOID_ENTERED')) {
                        voidOverlay.style.display = 'flex';
                    } else {
                        // Refresh case: Skip void, go to chat
                        showChatInterface();
                    }
                }
            });
        } else {
            console.log("🔒 [AUTH] User Logged Out");
            // Force Visibility (Nuclear Option)
            loginSection.style.cssText = "display: flex !important; opacity: 1 !important; visibility: visible !important; z-index: 9999 !important; position: fixed !important; top: 0 !important; left: 0 !important; width: 100vw !important; height: 100vh !important; background-color: #050505 !important; flex-direction: column !important;";

            document.getElementById('app-container').style.display = 'none';
            voidOverlay.style.display = 'none';
        }

        // State is ready -> Open the Gate
        openTheGate();
    });
}

function openTheGate() {
    const gate = document.getElementById('gate-overlay');
    // Only open if it hasn't been opened yet or if it's visible
    if (gate && gate.style.display !== 'none') {
        gate.classList.add('gate-open');
        setTimeout(() => {
            gate.style.display = 'none';
        }, 2000);
    }
}

// --- Event Listeners (Guaranteed Attachment) ---
function setupEventListeners() {
    // 1. Google Login
    const loginBtn = document.getElementById('google-login-btn');
    if (loginBtn) {
        loginBtn.addEventListener('click', () => {
            const provider = new firebase.auth.GoogleAuthProvider();
            firebase.auth().signInWithPopup(provider).catch(e => alert(e.message));
        });
    }

    // 2. Chat Interaction
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');

    if (sendBtn && userInput) {
        sendBtn.addEventListener('click', sendMessage);
        userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
        console.log("✅ [UI] Chat Listeners Attached");
    } else {
        console.error("❌ [UI] Chat Elements Missin in DOM!");
    }

    // 3. Form Submission
    const form = document.getElementById('submission-form');
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }
}

// --- Flow Control ---
function enterTheVoid() {
    console.log("🌌 [ACTION] Entering the Void...");
    const overlay = document.getElementById('void-overlay');
    overlay.style.opacity = '0';

    sessionStorage.setItem('VOID_ENTERED', 'true'); // Remember for refresh

    setTimeout(() => {
        overlay.style.display = 'none';
        showChatInterface();
    }, 1500);
}

function showChatInterface() {
    // Force Hide Login (Safety)
    document.getElementById('login-section').style.display = 'none';

    // Show App
    const app = document.getElementById('app-container');
    app.style.display = 'flex'; // Flexbox layout
    app.style.opacity = '1';

    // Initial AI Message (if empty)
    if (messages.length === 0) {
        const user = firebase.auth().currentUser;
        const name = user ? user.displayName.split(" ")[0] : "Human";
        appendMessage('ai', `Welcome, ${name}. Prove your worth.`);
        messages.push({ "role": "assistant", "content": `Welcome, ${name}. Prove your worth.` });
    }
}

// --- Chat Logic ---
async function sendMessage() {
    const input = document.getElementById('user-input');
    const text = input.value.trim();
    if (!text) return;

    console.log("💬 [CHAT] User sent:", text);

    // UI Update
    appendMessage('user', text);
    messages.push({ role: 'user', content: text });
    input.value = '';

    // Create AI Placeholder
    const aiMsgDiv = appendMessage('ai', '...');
    let fullResponse = "";

    try {
        const response = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${currentUserToken}`
            },
            body: JSON.stringify({ messages: messages })
        });

        if (!response.ok) throw new Error("API Error");

        // Stream Reader
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        aiMsgDiv.innerText = "";
        let accessGranted = false;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value);
            fullResponse += chunk;

            // Check for server's secure signal (NOT user-typeable text)
            if (chunk.includes("[[GATE_OPEN]]")) {
                accessGranted = true;
                // Remove the signal from display
                fullResponse = fullResponse.replace("[[GATE_OPEN]]", "").trim();
            }

            // Display (without the signal)
            const displayText = fullResponse.replace("[[GATE_OPEN]]", "").trim();
            aiMsgDiv.innerText = displayText + "▌"; // Cursor effect

            // Auto Scroll
            const history = document.getElementById('chat-history');
            history.scrollTop = history.scrollHeight;
        }

        // Clean final display
        const cleanResponse = fullResponse.replace("[[GATE_OPEN]]", "").trim();
        aiMsgDiv.innerText = cleanResponse;
        messages.push({ role: 'assistant', content: cleanResponse });

        // 🔐 SECURE CHECK: Only trust the server's signal
        if (accessGranted) {
            console.log("🔓 [SECURITY] Server confirmed ACCESS GRANTED. Triggering form...");
            setTimeout(triggerSuccess, 2000);
        }

    } catch (error) {
        console.error("❌ [CHAT] Error:", error);
        aiMsgDiv.innerText = "[OOPS! Too many people are trying to talk with me rn so you come back later]";
    }
}

function appendMessage(role, text) {
    const history = document.getElementById('chat-history');
    const div = document.createElement('div');
    div.className = role === 'user' ? 'user-msg' : 'ai-msg';
    div.innerText = text;
    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
    return div;
}

// --- Data Submission ---
function triggerSuccess() {
    localStorage.setItem('GIGACHAD_ACCESS', 'true');
    document.getElementById('app-container').style.display = 'none';

    const overlay = document.getElementById('success-overlay');
    overlay.style.display = 'flex';
    overlay.style.visibility = 'visible';
    document.getElementById('submission-form').style.display = 'block';

    // Update User Info
    const user = firebase.auth().currentUser;
    if (user) document.getElementById('user-email-display').innerText = user.email;
}

async function handleFormSubmit(e) {
    e.preventDefault();
    console.log("📝 [FORM] Submitting...");

    const btn = document.querySelector('#submission-form button');
    btn.innerText = "SECURING...";
    btn.disabled = true;

    // 1. Validate Student ID
    const studentId = document.getElementById('student-id').value.trim();
    if (!/^20\d{2}[A-Z0-9]{4}\d{4}[A-Z]?$/i.test(studentId)) {
        alert("❌ Invalid BITS ID format. Example: 2024A7PS1234P");
        btn.innerText = "SECURE CREDENTIALS";
        btn.disabled = false;
        return;
    }

    // 2. Collect Preferences as Array (not string)
    const prefSelect = document.getElementById('preference');
    const selectedPrefs = Array.from(prefSelect.selectedOptions).map(o => o.value);

    if (selectedPrefs.length === 0) {
        alert("❌ Please select at least one preference.");
        btn.innerText = "SECURE CREDENTIALS";
        btn.disabled = false;
        return;
    }

    // 3. Get Name with fallback
    const user = firebase.auth().currentUser;
    const userName = user.displayName || user.email.split('@')[0];

    // 4. Truncate chat history to last 50 messages (avoid 1MB Firestore limit)
    const truncatedHistory = messages.slice(-50);

    const data = {
        name: userName,
        student_id: studentId,
        preference: selectedPrefs,  // Now an array
        skills: document.getElementById('skills').value,
        commitments: document.getElementById('commitments').value,
        notes: document.getElementById('notes').value,
        chat_history: truncatedHistory
    };

    try {
        const res = await fetch(`${API_URL}/submit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${currentUserToken}`
            },
            body: JSON.stringify(data)
        });

        if (res.ok) {
            alert("APPLICATION SECURED. YOU MAY LEAVE.");
            window.location.reload();
        } else {
            throw new Error("Submission Failed");
        }
    } catch (error) {
        alert("Error: " + error.message);
        btn.disabled = false;
        btn.innerText = "TRY AGAIN";
    }
}

// --- Helpers ---
function openInfo() { document.getElementById('info-modal').style.display = 'flex'; }
function closeInfo() { document.getElementById('info-modal').style.display = 'none'; }
