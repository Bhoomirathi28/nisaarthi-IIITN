// The account lives on the phone. Sign-up works offline: the session is saved first,
// then sent to the server whenever the internet is available. No repeated logins.
import { api, setToken } from "../api";
import { load, save } from "./native";

export async function loadSession() {
  const s = await load("session", null);
  if (s?.token) setToken(s.token);
  return s;
}

export async function createSession({ name, phone, language, contacts }) {
  const session = { user: { name, phone, language }, token: null, pending: true, contactsDirty: false };
  await save("session", session);
  await save("contacts", contacts.map((c, i) => ({ id: Date.now() + i, ...c })));
  return session;
}

// Push anything not yet on the server. Safe to call often; does nothing when up to date.
export async function syncSession(session, contacts) {
  if (!session) return session;
  let s = session;
  try {
    if (s.pending) {
      const res = await api.signup({ ...s.user, contacts: contacts.map(({ name, phone }) => ({ name, phone })) });
      setToken(res.token);
      s = { ...s, token: res.token, pending: false, contactsDirty: false };
    } else if (s.contactsDirty && s.token) {
      await api.updateContacts(contacts.map(({ name, phone }) => ({ name, phone })));
      s = { ...s, contactsDirty: false };
    }
    if (s !== session) await save("session", s);
  } catch {
    /* offline or server down: try again later */
  }
  return s;
}
