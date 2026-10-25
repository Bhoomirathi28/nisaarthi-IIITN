import { useState } from "react";
import { useT } from "../i18n";
import { call } from "../lib/sos";
import { normalizePhone } from "../lib/phone";

const MAX = 5;

export default function Contacts({ contacts, setContacts }) {
  const { t } = useT();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const valid = name.trim() && normalizePhone(phone);

  const add = () => {
    if (!valid || contacts.length >= MAX) return;
    setContacts([...contacts, { id: Date.now(), name: name.trim(), phone: normalizePhone(phone) }]);
    setName(""); setPhone("");
  };

  return (
    <div className="contacts">
      <h1 className="screen-title">{t("contacts_title")}</h1>
      <p className="muted">{t("contacts_sub")}</p>
      {contacts.length === 0 && <p className="banner">{t("contacts_empty")}</p>}
      <ul className="contact-list">
        {contacts.map((c) => (
          <li key={c.id} className="panel contact">
            <button className="contact-main" onClick={() => call(c.phone)}>
              <span className="avatar" aria-hidden="true">{c.name[0]}</span>
              <span><strong>{c.name}</strong><br /><span className="muted small">{c.phone}</span></span>
            </button>
            {contacts.length > 1 && (
              <button className="btn btn-text" onClick={() => setContacts(contacts.filter((x) => x.id !== c.id))}>
                {t("remove")}
              </button>
            )}
          </li>
        ))}
      </ul>
      {contacts.length < MAX ? (
        <div className="panel form">
          <label><span className="field-label">{t("name")}</span>
            <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></label>
          <label><span className="field-label">{t("phone")}</span>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel" /></label>
          <button className="btn btn-primary btn-block" onClick={add} disabled={!valid}>{t("add_contact")}</button>
        </div>
      ) : <p className="muted small">{t("contacts_full")}</p>}
    </div>
  );
}
