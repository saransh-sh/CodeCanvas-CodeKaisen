async function requireAuth(callback) {
  await authReady;
  return auth.onAuthStateChanged((user) => {
    if (!user) {
      window.location.href = "/landing.html";
    } else {
      callback(user);
    }
  });
}

let isSigningIn = false;

async function signInWithGoogle() {
  if (isSigningIn) return null;
  isSigningIn = true;
  try {
    await authReady;
    return await auth.signInWithPopup(new firebase.auth.GoogleAuthProvider());
  } finally {
    isSigningIn = false;
  }
}

async function signOut() {
  await authReady;
  await auth.signOut();
  window.location.href = "/landing.html";
}

async function getIdToken() {
  await authReady;
  const user = auth.currentUser;
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
      const preferred = (data[mascotKey] && data[mascotKey].trim()) || "";
      const fallbackGif = (data.fallback && data.fallback.trim()) || LOGO_FALLBACK;
      mascotEl.src = preferred || fallbackGif;
    }
  }
}

async function syncUser(user) {
  await apiFetch("/api/users", {
    method: "POST",
    body: JSON.stringify({
      email: user.email,
      display_name: user.displayName,
    }),
  });
}
