import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";

// Korean 2-set (Dubeolsik) key trainer
// New features:
// - Phonetic cue under the main jamo (concise ASCII-friendly articulation hint)
// - Adaptive selection: on a miss, the next items pull from the jamo's confusability class
// - Syllable mode: practice full Hangul blocks; strict legality toggle
// - Keystroke trace (live ASCII of typed keys)
// - Syllable buildup indicator (초/중/종 fade-in as segments complete)
// Existing:
// - Space = Next when paused; separate toggles for compound vowels vs final clusters
// - Keyboard labels toggle hides BOTH main labels and shifted badges during attempt
// - Inline Yale (with diacritics) per Jamo; full 51-item inventory

// Types

type Jamo = {
  char: string;
  key?: string;         // single key (lowercase a-z)
  keySeq?: string[];    // multi-key sequence for compounds/clusters
  name: string;         // Korean name
  rr: string;           // Revised Romanization cue
  yale: string;         // Yale romanization (display; canonical; diacritics allowed)
  type: "consonant" | "vowel";
  requiresShift?: boolean; // for doubled consonants or single-key shifted vowels
};

// Cluster set for filtering
const CLUSTER_CHARS = new Set([
  "ㄳ","ㄵ","ㄶ","ㄺ","ㄻ","ㄼ","ㄽ","ㄾ","ㄿ","ㅀ","ㅄ"
]);

// QWERTY -> Jamo labels for overlay (unshifted)
const KEY_TO_JAMO: Record<string, string> = {
  q: "ㅂ", w: "ㅈ", e: "ㄷ", r: "ㄱ", t: "ㅅ",
  y: "ㅛ", u: "ㅕ", i: "ㅑ", o: "ㅐ", p: "ㅔ",
  a: "ㅁ", s: "ㄴ", d: "ㅇ", f: "ㄹ", g: "ㅎ",
  h: "ㅗ", j: "ㅓ", k: "ㅏ", l: "ㅣ",
  z: "ㅋ", x: "ㅌ", c: "ㅊ", v: "ㅍ", b: "ㅠ", n: "ㅜ", m: "ㅡ",
};
// Shifted badges for overlay (ALWAYS available as alternates; visibility respects label toggle)
const SHIFT_BADGE: Record<string, string> = {
  q: "ㅃ", w: "ㅉ", e: "ㄸ", r: "ㄲ", t: "ㅆ", o: "ㅒ", p: "ㅖ"
};

// 2-set mapping inventory (51) with inlined Yale (canonical)
const JAMO: Jamo[] = [
  // Consonants (single)
  { char: "ㄱ", key: "r", name: "기역", rr: "g/k", yale: "k", type: "consonant" },
  { char: "ㄴ", key: "s", name: "니은", rr: "n", yale: "n", type: "consonant" },
  { char: "ㄷ", key: "e", name: "디귿", rr: "d/t", yale: "t", type: "consonant" },
  { char: "ㄹ", key: "f", name: "리을", rr: "r/l", yale: "l", type: "consonant" },
  { char: "ㅁ", key: "a", name: "미음", rr: "m", yale: "m", type: "consonant" },
  { char: "ㅂ", key: "q", name: "비읍", rr: "b/p", yale: "p", type: "consonant" },
  { char: "ㅅ", key: "t", name: "시옷", rr: "s", yale: "s", type: "consonant" },
  { char: "ㅇ", key: "d", name: "이응", rr: "ng/0", yale: "ng/Ø", type: "consonant" },
  { char: "ㅈ", key: "w", name: "지읒", rr: "j", yale: "c", type: "consonant" },
  { char: "ㅊ", key: "c", name: "치읓", rr: "ch", yale: "ch", type: "consonant" },
  { char: "ㅋ", key: "z", name: "키읔", rr: "k", yale: "kh", type: "consonant" },
  { char: "ㅌ", key: "x", name: "티읕", rr: "t", yale: "th", type: "consonant" },
  { char: "ㅍ", key: "v", name: "피읖", rr: "p", yale: "ph", type: "consonant" },
  { char: "ㅎ", key: "g", name: "히읗", rr: "h", yale: "h", type: "consonant" },
  // Consonants (double via Shift)
  { char: "ㄲ", key: "r", name: "쌍기역", rr: "kk", yale: "kk", type: "consonant", requiresShift: true },
  { char: "ㄸ", key: "e", name: "쌍디귿", rr: "tt", yale: "tt", type: "consonant", requiresShift: true },
  { char: "ㅃ", key: "q", name: "쌍비읍", rr: "pp", yale: "pp", type: "consonant", requiresShift: true },
  { char: "ㅆ", key: "t", name: "쌍시옷", rr: "ss", yale: "ss", type: "consonant", requiresShift: true },
  { char: "ㅉ", key: "w", name: "쌍지읒", rr: "jj", yale: "cc", type: "consonant", requiresShift: true },
  // Vowels (single key)
  { char: "ㅏ", key: "k", name: "아", rr: "a", yale: "a", type: "vowel" },
  { char: "ㅐ", key: "o", name: "애", rr: "ae", yale: "ay", type: "vowel" },
  { char: "ㅑ", key: "i", name: "야", rr: "ya", yale: "ya", type: "vowel" },
  { char: "ㅓ", key: "j", name: "어", rr: "eo", yale: "e", type: "vowel" },
  { char: "ㅔ", key: "p", name: "에", rr: "e", yale: "ey", type: "vowel" },
  { char: "ㅕ", key: "u", name: "여", rr: "yeo", yale: "ye", type: "vowel" },
  { char: "ㅗ", key: "h", name: "오", rr: "o", yale: "o", type: "vowel" },
  { char: "ㅛ", key: "y", name: "요", rr: "yo", yale: "yo", type: "vowel" },
  { char: "ㅜ", key: "n", name: "우", rr: "u", yale: "wu", type: "vowel" },
  { char: "ㅠ", key: "b", name: "유", rr: "yu", yale: "ywu", type: "vowel" },
  { char: "ㅡ", key: "m", name: "으", rr: "eu", yale: "u", type: "vowel" },
  { char: "ㅣ", key: "l", name: "이", rr: "i", yale: "i", type: "vowel" },
  // Vowels (single key, shifted)
  { char: "ㅒ", key: "o", name: "얘", rr: "yae", yale: "yay", type: "vowel", requiresShift: true },
  { char: "ㅖ", key: "p", name: "예", rr: "ye", yale: "ye", type: "vowel", requiresShift: true },
  // Vowels (compound sequences)
  { char: "ㅘ", keySeq: ["h", "k"], name: "와", rr: "wa", yale: "wa", type: "vowel" },
  { char: "ㅙ", keySeq: ["h", "o"], name: "왜", rr: "wae", yale: "way", type: "vowel" },
  { char: "ㅚ", keySeq: ["h", "l"], name: "외", rr: "oe", yale: "oy", type: "vowel" },
  { char: "ㅝ", keySeq: ["n", "j"], name: "워", rr: "wo", yale: "wŏ", type: "vowel" },
  { char: "ㅞ", keySeq: ["n", "p"], name: "웨", rr: "we", yale: "wĕy", type: "vowel" },
  { char: "ㅟ", keySeq: ["n", "l"], name: "위", rr: "wi", yale: "wi", type: "vowel" },
  { char: "ㅢ", keySeq: ["m", "l"], name: "의", rr: "ui/ei", yale: "ŭy", type: "vowel" },
  // Final-consonant clusters (받침 합용, two-key sequences)
  { char: "ㄳ", keySeq: ["r", "t"], name: "기역시옷", rr: "gs", yale: "ks", type: "consonant" },
  { char: "ㄵ", keySeq: ["s", "w"], name: "니은지읒", rr: "nj", yale: "nc", type: "consonant" },
  { char: "ㄶ", keySeq: ["s", "g"], name: "니은히읗", rr: "nh", yale: "nh", type: "consonant" },
  { char: "ㄺ", keySeq: ["f", "r"], name: "리을기역", rr: "lg", yale: "lk", type: "consonant" },
  { char: "ㄻ", keySeq: ["f", "a"], name: "리을미음", rr: "lm", yale: "lm", type: "consonant" },
  { char: "ㄼ", keySeq: ["f", "q"], name: "리을비읍", rr: "lb", yale: "lp", type: "consonant" },
  { char: "ㄽ", keySeq: ["f", "t"], name: "리을시옷", rr: "ls", yale: "ls", type: "consonant" },
  { char: "ㄾ", keySeq: ["f", "x"], name: "리을티읕", rr: "lt", yale: "lt", type: "consonant" },
  { char: "ㄿ", keySeq: ["f", "v"], name: "리을피읖", rr: "lp", yale: "lp'", type: "consonant" },
  { char: "ㅀ", keySeq: ["f", "g"], name: "리을히읗", rr: "lh", yale: "lh", type: "consonant" },
  { char: "ㅄ", keySeq: ["q", "t"], name: "비읍시옷", rr: "bs", yale: "ps", type: "consonant" },
];

// === Phonetic micro-cues (ASCII-friendly, ultra-short) ===
const PHON_CUE: Record<string, string> = {
  // consonants
  "ㄱ": "k (unasp)", "ㄲ": "kk (tense)", "ㅋ": "kʰ (asp)",
  "ㄷ": "t (unasp)", "ㄸ": "tt (tense)", "ㅌ": "tʰ (asp)",
  "ㅂ": "p (unasp)", "ㅃ": "pp (tense)", "ㅍ": "pʰ (asp)",
  "ㅅ": "s", "ㅆ": "s (tense)", "ㅈ": "c (unasp)", "ㅉ": "cc (tense)", "ㅊ": "ch (asp)",
  "ㅎ": "h", "ㄴ": "n", "ㅁ": "m", "ㄹ": "r/l", "ㅇ": "∅/ng",
  // vowels
  "ㅏ": "a (father)", "ㅐ": "ay (bed)", "ㅑ": "ya",
  "ㅓ": "e (uh)", "ㅔ": "ey (ay)", "ㅕ": "ye",
  "ㅗ": "o (close)", "ㅛ": "yo",
  "ㅜ": "wu (rounded)", "ㅠ": "ywu",
  "ㅡ": "ɯ (barred u)", "ㅣ": "i",
  "ㅘ": "wa", "ㅙ": "way", "ㅚ": "oy",
  "ㅝ": "wŏ", "ㅞ": "wĕy", "ㅟ": "wi", "ㅢ": "ŭy",
  // clusters (coda-only): keep mnemonic
  "ㄳ": "k+s", "ㄵ": "n+c", "ㄶ": "n+h", "ㄺ": "l+k", "ㄻ": "l+m",
  "ㄼ": "l+p", "ㄽ": "l+s", "ㄾ": "l+t", "ㄿ": "l+p'", "ㅀ": "l+h", "ㅄ": "p+s",
};

// === Confusability classes ===
// Groups that learners commonly confuse; we will focus-sample from these after a miss.
const CONFUSABLES: string[][] = [
  ["ㄱ","ㅋ","ㄲ"], ["ㄷ","ㅌ","ㄸ"], ["ㅂ","ㅍ","ㅃ"], ["ㅈ","ㅊ","ㅉ"], ["ㅅ","ㅆ"],
  ["ㅐ","ㅔ","ㅒ","ㅖ"],
  ["ㅗ","ㅜ"],
  ["ㅘ","ㅙ","ㅚ"],
  ["ㅝ","ㅞ","ㅟ"],
  ["ㅡ","ㅓ","ㅗ"],
];
const CONFUSABLE_INDEX: Record<string, Set<string>> = (() => {
  const map: Record<string, Set<string>> = {};
  for (const group of CONFUSABLES) {
    for (const a of group) {
      if (!map[a]) map[a] = new Set();
      for (const b of group) if (b !== a) map[a].add(b);
    }
  }
  return map;
})();

// --- Hangul composition tables (Unicode algorithm) ---
const L_TABLE = [
  "ㄱ","ㄲ","ㄴ","ㄷ","ㄸ","ㄹ","ㅁ","ㅂ","ㅃ","ㅅ","ㅆ","ㅇ","ㅈ","ㅉ","ㅊ","ㅋ","ㅌ","ㅍ","ㅎ"
];
const V_TABLE = [
  "ㅏ","ㅐ","ㅑ","ㅒ","ㅓ","ㅔ","ㅕ","ㅖ","ㅗ","ㅘ","ㅙ","ㅚ","ㅛ","ㅜ","ㅝ","ㅞ","ㅟ","ㅠ","ㅡ","ㅢ","ㅣ"
];
const T_TABLE = [
  "", "ㄱ","ㄲ","ㄳ","ㄴ","ㄵ","ㄶ","ㄷ","ㄹ","ㄺ","ㄻ","ㄼ","ㄽ","ㄾ","ㄿ","ㅀ","ㅁ","ㅂ","ㅄ","ㅅ","ㅆ","ㅇ","ㅈ","ㅊ","ㅋ","ㅌ","ㅍ","ㅎ"
];
const SBase = 0xac00; // '가'
const NCount = 588;   // VCount * TCount
const TCount = 28;
function composeHangulBlock(L: string, V: string, T?: string | null): string {
  const l = L_TABLE.indexOf(L);
  const v = V_TABLE.indexOf(V);
  const t = T ? T_TABLE.indexOf(T) : 0;
  if (l < 0 || v < 0 || t < 0) return L + V + (T || "");
  const code = SBase + l * NCount + v * TCount + t;
  return String.fromCharCode(code);
}

function keysOf(j: Jamo): string[] { return j.keySeq ?? (j.key ? [j.key] : []); }
function shiftSeqOf(j: Jamo): boolean[] {
  const seq = keysOf(j);
  if (seq.length === 1) return [!!j.requiresShift];
  return seq.map(() => false);
}
function labelForSeq(seq: string[], shiftSeq: boolean[]): string {
  return seq.map((k, i) => (shiftSeq[i] ? "Shift+" + k.toUpperCase() : k.toUpperCase())).join(" + ");
}

// Weighted sampler for spaced drilling
function weightedChoice<T>(items: T[], weights: number[]) {
  const total = weights.reduce((a, b) => a + b, 0);
  let r = Math.random() * total;
  for (let i = 0; i < items.length; i++) {
    r -= weights[i];
    if (r <= 0) return i;
  }
  return items.length - 1;
}

export default function KoreanKeyTrainer() {
  const MODES = ["both", "consonant", "vowel", "syllable"] as const;
  const ROWS: string[] = ["qwertyuiop", "asdfghjkl", "zxcvbnm"];

  // Strict syllable generation (legal 초/중/종 only)
  const ALLOWED_INITIAL = new Set(L_TABLE);
  const ALLOWED_MEDIAL = new Set(V_TABLE);
  const ALLOWED_CODA = new Set(T_TABLE.slice(1)); // non-empty codas only


  const [mode, setMode] = useState<(typeof MODES)[number]>("both");
  const [includeDoubles, setIncludeDoubles] = useState(true);
  const [includeCompoundVowels, setIncludeCompoundVowels] = useState(true);
  const [includeFinalClusters, setIncludeFinalClusters] = useState(true);
  const [activeIdx, setActiveIdx] = useState(0);
  const [progress, setProgress] = useState(0);
  const [streak, setStreak] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [attempts, setAttempts] = useState(0);
  const [lastFeedback, setLastFeedback] = useState<string | null>(null);
  const [weights, setWeights] = useState<number[]>(() => JAMO.map(() => 1));
  const [showHighlights, setShowHighlights] = useState(false); // highlight overlay only after an attempt
  const [awaitNext, setAwaitNext] = useState(false); // pause before advancing
  const [hideLabelsDuringAttempt, setHideLabelsDuringAttempt] = useState(true); // toggle
  const [strictSyllables, setStrictSyllables] = useState(true);
  const [typedSeq, setTypedSeq] = useState<string[]>([]); // NEW: live keystroke trace

  // Adaptive focus queue (indices into JAMO)
  const [focusQueue, setFocusQueue] = useState<number[]>([]);

  // Syllable mode target
  const [syllableTarget, setSyllableTarget] = useState<{ L: Jamo; V: Jamo; T: Jamo | null } | null>(null);

  const isCompoundVowel = (j: Jamo) => j.type === "vowel" && Array.isArray(j.keySeq) && j.keySeq.length > 1;
  const isFinalCluster = (j: Jamo) => CLUSTER_CHARS.has(j.char);
  // keysOf moved above with shift tracking helpers

  const pool = useMemo(() => {
    if (mode === "syllable") return [] as Jamo[]; // handled separately
    return JAMO.filter(j =>
      (mode === "both" || j.type === mode) &&
      ((includeDoubles || !j.requiresShift) || j.type === "vowel") &&
      (includeCompoundVowels || !(j.type === "vowel" && Array.isArray(j.keySeq) && j.keySeq.length > 1)) &&
      (includeFinalClusters || !CLUSTER_CHARS.has(j.char))
    );
  }, [mode, includeDoubles, includeCompoundVowels, includeFinalClusters]);

  const poolIndices = useMemo(() => pool.map(j => JAMO.indexOf(j)), [pool]);
  const weightsForPool = useMemo(() => poolIndices.map(i => weights[i]), [poolIndices, weights]);

  const pickNext = () => {
    setTypedSeq([]); // clear keystroke trace whenever a new target is picked
    if (mode === "syllable") {
      // Choose onset (consonant), vowel, optional coda (consonant or cluster)
      const onsetPool = JAMO.filter(j => j.type === "consonant" && !CLUSTER_CHARS.has(j.char) && (includeDoubles || !j.requiresShift) && (!strictSyllables || ALLOWED_INITIAL.has(j.char)));
      const vowelPool = JAMO.filter(j => j.type === "vowel" && (includeCompoundVowels || !(j.keySeq && j.keySeq.length > 1)) && (!strictSyllables || ALLOWED_MEDIAL.has(j.char)));
      const codaCandidates = JAMO.filter(j => j.type === "consonant" && (!strictSyllables || ALLOWED_CODA.has(j.char)));
      const codaPool = includeFinalClusters ? codaCandidates : codaCandidates.filter(j => !CLUSTER_CHARS.has(j.char));
      const L = onsetPool[Math.floor(Math.random() * onsetPool.length)];
      const V = vowelPool[Math.floor(Math.random() * vowelPool.length)];
      const wantCoda = Math.random() < 0.5;
      const T = wantCoda && codaPool.length > 0 ? codaPool[Math.floor(Math.random() * codaPool.length)] : null;
      setSyllableTarget({ L, V, T });
      setProgress(0);
      setShowHighlights(false);
      setAwaitNext(false);
      setLastFeedback(null);
      return;
    }
    // consume focusQueue first, but ensure it's still in pool
    while (focusQueue.length > 0) {
      const idx = focusQueue[0];
      if (poolIndices.includes(idx)) {
        setActiveIdx(idx);
        setFocusQueue(q => q.slice(1));
        setProgress(0);
        setShowHighlights(false);
        setAwaitNext(false);
        return;
      } else {
        setFocusQueue(q => q.slice(1));
      }
    }
    if (pool.length === 0) return;
    const localIdx = weightedChoice(pool, weightsForPool);
    setActiveIdx(poolIndices[localIdx]);
    setProgress(0);
    setShowHighlights(false);
    setAwaitNext(false);
  };

  useEffect(() => { pickNext(); }, [mode, includeDoubles, includeCompoundVowels, includeFinalClusters]);

  const expected = mode === "syllable" ? null : JAMO[activeIdx];
  const expectedSeqRaw: string[] = useMemo(() => {
    if (mode === "syllable") {
      if (!syllableTarget) return [];
      const parts = [syllableTarget.L, syllableTarget.V].concat(syllableTarget.T ? [syllableTarget.T] : []);
      return parts.flatMap(j => keysOf(j));
    }
    return expected ? keysOf(expected) : [];
  }, [mode, expected, syllableTarget]);
  const expectedShiftSeq: boolean[] = useMemo(() => {
    if (mode === "syllable") {
      if (!syllableTarget) return [];
      const parts = [syllableTarget.L, syllableTarget.V].concat(syllableTarget.T ? [syllableTarget.T] : []);
      return parts.flatMap(j => shiftSeqOf(j));
    }
    return expected ? shiftSeqOf(expected) : [];
  }, [mode, expected, syllableTarget]);
  const expectedSeq = expectedSeqRaw;

  // --- Syllable assembly progress (for visual buildup) ---
  const syllPartSeqs = useMemo(() => {
    if (mode !== "syllable" || !syllableTarget) return [] as string[][];
    return [keysOf(syllableTarget.L), keysOf(syllableTarget.V), syllableTarget.T ? keysOf(syllableTarget.T) : []];
  }, [mode, syllableTarget]);
  const syllPartLens = useMemo(() => syllPartSeqs.map(s => s.length), [syllPartSeqs]);
  const syllDoneFlags = useMemo(() => {
    if (mode !== "syllable" || !syllableTarget) return { L: false, V: false, T: false } as const;
    const l = syllPartLens[0] ?? 0;
    const v = syllPartLens[1] ?? 0;
    const t = syllPartLens[2] ?? 0;
    const p = progress;
    return {
      L: p >= l,
      V: p >= l + v,
      T: t > 0 ? p >= l + v + t : false,
    } as const;
  }, [mode, syllableTarget, syllPartLens, progress]);

  // Expected keys label for feedback (explicit)
  const expectedKeysLabel = useMemo(() => {
    if (mode === "syllable") return labelForSeq(expectedSeq, expectedShiftSeq);
    if (!expected) return "";
    return labelForSeq(expectedSeq, expectedShiftSeq);
  }, [mode, expected, expectedSeq, expectedShiftSeq]);

  // Add confusables to queue (intersected with current pool)
  const enqueueConfusables = (char: string) => {
    const confSet = CONFUSABLE_INDEX[char];
    if (!confSet) return;
    const candidates = Array.from(confSet)
      .map(c => JAMO.findIndex(j => j.char === c))
      .filter(i => i >= 0 && poolIndices.includes(i));
    if (candidates.length === 0) return;
    setFocusQueue(q => {
      const next = [...q];
      for (const i of candidates) if (!next.includes(i)) next.push(i);
      // cap queue to avoid long detours
      return next.slice(0, 6);
    });
  };

  // Keyboard input + Space-to-next handler
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const isSyll = mode === "syllable";
      if (!isSyll && !expected) return;

      // If paused, allow Space to advance
      if (awaitNext) {
        if (e.code === "Space" || e.key === " ") {
          e.preventDefault();
          setLastFeedback(null);
          pickNext();
        }
        return; // ignore other keys while paused
      }

      // Ignore pure modifiers
      if (e.key === "Shift" || e.key === "Alt" || e.key === "Meta" || e.key === "Control") return;
      // Letters only
      const pressed = e.key.length === 1 ? e.key.toLowerCase() : "";
      if (!/^[a-z]$/.test(pressed)) return;

      // Step-wise check with shift requirement
      const needShift = expectedShiftSeq[progress] || false;
      const expectedKey = expectedSeq[progress];

      // Update visible keystroke trace
      setTypedSeq(ts => [...ts, needShift ? pressed.toUpperCase() : pressed]);

      if (pressed === expectedKey && (!needShift || e.shiftKey)) {
        const nextProgress = progress + 1;
        if (nextProgress === expectedSeq.length) {
          setAttempts(a => a + 1);
          setCorrect(c => c + 1);
          setStreak(s => s + 1);
          const label = isSyll ? "OK: " + renderSyllableBlock() + " — " + expectedKeysLabel : ("OK: " + (expected?.char || "") + " — " + expectedKeysLabel);
          setLastFeedback(label);
          if (!isSyll) setWeights(ws => ws.map((w, i) => (i === activeIdx ? Math.max(0.5, w * 0.9) : w)));
          setShowHighlights(true);
          setAwaitNext(true);
        } else {
          setProgress(nextProgress);
        }
      } else {
        setAttempts(a => a + 1);
        setStreak(0);
        const shiftHint = needShift && !e.shiftKey ? " (needs Shift)" : "";
        const label = isSyll ? ("X: " + renderSyllableBlock() + " — " + expectedKeysLabel + shiftHint + " at step " + (progress + 1)) : ("X: " + (expected?.char || "") + " — " + expectedKeysLabel + shiftHint + (expectedSeq.length > 1 ? " at step " + (progress + 1) : ""));
        setLastFeedback(label);
        if (!isSyll) {
          setWeights(ws => ws.map((w, i) => (i === activeIdx ? Math.min(10, w + 0.6) : w)));
          enqueueConfusables(expected!.char);
        }
        setProgress(0);
        setShowHighlights(true);
        setAwaitNext(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeIdx, expected, progress, expectedSeq, expectedKeysLabel, awaitNext, poolIndices, expectedShiftSeq]);

  // Per-jamo stats
  const [acc, setAcc] = useState<Record<number, { c: number; a: number }>>({});
  useEffect(() => {
    if (!expected || lastFeedback == null) return;
    const isOk = lastFeedback.startsWith("OK:");
    setAcc(prev => {
      const i = activeIdx;
      const p = prev[i] || { c: 0, a: 0 };
      return { ...prev, [i]: { c: p.c + (isOk ? 1 : 0), a: p.a + 1 } };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastFeedback]);

  const accuracy = attempts ? Math.round((100 * correct) / attempts) : 0;

  // Highlight policy: only after attempt
  function isHighlightedKey(ch: string): boolean {
    if (!showHighlights) return false;
    return expectedSeq.includes(ch);
  }

  // Label visibility: if paused => always show; else depends on toggle
  const shouldShowKeyLabels = (paused: boolean) => paused || !hideLabelsDuringAttempt;

  /*
  // Self-tests (act like unit tests)
  const [selfTests, setSelfTests] = useState<string[]>([]);
  useEffect(() => {
    const msgs: string[] = [];
    const assert = (cond: boolean, msg: string) => msgs.push(cond ? "PASS: " + msg : "FAIL: " + msg);

    // 1) Complete count
    assert(JAMO.length === 51, "Contains 51 training targets");
    // 2) Mapping presence
    assert(JAMO.every(j => j.key || (j.keySeq && j.keySeq.length > 0)), "All jamo have a mapping");
    // 3) keySeq length validity
    assert(JAMO.filter(j => j.keySeq).every(j => (j.keySeq as string[]).length >= 1), "keySeq length >= 1 for sequences");
    // 4) requiresShift implies single-key
    assert(JAMO.filter(j => j.requiresShift).every(j => !j.keySeq || j.keySeq.length === 1), "Shift items are single-key");
    // 5) Yale diacritics checks for specific vowels
    const yMap = new Map(JAMO.map(j => [j.char, j.yale]));
    assert(yMap.get("ㅝ") === "wŏ", "ㅝ uses wŏ");
    assert(yMap.get("ㅞ") === "wĕy", "ㅞ uses wĕy");
    assert(yMap.get("ㅢ") === "ŭy", "ㅢ uses ŭy");
    assert(yMap.get("ㅜ") === "wu" && yMap.get("ㅠ") === "ywu", "ㅜ/ㅠ use wu/ywu");
    // 6) Confusables index coverage for a few reps
    assert(["ㄱ","ㅐ","ㅗ"].every(ch => !!CONFUSABLE_INDEX[ch]), "Confusables index seeded");
    // 7) Cluster set size
    assert(CLUSTER_CHARS.size === 11, "Cluster set has 11 entries");
    // 8) Label-hiding policy sanity: when paused, labels show
    const pausedShow = true;
    assert((pausedShow || !true) === true, "Keyboard labels show while paused");
    // 9) Hangul composition sanity
    assert(composeHangulBlock("ㄱ","ㅏ") === "가", "Compose ㄱ+ㅏ => 가");
    assert(composeHangulBlock("ㄱ","ㅏ","ㅂ") === "갑", "Compose ㄱ+ㅏ+ㅂ => 갑");
    // 10) Labeling sanity
    assert(labelForSeq(["r","k"], [false,false]) === "R + K", "Label seq rk => R + K");

    setSelfTests(msgs);
  }, []);
  */

  function renderSyllableBlock(): string {
    if (!syllableTarget) return "";
    return composeHangulBlock(syllableTarget.L.char, syllableTarget.V.char, syllableTarget.T?.char ?? undefined);
  }

  return (
    <div className="min-h-screen w-full bg-neutral-950 text-neutral-100 flex flex-col items-center p-6">
      <div className="max-w-3xl w-full">
        <header className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold tracking-tight">Keyboard Practice</h1>
          <div className="text-sm text-neutral-400">두벌식</div>
        </header>

        <section className="grid md:grid-cols-3 gap-4 mb-6">
          {/* Controls */}
          <div className="p-4 rounded-2xl bg-neutral-900 border border-neutral-800">
            <div className="text-xs uppercase tracking-widest text-neutral-400 mb-2">Mode</div>
            <div className="flex flex-wrap gap-2">
              {(["both", "consonant", "vowel", "syllable"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={("px-3 py-1.5 rounded-xl border ") + (mode === m ? "bg-neutral-800 border-neutral-600" : "border-neutral-800 hover:bg-neutral-900")}
                >{m}</button>
              ))}
            </div>
            <label className="flex items-center gap-2 mt-3 text-sm">
              <input type="checkbox" checked={includeDoubles} onChange={e => setIncludeDoubles(e.target.checked)} />
              Include double consonants (Shift)
            </label>
            <label className="flex items-center gap-2 mt-2 text-sm">
              <input type="checkbox" checked={includeCompoundVowels} onChange={e => setIncludeCompoundVowels(e.target.checked)} />
              Include compound vowels (e.g., ㅘ, ㅙ, ㅚ, ㅝ, ㅞ, ㅟ, ㅢ)
            </label>
            <label className="flex items-center gap-2 mt-2 text-sm">
              <input type="checkbox" checked={includeFinalClusters} onChange={e => setIncludeFinalClusters(e.target.checked)} />
              Include final-consonant clusters (e.g., ㄳ, ㄵ, ㄶ, ...)
            </label>
            {mode === "syllable" && (
              <label className="flex items-center gap-2 mt-2 text-sm">
                <input type="checkbox" checked={strictSyllables} onChange={e => setStrictSyllables(e.target.checked)} />
                Strict syllables (legal 초/중/종 only)
              </label>
            )}
          </div>

          {/* Session stats */}
          <div className="p-4 rounded-2xl bg-neutral-900 border border-neutral-800">
            <div className="text-xs uppercase tracking-widest text-neutral-400 mb-2">Session</div>
            <div className="text-lg">Accuracy: <span className="font-semibold">{accuracy}%</span></div>
            <div className="text-lg">Streak: <span className="font-semibold">{streak}</span></div>
            <div className="text-sm text-neutral-400">Attempts: {attempts} · Correct: {correct}</div>
          </div>

          {/* Hint */}
          <div className="p-4 rounded-2xl bg-neutral-900 border border-neutral-800">
            <div className="text-xs uppercase tracking-widest text-neutral-400 mb-2">Hint</div>
            {mode !== "syllable" && expected && (
              <div className="text-sm leading-relaxed">
                <div><span className="text-neutral-400">Name:</span> {expected.name}</div>
                <div><span className="text-neutral-400">Romanization (RR):</span> {expected.rr}</div>
                <div><span className="text-neutral-400">Romanization (Yale):</span> {expected.yale}</div>
                <div>
                  <span className="text-neutral-400">Type:</span> {expected.type}
                  {expected.requiresShift && (!expected.keySeq || expected.keySeq.length === 1) ? " • requires Shift" : ""}
                  {expected.keySeq && expected.keySeq.length > 1 ? (" • " + expected.keySeq.length + "-key sequence") : ""}
                </div>
              </div>
            )}
            {mode === "syllable" && syllableTarget && (
              <div className="text-sm leading-relaxed">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-neutral-400 text-xs">Initial (초성)</div>
                    <div className="text-lg">{syllableTarget.L.char}</div>
                    <div className="text-xs text-neutral-400">RR: {syllableTarget.L.rr}</div>
                  </div>
                  <div>
                    <div className="text-neutral-400 text-xs">Vowel (중성)</div>
                    <div className="text-lg">{syllableTarget.V.char}</div>
                    <div className="text-xs text-neutral-400">RR: {syllableTarget.V.rr}</div>
                  </div>
                  {syllableTarget.T && (
                    <div className="col-span-2">
                      <div className="text-neutral-400 text-xs">Final (종성)</div>
                      <div className="text-lg">{syllableTarget.T.char}</div>
                      <div className="text-xs text-neutral-400">RR: {syllableTarget.T.rr}</div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </section>

        <main className="rounded-3xl border border-neutral-800 bg-neutral-900 p-8 flex flex-col items-center gap-4">
          <div className="text-8xl md:text-[10rem] leading-none font-semibold">
            {mode === "syllable" && syllableTarget ? renderSyllableBlock() : (expected ? expected.char : "")}
          </div>
          {/* Phonetic cue directly under main jamo or combined guide */}
          <div className="text-sm text-neutral-400 h-5">
            {mode !== "syllable" ? (expected ? (PHON_CUE[expected.char] || "") : "") : (
              syllableTarget ? (syllableTarget.L.rr + "-" + syllableTarget.V.rr + (syllableTarget.T ? ("-" + syllableTarget.T.rr) : "")) : ""
            )}
          </div>
          {mode === "syllable" && syllableTarget && (
            <div className="text-sm text-neutral-400">
              <span className={syllDoneFlags.L ? "text-neutral-100" : "opacity-50"}>{syllableTarget.L.char}</span>
              <span className="mx-1">·</span>
              <span className={syllDoneFlags.V ? "text-neutral-100" : "opacity-50"}>{syllableTarget.V.char}</span>
              {syllableTarget.T && (
                <>
                  <span className="mx-1">·</span>
                  <span className={syllDoneFlags.T ? "text-neutral-100" : "opacity-50"}>{syllableTarget.T.char}</span>
                </>
              )}
            </div>
          )}
          <div className="text-neutral-400">Press the corresponding key{expectedSeq.length > 1 ? " sequence" : ""} on your English keyboard.</div>
          {typedSeq.length > 0 && !awaitNext && (
            <div className="text-xs text-neutral-500 font-mono">Typed: {typedSeq.join(" + ")}</div>
          )}
          {lastFeedback ? (
            <div className={("text-lg font-medium ") + (lastFeedback.startsWith("OK:") ? "text-emerald-400" : "text-rose-400")}>{lastFeedback}</div>
          ) : null}
          <div className="flex gap-2">
            <button
              onClick={() => { setStreak(0); setLastFeedback(null); setProgress(0); setFocusQueue([]); pickNext(); }}
              className="px-4 py-2 rounded-xl border border-neutral-800 hover:bg-neutral-800"
            >Skip</button>
            <button
              onClick={() => { if (awaitNext) { setLastFeedback(null); pickNext(); } }}
              disabled={!awaitNext}
              className={("px-4 py-2 rounded-xl border ") + (awaitNext ? "border-neutral-800 hover:bg-neutral-800" : "border-neutral-900 text-neutral-600 cursor-not-allowed")}
            >Next (Space)</button>
            <button
              onClick={() => { setAttempts(0); setCorrect(0); setStreak(0); setLastFeedback(null); setWeights(JAMO.map(() => 1)); setProgress(0); setFocusQueue([]); pickNext(); }}
              className="px-4 py-2 rounded-xl border border-neutral-800 hover:bg-neutral-800"
            >Reset</button>
          </div>
        </main>

        {/* On-screen keyboard overlay with Jamo labels; highlights only AFTER attempt */}
        <section className="mt-6 rounded-3xl border border-neutral-800 bg-neutral-900 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm text-neutral-400">Keyboard overlay</h3>
            <label className="text-xs flex items-center gap-2 text-neutral-400">
              <input type="checkbox" checked={hideLabelsDuringAttempt} onChange={e => setHideLabelsDuringAttempt(e.target.checked)} />
              Hide key labels during attempt
            </label>
          </div>
          <div className="flex flex-col items-center gap-1 select-none">
            {ROWS.map((row, ri) => (
              <div key={ri} className="flex gap-1">
                {row.split("").map((k) => {
                  const base = "relative w-10 h-12 rounded-lg border text-center leading-[3rem] font-mono";
                  const cls = isHighlightedKey(k) ? "bg-emerald-900/40 border-emerald-700" : "bg-neutral-800 border-neutral-700";
                  const label = KEY_TO_JAMO[k] || "\u00A0";
                  const badge = SHIFT_BADGE[k] || "";
                  const show = shouldShowKeyLabels(awaitNext);
                  return (
                    <div key={k} className={base + " " + cls}>
                      {show ? label : "\u00A0"}
                      {show && badge ? (
                        <span className="absolute right-1 top-1 text-[0.6rem] opacity-80">{badge}</span>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ))}
            <div className="flex gap-1 mt-1">
              {[0, 1].map((i) => {
                const show = showHighlights && expected && expected.requiresShift && expectedSeq.length === 1;
                const base = "px-3 h-10 rounded-lg border text-center leading-10 font-mono uppercase";
                const cls = show ? "bg-emerald-900/40 border-emerald-700" : "bg-neutral-800 border-neutral-700";
                return <div key={i} className={base + " " + cls}>shift</div>;
              })}
            </div>
          </div>
        </section>

        <section className="mt-8">
          <h2 className="text-lg font-semibold mb-3">Per-jamo accuracy</h2>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
            {JAMO.filter(j => (
              (mode === "both" || j.type === mode) &&
              (includeDoubles || !j.requiresShift || j.type === "vowel") &&
              (includeCompoundVowels || !isCompoundVowel(j)) &&
              (includeFinalClusters || !isFinalCluster(j))
            )).map(j => {
              const i = JAMO.indexOf(j);
              const stat = acc[i];
              const pct = stat ? Math.round((100 * stat.c) / stat.a) : 0;
              return (
                <div key={i} className="p-2 rounded-xl bg-neutral-900 border border-neutral-800 text-center">
                  <div className="text-2xl">{j.char}</div>
                  <div className="text-xs text-neutral-400 font-mono">{PHON_CUE[j.char] || ""}</div>
                  <div className="text-sm font-medium">{pct}%</div>
                </div>
              );
            })}
          </div>
        </section>

        {/*<section className="mt-8 text-xs text-neutral-500">
          <details>
            <summary>Self-tests</summary>
            <ul className="list-disc pl-5">
              {selfTests.map((m, i) => <li key={i}>{m}</li>)}
            </ul>
          </details>
        </section>*/}

        <footer className="mt-10 text-sm text-neutral-500">
          {/*Phonetic cues pair keypress with sound. After a miss, the trainer temporarily samples from confusable items (e.g., ㅐ/ㅔ/ㅒ/ㅖ; ㄱ/ㅋ/ㄲ) to sharpen contrasts. Press Space to advance when paused.*/}
          Noah Trupin, 2025
        </footer>
      </div>
    </div>
  );
}

if (typeof document !== "undefined") {
  const el = document.getElementById("root") || (() => {
    const d = document.createElement("div");
    d.id = "root";
    document.body.appendChild(d);
    return d;
  })();
  createRoot(el).render(<KoreanKeyTrainer />);
}
