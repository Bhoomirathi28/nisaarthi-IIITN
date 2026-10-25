import { useState } from "react";
import { LANGS, useT } from "../i18n";
import { normalizePhone } from "../lib/phone";

const MAX = 5;
const blank = () => ({ name: "", phone: "" });

export default function SignUp({ lang, setLang, onDone }) {
  const { t } = useT();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [contacts, setContacts] = useState([blank()]);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  const setContact = (i, patch) => setContacts(contacts.map((c, j) => (j === i ? { ...c, ...patch } : c)));

  const submit = async () => {
    const e = {};
    const own = normalizePhone(phone);
    if (!name.trim()) e.name = "err_name";
    if (!own) e.phone = "err_phone";
    const filled = contacts.filter((c) => c.name.trim() || c.phone.trim());
    const cleaned = [];
    filled.forEach((c, i) => {
      const p = normalizePhone(c.phone);
      if (!c.name.trim() || !p) e[`c${i}`] = "err_contact";
      else if (p === own) e[`c${i}`] = "err_contact_self";
      else cleaned.push({ name: c.name.trim(), phone: p });
    });
    if (!filled.length) e.c0 = "err_contact";
    setErrors(e);
    if (Object.keys(e).length) return;
    setBusy(true);
    await onDone({ name: name.trim(), phone: own, language: lang, contacts: cleaned });
  };

  const Err = ({ k }) => (errors[k] ? <p className="field-error" role="alert">{t(errors[k])}</p> : null);

  return (
    <div className="signup">
      <header className="signup-head">
        <h1 className="brand">NISAARTHI</h1>
        <p className="tagline">{t("tagline")}</p>
        <p className="muted">{t("signup_sub")}</p>
      </header>

      <section className="panel panel-framed">
        <h2>{t("choose_language")}</h2>
        <div className="lang-grid">
          {LANGS.map((l) => (
            <button key={l.code} lang={l.code} className={`lang-chip ${lang === l.code ? "on" : ""}`}
              aria-pressed={lang === l.code} onClick={() => setLang(l.code)}>
              {l.name}
            </button>
          ))}
        </div>
      </section>

      <section className="panel form">
        <h2>{t("about_you")}</h2>
        <label>
          <span className="field-label">{t("your_name")}</span>
          <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
        </label>
        <Err k="name" />
        <label>
          <span className="field-label">{t("your_phone")}</span>
          <span className="phone-input">
            <span className="prefix">+91</span>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel" maxLength={14} />
          </span>
        </label>
        <Err k="phone" />
      </section>

      <section className="panel form">
        <h2>{t("contacts_title")}</h2>
        <p className="muted small">{t("em_contacts_note")}</p>
        {contacts.map((c, i) => (
          <div key={i} className="contact-entry">
            <div className="row-between">
              <span className="field-label">{t("contact_n", { n: i + 1 })}</span>
              {contacts.length > 1 && (
                <button className="btn btn-text" onClick={() => setContacts(contacts.filter((_, j) => j !== i))}>
                  {t("remove")}
                </button>
              )}
            </div>
            <div className="two-col">
              <input aria-label={t("name")} placeholder={t("name")} value={c.name}
                onChange={(e) => setContact(i, { name: e.target.value })} />
              <input aria-label={t("phone")} placeholder={t("phone")} value={c.phone} inputMode="tel"
                onChange={(e) => setContact(i, { phone: e.target.value })} />
            </div>
            <Err k={`c${i}`} />
          </div>
        ))}
        {contacts.length < MAX && (
          <button className="btn btn-ghost" onClick={() => setContacts([...contacts, blank()])}>+ {t("add_another")}</button>
        )}
      </section>

      <button className="btn btn-primary btn-block btn-big" onClick={submit} disabled={busy}>
        {t("create_account")}
      </button>
      <p className="muted small center">{t("signup_privacy")}</p>
    </div>
  );
}
