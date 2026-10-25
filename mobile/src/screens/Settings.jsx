import { useState } from "react";
import { LANGS, useT } from "../i18n";
import { defaultApiBase } from "../api";
import { IconBack } from "../components/Icons";

export default function Settings({ lang, setLang, settings, setSettings, onBack }) {
  const { t } = useT();
  const [server, setServer] = useState(settings.server);
  const [saved, setSaved] = useState(false);

  return (
    <div className="settings">
      <div className="row-start">
        <button className="icon-btn" onClick={onBack} aria-label={t("close")}><IconBack /></button>
        <h1 className="screen-title">{t("settings")}</h1>
      </div>

      <fieldset className="segmented">
        <legend className="field-label">{t("language")}</legend>
        {LANGS.map((l) => (
          <label key={l.code} className={lang === l.code ? "on" : ""} lang={l.code}>
            <input type="radio" name="lang" checked={lang === l.code} onChange={() => setLang(l.code)} />
            {l.name}
          </label>
        ))}
      </fieldset>

      <div className="panel form">
        <label className="switch">
          <span>{t("shake_setting")}</span>
          <input type="checkbox" checked={settings.shake}
            onChange={(e) => setSettings({ ...settings, shake: e.target.checked })} />
        </label>
        <label className="switch">
          <span>{t("siren_setting")}</span>
          <input type="checkbox" checked={settings.sirenAuto}
            onChange={(e) => setSettings({ ...settings, sirenAuto: e.target.checked })} />
        </label>
      </div>

      <div className="panel form">
        <label>
          <span className="field-label">{t("server")}</span>
          <input value={server} placeholder={defaultApiBase} onChange={(e) => { setServer(e.target.value); setSaved(false); }}
            inputMode="url" autoCapitalize="off" />
        </label>
        <button className="btn btn-ghost" onClick={() => { setSettings({ ...settings, server: server.trim() }); setSaved(true); }}>
          {saved ? t("saved") : t("save")}
        </button>
      </div>
    </div>
  );
}
