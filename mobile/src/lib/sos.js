import { openUrl } from "./native";

// SMS works without internet: it opens the phone's SMS app with every contact and the
// coordinates filled in. One tap on "send" and it goes over the mobile network.
export function smsUrl(contacts, body) {
  const numbers = contacts.map((c) => c.phone.replace(/[^\d+]/g, "")).join(",");
  return `sms:${numbers}?body=${encodeURIComponent(body)}`;
}

export function sendSosSms(contacts, body) {
  return openUrl(smsUrl(contacts, body));
}

export function call(number) {
  return openUrl(`tel:${number}`);
}

// Loud two-tone siren made with Web Audio, so no sound file is needed and it works offline.
let ctx = null;
let nodes = null;

export function startSiren() {
  if (nodes) return;
  ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
  ctx.resume();
  const osc = ctx.createOscillator();
  const lfo = ctx.createOscillator();
  const lfoGain = ctx.createGain();
  const gain = ctx.createGain();
  osc.type = "sawtooth";
  osc.frequency.value = 950;
  lfo.type = "triangle";
  lfo.frequency.value = 1.6; // sweeps up and down
  lfoGain.gain.value = 420;
  gain.gain.value = 1.0;
  lfo.connect(lfoGain).connect(osc.frequency);
  osc.connect(gain).connect(ctx.destination);
  osc.start();
  lfo.start();
  nodes = { osc, lfo };
  if (navigator.vibrate) navigator.vibrate([600, 200, 600, 200, 600, 200, 600]);
}

export function stopSiren() {
  if (!nodes) return;
  nodes.osc.stop();
  nodes.lfo.stop();
  nodes = null;
  if (navigator.vibrate) navigator.vibrate(0);
}

export const sirenPlaying = () => nodes !== null;
