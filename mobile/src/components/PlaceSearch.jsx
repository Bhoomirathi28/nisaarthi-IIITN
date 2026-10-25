import { useEffect, useRef, useState } from "react";
import { useT } from "../i18n";
import { api } from "../api";
import ConfidenceChip from "./ConfidenceChip";
import { recentPlaces, rememberPlace } from "../lib/places";

const WAIT_MS = 300;
const MIN_CHARS = 3;

// One search box with a dropdown of suggestions. "Choose on map" is always the last option,
// for addresses search can't find. `topOption` adds an extra first row (e.g. "Use my current location").
export default function PlaceSearch({ id, label, display, near, onSelect, onChooseMap, topOption, onRemove, removeLabel }) {
  const { t } = useT();
  const [text, setText] = useState(display || "");
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | searching | done | offline
  const reqId = useRef(0);

  // Show the chosen place when the box isn't being edited
  useEffect(() => { if (!open) setText(display || ""); }, [display, open]);

  useEffect(() => {
    if (!open) return;
    const q = text.trim();
    if (q.length < MIN_CHARS || q === display) { setResults([]); setStatus("idle"); return; }
    const myId = ++reqId.current;
    setStatus("searching");
    const timer = setTimeout(async () => {
      try {
        const res = await api.searchPlaces(q, near);
        if (myId === reqId.current) { setResults(res.results); setStatus("done"); }
      } catch {
        // Server unreachable: fall back to places picked before, labelled as saved data
        const low = q.toLowerCase();
        const saved = (await recentPlaces()).filter((p) => p.name?.toLowerCase().includes(low))
          .map((p) => ({ ...p, label: "OUTDATED" }));
        if (myId === reqId.current) { setResults(saved); setStatus("offline"); }
      }
    }, WAIT_MS);
    return () => clearTimeout(timer);
  }, [text, open]);

  const close = () => { setOpen(false); setResults([]); setStatus("idle"); };
  const pick = (p) => { rememberPlace(p); onSelect(p); close(); };
  // Keep focus in the input so the tap lands on the option before the dropdown closes
  const keep = (e) => e.preventDefault();

  return (
    <div className="place-search">
      <label htmlFor={id} className="field-label">{label}</label>
      <div className="place-input">
        <input id={id} type="text" autoComplete="off" placeholder={t("search_place")} value={text}
          onFocus={(e) => { setOpen(true); e.target.select(); }}
          onBlur={close}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Escape" && e.target.blur()} />
        {onRemove && (
          <button type="button" className="icon-btn place-remove" aria-label={removeLabel} onClick={onRemove}>✕</button>
        )}
      </div>
      {open && (
        <ul className="suggestions" role="listbox" aria-label={label}>
          {topOption && (
            <li><button type="button" className="suggestion suggestion-special" onMouseDown={keep}
              onClick={() => { topOption.onPick(); close(); }}>◎ {topOption.label}</button></li>
          )}
          {status === "searching" && <li className="suggestion-note">{t("searching")}</li>}
          {status === "offline" && <li className="suggestion-note">{t("search_offline")}</li>}
          {status === "idle" && text.trim().length < MIN_CHARS && <li className="suggestion-note">{t("type_more")}</li>}
          {(status === "done" || status === "offline") && results.length === 0 && (
            <li className="suggestion-note">{t("no_results")}</li>
          )}
          {results.map((p, i) => (
            <li key={`${p.lat},${p.lon},${i}`}>
              <button type="button" className="suggestion" onMouseDown={keep} onClick={() => pick(p)}>
                <span className="suggestion-text">
                  <span>{p.name}</span>
                  {p.address && <span className="muted small">{p.address}</span>}
                </span>
                {p.label && <ConfidenceChip label={p.label} small />}
              </button>
            </li>
          ))}
          <li><button type="button" className="suggestion suggestion-special" onMouseDown={keep}
            onClick={() => { onChooseMap(); close(); }}>⌖ {t("choose_on_map")}</button></li>
        </ul>
      )}
    </div>
  );
}
