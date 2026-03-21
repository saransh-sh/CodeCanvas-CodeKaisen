window.authReady = (async function initFirebase() {
  const res = await fetch("/api/config/firebase");
  if (!res.ok) throw new Error("Could not load Firebase config from server");
  const firebaseConfig = await res.json();
  if (!firebase.apps || !firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
  }
  window.auth = firebase.auth();
})();
