/* =========================================================================
   RoadWatch — auth.js
   Login / register, JWT storage (localStorage), and role-gated UI.
   Exposes window.Auth for the other files (citizen.js, admin.js, script.js).
   ========================================================================= */

const Auth = (() => {
  const STORAGE_KEY = "roadwatch_auth"; // {token, username, role}

  function load() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); }
    catch (e) { return null; }
  }
  function save(session) { localStorage.setItem(STORAGE_KEY, JSON.stringify(session)); }
  function clear() { localStorage.removeItem(STORAGE_KEY); }

  let session = load();

  function token() { return session && session.access_token; }
  function username() { return session && session.username; }
  function role() { return session && session.role; }
  function isAdmin() { return role() === "admin"; }
  function isLoggedIn() { return !!token(); }
  function headers() { return token() ? { Authorization: `Bearer ${token()}` } : {}; }

  function setSession(s) { session = s; save(s); updateAuthUI(); }
  function logout() { session = null; clear(); updateAuthUI(); toast("Logged out."); activateView("detect"); }

  return { token, username, role, isAdmin, isLoggedIn, headers, setSession, logout };
})();
window.Auth = Auth; // classic <script> top-level const doesn't attach to window by itself

function updateAuthUI() {
  const loggedIn = Auth.isLoggedIn();
  const admin = Auth.isAdmin();

  document.getElementById("btnLogin").hidden = loggedIn;
  document.getElementById("btnLogout").hidden = !loggedIn;
  const chip = document.getElementById("userChip");
  chip.hidden = !loggedIn;
  if (loggedIn) chip.textContent = `${Auth.username()} · ${Auth.role()}`;

  document.getElementById("bellBtn").hidden = !admin;

  document.querySelectorAll('[data-role="admin"]').forEach((el) => { el.hidden = !admin; });
  document.querySelectorAll('[data-role="user"]').forEach((el) => { el.hidden = !loggedIn || admin; });

  // if the currently active tab just got hidden (e.g. logged out of admin), bounce to Detect
  const activeTab = document.querySelector(".tab-btn.active");
  if (activeTab && activeTab.hidden) activateView("detect");

  if (admin && window.Admin) Admin.refreshBellBadge();
}

/* ---------------- Login modal ---------------- */
const loginModal = document.getElementById("loginModal");
let loginMode = "login"; // "login" | "register"

function openLoginModal() {
  loginMode = "login";
  document.getElementById("loginTitle").textContent = "Log in";
  document.getElementById("btnLoginToggle").textContent = "Create citizen account";
  document.getElementById("loginUser").value = "";
  document.getElementById("loginPass").value = "";
  document.getElementById("loginEmail").value = "";
  document.getElementById("loginEmail").hidden = true;
  document.getElementById("loginErr").textContent = "";
  loginModal.hidden = false;
  document.getElementById("loginUser").focus();
}
function closeLoginModal() { loginModal.hidden = true; }

document.getElementById("btnLogin").addEventListener("click", openLoginModal);
document.getElementById("btnLoginCancel").addEventListener("click", closeLoginModal);
loginModal.addEventListener("click", (e) => { if (e.target === loginModal) closeLoginModal(); });

document.getElementById("btnLoginToggle").addEventListener("click", () => {
  loginMode = loginMode === "login" ? "register" : "login";
  document.getElementById("loginTitle").textContent = loginMode === "login" ? "Log in" : "Create citizen account";
  document.getElementById("btnLoginToggle").textContent = loginMode === "login" ? "Create citizen account" : "Back to log in";
  document.getElementById("loginEmail").hidden = loginMode !== "register";
  document.getElementById("loginErr").textContent = "";
});

document.getElementById("btnLogout").addEventListener("click", () => Auth.logout());

document.getElementById("btnLoginSubmit").addEventListener("click", submitLogin);
[document.getElementById("loginUser"), document.getElementById("loginPass")].forEach((el) => {
  el.addEventListener("keydown", (e) => { if (e.key === "Enter") submitLogin(); });
});

async function submitLogin() {
  const username = document.getElementById("loginUser").value.trim();
  const password = document.getElementById("loginPass").value;
  const errEl = document.getElementById("loginErr");
  errEl.textContent = "";

  if (!username || !password) { errEl.textContent = "Enter a username and password."; return; }

  const path = loginMode === "login" ? "/auth/login" : "/auth/register";
  const payload = { username, password };
  if (loginMode === "register") {
    const email = document.getElementById("loginEmail").value.trim();
    if (email) payload.email = email;
  }
  try {
    const data = await api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    Auth.setSession(data);
    closeLoginModal();
    toast(loginMode === "login" ? `Welcome back, ${data.username}.` : `Account created — welcome, ${data.username}.`);
  } catch (e) {
    errEl.textContent = e.message || "Login failed.";
  }
}

updateAuthUI();
