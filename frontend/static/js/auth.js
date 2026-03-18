const authReady = (async function initFirebase() {
  const res = await fetch("/api/config/firebase");
  if (!res.ok) throw new Error("Could not load Firebase config from server");
  const firebaseConfig = await res.json();
  if (!firebase.apps || !firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
  }
})();

async function requireAuth(callback) {
  await authReady;
  // Return the unsubscribe function so the caller can clean up if needed.
  return firebase.auth().onAuthStateChanged((user) => {
    if (!user) {
      window.location.href = "/landing.html";
    } else {
      callback(user);
    }
  });
}

async function signInWithGoogle() {
  await authReady;
  return firebase.auth().signInWithPopup(new firebase.auth.GoogleAuthProvider());
}

async function signOut() {
  await authReady;
  firebase.auth().signOut().then(() => {
    window.location.href = "/landing.html";
  });
}

async function getIdToken() {
  await authReady;
  const user = firebase.auth().currentUser;
  if (!user) throw new Error("Not authenticated");
  return user.getIdToken();
}

async function apiFetch(url, options = {}) {
  const token = await getIdToken();
  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    ...(options.headers || {}),
  };
  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

async function loadKaizenGifs(mascotImgId, mascotKey) {
  const MASCOTS_URL = "/assets/mascots.json";
  const LOGO_FALLBACK = "/assets/logo.png";
  let data = {};
  try {
    const res = await fetch(MASCOTS_URL);
    data = await res.json();
  } catch (err) {
    console.warn("Failed to load mascots.json:", err);
  }


  const logoEl = document.getElementById("kaizenLogo");
  if (logoEl) {
    const logoSrc = (data.logo && data.logo.trim()) || LOGO_FALLBACK;
    logoEl.src = logoSrc;
  }

  if (mascotImgId && mascotKey) {
    const mascotEl = document.getElementById(mascotImgId);
    if (mascotEl) {
      const stored = localStorage.getItem("kaizen_mascot_url");
      const preferred = (data[mascotKey] && data[mascotKey].trim()) || "";
      const fallbackGif = (data.fallback && data.fallback.trim()) || LOGO_FALLBACK;
      mascotEl.src = preferred || stored || fallbackGif;
    }
  }
}


async function syncUser(user) {
  await fetch("/api/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      uid: user.uid,
      email: user.email,
      display_name: user.displayName,
    }),
  });
}