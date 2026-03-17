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