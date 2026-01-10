const API_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? "http://localhost:8000"
    : "https://gigachad-ai-gatekeeper-backend.onrender.com";
let firebaseConfig = null;

// Fetch Config from Backend (Securely render env vars)
async function initApp() {
    try {
        const res = await fetch(`${API_URL}/config`);
        if (!res.ok) {
            console.error("Config fetch failed with:", res.status);
            throw new Error("Failed to load config");
        }
        firebaseConfig = await res.json();
        if (!firebase.apps.length) {
            firebase.initializeApp(firebaseConfig);
        } else {
            console.log("Firebase already initialized");
        }
    } catch (e) {
        console.error("Config Error Details:", e);
        // Fallback for debugging
        document.body.innerHTML = `<h1 style='color:red; text-align:center; margin-top:50px;'>⚠️ SYSTEM CONFIGURATION FAILED</h1><p style='text-align:center; color:white;'>${e.message}<br>Check console for details.</p>`;
    }
}

// Initialize immediately
initApp();

const gateOverlay = document.getElementById('gate-overlay');
const appContainer = document.getElementById('app-container');
const chatHistory = document.getElementById('chat-history');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const successOverlay = document.getElementById('success-overlay');
const submissionForm = document.getElementById('submission-form');
const loginSection = document.getElementById('login-section');
const loginBtn = document.getElementById('google-login-btn');
const emailDisplay = document.getElementById('user-email-display');

// State
let messages = [];
let currentUserToken = null;

const submittedOverlay = document.getElementById('submitted-overlay');

// --- Persistence Check ---
const hasAccess = localStorage.getItem('GIGACHAD_ACCESS');
const hasSubmitted = localStorage.getItem('GIGACHAD_SUBMITTED');

window.addEventListener('load', () => {
    if (hasSubmitted) {
        // Mode 1: Already Submitted -> Block everything
        submittedOverlay.style.display = 'flex';
        gateOverlay.style.display = 'none';
        appContainer.style.display = 'none';
    } else if (hasAccess) {
        // Mode 2: Access Granted but not submitted -> Go straight to form
        successOverlay.style.display = 'flex';
        gateOverlay.style.display = 'none';
        appContainer.style.opacity = '0.1'; // dim background
        appContainer.style.pointerEvents = 'none'; // disable interaction
    } else {
        // Mode 3: Normal Entry -> Animation
        setTimeout(() => {
            gateOverlay.classList.add('gate-open');
            // LOGIN FIRST FLOW:
            // 1. Hide the Chat App initially
            appContainer.style.display = 'none';
            // 2. Show the Success Overlay (which acts as the login container now)
            successOverlay.style.display = 'flex';
            // 3. Ensure Login Button is visible
            loginSection.style.display = 'block';
            submissionForm.style.display = 'none';
        }, 1500);
    }
});

// --- Auth Logic (LOGIN FIRST) ---
loginBtn.addEventListener('click', () => {
    const provider = new firebase.auth.GoogleAuthProvider();
    provider.setCustomParameters({ hd: "pilani.bits-pilani.ac.in" });

    firebase.auth().signInWithPopup(provider)
        .then((result) => {
            const user = result.user;
            if (!user.email.endsWith("bits-pilani.ac.in")) {
                alert("Restricted Access: @pilani.bits-pilani.ac.in required.");
                user.delete();
                return;
            }

            user.getIdToken().then(idToken => {
                // --- Success ---
                currentUserToken = idToken; // Store for API calls
                loginSection.style.display = 'none'; // Hide Login

                // Check if user already has access or submitted
                if (localStorage.getItem('GIGACHAD_ACCESS') === 'true') {
                    // Skip Void, show form directly
                    triggerSuccess();
                } else {
                    // SHOW THE VOID (Cinematic Intro)
                    document.getElementById('void-overlay').style.display = 'flex';
                }
            });
        })
        .catch((error) => {
            alert("Login Failed: " + error.message);
        });
});

// --- Cinematic Logic ---
function enterTheVoid() {
    const overlay = document.getElementById('void-overlay');
    overlay.style.opacity = '0'; // Fade out

    setTimeout(() => {
        overlay.style.display = 'none';

        // Show Chat Interface
        appContainer.style.display = 'flex';
        appContainer.style.opacity = '0';
        setTimeout(() => appContainer.style.opacity = '1', 100);

        // First message
        if (messages.length === 0) {
            const user = firebase.auth().currentUser;
            const name = user ? user.displayName.split(" ")[0] : "User";
            appendMessage('ai', `Welcome, ${name}. Proove your worth.`);
            messages.push({ "role": "assistant", "content": `Welcome, ${name}. Proove your worth.` });
        }
    }, 1500); // Wait for fade
}

function openInfo() { document.getElementById('info-modal').style.display = 'flex'; }
function closeInfo() { document.getElementById('info-modal').style.display = 'none'; }

// --- Chat Logic ---
function appendMessage(role, text) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerText = text;
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return div;
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    if (!currentUserToken) {
        alert("Session Expired. Please reload.");
        return;
    }

    // UI Updates
    userInput.value = '';
    appendMessage('user', text);
    messages.push({ role: 'user', content: text });

    // Create placeholder for AI
    const aiMsgDiv = appendMessage('ai', '...');
    let fullResponse = "";

    try {
        const response = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${currentUserToken}` // Send Token
            },
            body: JSON.stringify({ messages: messages })
        });

        if (!response.ok) throw new Error("API Error");

        // Streaming logic
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        aiMsgDiv.innerText = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            fullResponse += chunk;
            aiMsgDiv.innerText = fullResponse + "▌";
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }

        // Finalize
        aiMsgDiv.innerText = fullResponse;
        messages.push({ role: 'assistant', content: fullResponse });

        // Check Access (Regex)
        const accessRegex = /\[?\s*access\s+granted\s*\]?/i;
        if (accessRegex.test(fullResponse)) {
            triggerSuccess();
        }

    } catch (e) {
        aiMsgDiv.innerText = "Error: " + e.message;
    }
}

function triggerSuccess() {
    localStorage.setItem('GIGACHAD_ACCESS', 'true');
    setTimeout(() => {
        // Hide Chat
        appContainer.style.display = 'none';

        // Show Success Overlay with Updated Content
        document.getElementById('overlay-title').innerText = "🔓 ACCESS GRANTED";
        document.getElementById('overlay-subtitle').innerText = "Welcome to the elite.";

        // Ensure Form is Visible, Login is Hidden
        loginSection.style.display = 'none';
        submissionForm.style.display = 'block';

        successOverlay.style.display = 'flex';
    }, 1000);
}

// --- Event Listeners ---
sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

// --- Form Submission ---
submissionForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!currentUserToken) {
        alert("Authentication Required.");
        return;
    }

    const btn = submissionForm.querySelector('button');
    btn.disabled = true;
    btn.innerText = "SECURING...";

    const data = {
        name: firebase.auth().currentUser.displayName, // Auto-fill name
        student_id: document.getElementById('student-id').value,
        preference: document.getElementById('preference').value,
        skills: document.getElementById('skills').value,
        commitments: document.getElementById('commitments').value,
        notes: document.getElementById('notes').value,
        chat_history: messages // Send full chat log
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
            localStorage.setItem('GIGACHAD_SUBMITTED', 'true');
            alert("Credentials Secured. We will be in touch.");
            successOverlay.style.display = 'none';
            // Reload to show submitted overlay
            window.location.reload();
        } else {
            const err = await res.json();
            alert("Error: " + (err.detail || "Unknown error"));
        }
    } catch (e) {
        alert("Connection Failed.");
    } finally {
        btn.disabled = false;
        btn.innerText = "SECURE CREDENTIALS";
    }
});
