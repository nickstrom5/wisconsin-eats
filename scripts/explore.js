// Wisconsin Eats web app: the iPhone app's guides, search, filters, map and place details, in the browser.
// Same data file as the app (split into core + detail by scripts/make-site.py). No cookies, no trackers;
// saved places and the last guide live in this browser's localStorage only, and the location for "Near me" never leaves the page.
// The page's Content-Security-Policy allows only this inline script (by hash) and same-origin fetches, so: no inline event
// attributes or style attributes in any HTML built here; wire events with properties and toggle classes instead.
(() => {
  "use strict";
  const BASE = document.documentElement.dataset.base || "";
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = {
    get(k, d) { try { const v = localStorage.getItem("we-" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem("we-" + k, JSON.stringify(v)); } catch { /* private mode */ } },
  };
  const own = (o, k) => typeof k === "string" && Object.hasOwn(o, k);   // "constructor" or "__proto__" in a URL is not a guide

  // Links built from data: a website only as http(s) (a bare host gets https://), a phone as tel: with digits and + only.
  function safeSite(u) {
    u = String(u || "").trim();
    if (!u || /[\s"'<>\\`]/.test(u)) return null;
    if (!/^[a-z][a-z0-9+.-]*:/i.test(u)) u = "https://" + u.replace(/^\/+/, "");
    try {
      const x = new URL(u);
      return (x.protocol === "http:" || x.protocol === "https:") && x.hostname.includes(".") ? x.href : null;
    } catch { return null; }
  }
  const telHref = (ph) => { const t = String(ph || "").replace(/[^\d+]/g, ""); return t.replace(/\D/g, "").length >= 10 ? "tel:" + t : null; };
  const num = (x) => (Number.isFinite(+x) ? +x : null);

  // ---------------------------------------------------------------- search (a port of WisconsinEats/Models/Search.swift)
  const typeSyn = { avenue: "ave", av: "ave", street: "st", boulevard: "blvd", road: "rd", drive: "dr", place: "pl", court: "ct",
    parkway: "pkwy", highway: "hwy", lane: "ln", trail: "trl", circle: "cir", terrace: "ter" };
  const syn = { ...typeSyn, north: "n", south: "s", east: "e", west: "w", saint: "st", mount: "mt", fort: "ft" };
  const abbrs = new Set(Object.values(syn)), typeAbbrs = new Set(Object.values(typeSyn));
  const SUPPER = 1, FISHFRY = 2, CURDS = 4, CUSTARD = 8, BOIL = 16;
  const tagPhrases = [["friday fish fry", FISHFRY], ["fish fries", FISHFRY], ["fish fry", FISHFRY], ["fishfry", FISHFRY],
    ["supper clubs", SUPPER], ["supper club", SUPPER], ["supperclub", SUPPER], ["frozen custard", CUSTARD], ["custard", CUSTARD],
    ["fish boil", BOIL], ["cheese curds", CURDS], ["curds", CURDS]];
  function normalize(s) {
    let t = String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    t = t.replace(/\b([a-z0-9])\s*&\s*([a-z0-9])\b/g, "$1$2").replace(/&/g, " and ").replace(/['’`]/g, "");
    return t.replace(/[^\p{L}\p{N}]+/gu, " ").trim();
  }
  const normAddr = (s) => normalize(s).split(" ").map((w) => (own(syn, w) ? syn[w] : w)).join(" ");

  function parse(text) {
    const q = { tokens: [], town: null, townPhrase: null, tag: 0, tagPhrase: null };
    let raw = normalize(text).split(" ").filter(Boolean);
    if (!raw.length) return q;
    let mapped = raw.map((w) => (own(syn, w) ? syn[w] : w));
    const find = (phrase) => {
      const p = phrase.split(" ");
      for (let i = 0; i + p.length <= mapped.length; i++) if (p.every((w, k) => mapped[i + k] === w)) return [i, i + p.length];
      return null;
    };
    const cut = ([a, b]) => { const words = raw.slice(a, b).join(" "); raw.splice(a, b - a); mapped.splice(a, b - a); return words; };
    for (const [phrase, tag] of tagPhrases) { const r = find(normalize(phrase)); if (r) { q.tag = tag; q.tagPhrase = cut(r); break; } }
    for (const key of TOWN_KEYS_BY_LENGTH) {
      const r = find(key);
      if (r && !(r[1] < mapped.length && typeAbbrs.has(mapped[r[1]]))) { q.town = TOWN_KEYS.get(key); q.townPhrase = cut(r); break; }
    }
    const stop = new Set(["the", "and", "of", "a", "in", "near", "me"]);   // "fish fry near me" isn't Mequon
    let idx = raw.map((_, i) => i);
    // stop words drop out when something real is left, or when the query already named a guide or town ("fish fry near me")
    if (q.tag != null || q.town != null || idx.some((i) => !stop.has(mapped[i]))) idx = idx.filter((i) => !stop.has(mapped[i]));
    idx.forEach((i, n) => {
      const token = raw[i], isLast = n === idx.length - 1;
      if (own(syn, token)) { q.tokens.push([` ${syn[token]} `, ` ${token}`]); return; }
      const whole = (abbrs.has(token) && (!isLast || token.length > 1)) || (token.length <= 2 && !isLast);
      const needles = [" " + token + (whole ? " " : "")];
      if (isLast && token.length >= 3) for (const [word, abbr] of Object.entries(typeSyn)) if (word !== token && word.startsWith(token)) needles.push(` ${abbr} `);
      q.tokens.push(needles);
    });
    if (q.tokens.length >= 2 && idx.length && typeAbbrs.has(mapped[idx[idx.length - 1]])) {
      const last = idx[idx.length - 1], prev = idx[idx.length - 2];
      q.tokens.splice(-2, 2, [` ${mapped[prev]} ${mapped[last]} `, ` ${raw[prev]} ${raw[last]}`]);
    }
    return q;
  }
  const qEmpty = (q) => !q.tokens.length && !q.town && !q.tag;
  function matches(p, q) {
    if (q.tag && !(p.g & q.tag)) {
      const stem = normalize(q.tagPhrase || "").replace(/s$/, "");
      if (!stem || !p.nameText.includes(" " + stem)) return false;
    }
    if (q.town && p.c !== q.town && !p.nameText.includes(" " + normalize(q.townPhrase || ""))) return false;
    return q.tokens.every((needles) => needles.some((n) => p.search.includes(n)));
  }
  const nameMatches = (p, q) => q.tokens.length && q.tokens.every((needles) => needles.some((n) => p.nameText.includes(n)));

  // ---------------------------------------------------------------- guides (WisconsinEats/Models/Guide.swift)
  const GUIDES = {
    fishfry: { title: "Friday Fish Fry", sub: "Hand-checked Friday fish fries, with the fish they serve", inc: (p) => p.hc && p.g & FISHFRY, sorts: ["featured", "nearest", "oldest", "name"] },
    supper: { title: "Supper Clubs", sub: "Relish trays, old fashioneds and prime rib, statewide", inc: (p) => p.hc && p.g & SUPPER, sorts: ["featured", "nearest", "oldest", "name"] },
    custard: { title: "Frozen Custard", sub: "Local custard stands, not the chains", inc: (p) => p.hc && p.g & CUSTARD && p.ch < 5, sorts: ["featured", "nearest", "oldest", "name"] },
    icons: { title: "Wisconsin Icons", sub: "James Beard honorees and long-running institutions", inc: (p) => p.ip != null, sorts: ["iconic", "oldest", "nearest"], ranked: true },
    oldest: { title: "Oldest Places", sub: "Verified founding years, oldest first", inc: (p) => p.f != null, sorts: ["oldest"], ranked: true },
    inspections: { title: "Inspections", sub: "Dane County inspections, cleanest first. Grades are ours, on a curve, not official grades.", inc: (p) => p.in >= 2, sorts: ["cleanest"], ranked: true },
    all: { title: "All Restaurants", sub: "Restaurants, cafés, taverns and bakeries statewide", inc: () => true, sorts: ["name", "nearest"] },
    saved: { title: "Saved", sub: "Places you saved in this browser", inc: (p) => saved.has(p.id), sorts: ["name", "nearest"] },
  };
  const SORT_LABEL = { featured: "Featured first", nearest: "Nearest", oldest: "Oldest first", name: "A to Z", iconic: "Most iconic", cleanest: "Cleanest" };

  // ---------------------------------------------------------------- state
  let P = [], D = null, CAL = {}, TOWN_KEYS = new Map(), TOWN_KEYS_BY_LENGTH = [], CHECKED = "";
  let here = null, shown = 100, current = [], view = "list", wired = false;
  const savedIds = store.get("saved", []);
  const saved = new Set(Array.isArray(savedIds) ? savedIds.filter((x) => typeof x === "string") : []);
  const st = { g: "fishfry", q: "", sort: "", town: "", cuisine: "", chains: false, p: "" };

  const miles = (a, b) => {
    const r = Math.PI / 180, dLa = (b.la - a.la) * r, dLo = (b.lo - a.lo) * r;
    const h = Math.sin(dLa / 2) ** 2 + Math.cos(a.la * r) * Math.cos(b.la * r) * Math.sin(dLo / 2) ** 2;
    return 3958.8 * 2 * Math.asin(Math.sqrt(h));
  };
  const milesText = (m) => (m < 10 ? m.toFixed(1) : Math.round(m)) + " mi";

  function order() {   // "Nearest" only once there's a location fix: a #sort=nearest link, a refusal or a timeout never claims distance order
    const g = GUIDES[st.g];
    if (st.sort && g.sorts.includes(st.sort) && (st.sort !== "nearest" || here)) return st.sort;
    if (["fishfry", "supper", "custard"].includes(st.g) && here) return "nearest";
    return g.sorts.find((s) => s !== "nearest" || here) || g.sorts[0];
  }

  function allows(p) {
    if (st.town && p.c !== st.town) return false;
    if (st.cuisine && p.cu !== st.cuisine) return false;
    if (st.chains && p.ch >= 5) return false;
    return true;
  }

  function list() {
    const g = GUIDES[st.g], q = parse(st.q), o = order();
    if (qEmpty(q) && st.q.trim()) return [];   // typed something, but nothing searchable ("🍕", "!!!")
    // the only non-restaurants here are hand-picked icons (a cheese shop, a sausage maker): Icons guide only
    let out = P.filter((p) => (!p.v || st.g === "icons") && g.inc(p) && allows(p) && (qEmpty(q) || matches(p, q)));
    const byName = (a, b) => a.n.localeCompare(b.n, "en", { sensitivity: "base" });
    const dist = (p) => (here && p.la != null ? miles(here, p) : Infinity);
    if (o === "nearest" && here) out.sort((a, b) => dist(a) - dist(b) || byName(a, b));
    else if (o === "featured" || o === "nearest") out.sort((a, b) => (b.ip ?? -1) - (a.ip ?? -1) || (a.f ?? 9999) - (b.f ?? 9999) || byName(a, b));
    else if (o === "oldest") out.sort((a, b) => (a.f ?? 9999) - (b.f ?? 9999) || byName(a, b));
    else if (o === "iconic") out.sort((a, b) => (b.ip ?? -1) - (a.ip ?? -1) || byName(a, b));
    else if (o === "cleanest") out.sort((a, b) => (b.sc ?? 50) - (a.sc ?? 50) || byName(a, b));
    else out.sort(byName);
    if (q.tokens.length && !g.ranked) {       // name matches first when searching
      const named = out.filter((p) => nameMatches(p, q));
      if (named.length && named.length < out.length) { const ids = new Set(named); out = named.concat(out.filter((p) => !ids.has(p))); }
    }
    return out;
  }

  // ---------------------------------------------------------------- rendering
  function chips(p, max) {
    const c = [];
    const jb = p.h & 1 ? "America's Classic" : p.h & 2 ? "James Beard winner" : p.h & 4 ? "James Beard finalist" : p.h & 8 ? "James Beard semifinalist" : null;
    if (jb) c.push(`<span class="tag tag-jb">${jb}</span>`);
    if (p.g & FISHFRY) c.push('<span class="tag">Fish fry</span>');
    if (p.g & SUPPER) c.push('<span class="tag">Supper club</span>');
    if (p.g & CUSTARD) c.push('<span class="tag">Custard</span>');
    if (p.g & BOIL) c.push('<span class="tag">Fish boil</span>');
    if (p.h & 16 && !jb) c.push('<span class="tag tag-plain">Icon</span>');
    if (p.ch >= 5) c.push(`<span class="tag tag-plain">Chain · ${esc(p.ch)}</span>`);
    if (p.t === 0 && !p.h && !p.g) c.push('<span class="tag tag-dash">Listing only</span>');
    return (max ? c.slice(0, max) : c).join("");
  }

  function metric(p, o) {
    if (o === "nearest" && here && p.la != null) return [milesText(miles(here, p)), "away"];
    if (o === "cleanest" && p.gr) return [`${p.gr} ${p.sc}`, "our grade"];
    if (o === "iconic" && p.ip != null) return [String(Math.round(p.ip)), "iconic pts"];
    if (p.f && st.g !== "all") return [String(p.f), "since"];
    return null;
  }

  // Before the data arrives: show the guide from the URL or last visit, so nothing moves when the list fills in.
  function preRender() {
    document.querySelectorAll(".ex-guides button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.g === st.g)));
    $("#ex-sub").textContent = GUIDES[st.g].sub;
  }

  function render() {
    const g = GUIDES[st.g], o = order();
    current = list();
    preRender();
    const sortSel = $("#ex-sort");
    sortSel.innerHTML = g.sorts.map((s) => `<option value="${s}"${s === o ? " selected" : ""}>${SORT_LABEL[s]}</option>`).join("");
    sortSel.disabled = g.sorts.length < 2;
    const filters = [st.town && `in ${st.town}`, st.cuisine && st.cuisine, st.chains && "no chains"].filter(Boolean);
    $("#ex-count").textContent = `${current.length.toLocaleString()} ${current.length === 1 ? "place" : "places"} · ${SORT_LABEL[o]}` + (filters.length ? ` · ${filters.join(", ")}` : "");
    const clear = $("#ex-clear");
    clear.classList.toggle("ex-off", !filters.length);   // kept in the layout, so the row doesn't reflow
    clear.disabled = !filters.length;
    if (view === "list") renderList(o); else drawMap();
    saveHash();
  }

  function renderList(o) {
    const ol = $("#ex-list");
    const g = GUIDES[st.g];
    if (!current.length) {
      // a search inside a guide that the rest of the state answers ("kopps" in Fish fry): offer the whole list, not a dead end
      const q = parse(st.q);
      const elsewhere = st.g !== "all" && !qEmpty(q) ? P.filter((p) => !p.v && allows(p) && matches(p, q)).length : 0;
      ol.innerHTML = `<li class="ex-empty">${elsewhere
        ? `Nothing in ${esc(g.title)} matches that. <button type="button" class="ex-linkbtn" id="ex-all">Search all restaurants (${elsewhere.toLocaleString()} ${elsewhere === 1 ? "match" : "matches"})</button>`
        : st.g === "saved" && qEmpty(q) ? "Nothing saved yet. Open a place and tap Save to keep it here, in this browser." : "No places match. Try fewer words or clear the filters."}</li>`;
      const all = $("#ex-all");
      if (all) all.onclick = () => { st.g = "all"; st.sort = ""; shown = 100; render(); $(".ex-row")?.focus(); };
      $("#ex-more").hidden = true;
      return;
    }
    ol.innerHTML = current.slice(0, shown).map((p, i) => {
      const m = metric(p, o);
      const rank = g.ranked ? `<span class="ex-rank${i < 3 ? " top" : ""}"><span class="vh">Rank </span>${i + 1}</span>` : "";
      return `<li><button class="ex-row" data-i="${p.i}">${rank}<span class="ex-main"><b>${esc(p.n)}</b><span class="ex-town">${esc([p.c, p.cu].filter(Boolean).join(" · "))}</span><span class="ex-chips">${chips(p, 4)}</span></span>${m ? `<span class="ex-metric"><b>${esc(m[0])}</b><small>${m[1]}</small></span>` : ""}</button></li>`;
    }).join("");
    const left = current.length - shown;
    $("#ex-more").hidden = left <= 0;
    $("#ex-more").textContent = `Show more (${left.toLocaleString()} left)`;
  }

  // ---------------------------------------------------------------- place panel (a modal dialog: the rest of the page is inert)
  const JUR = { 1: "City of Milwaukee", 2: "Public Health Madison & Dane County" };
  const TIER = { 2: "Licensed", 1: "Confirmed listing", 0: "Listing only" };

  function rate(p) {
    const src = SOURCES[p.s] || "meta";
    const group = src === "meta" ? (p.t === 1 ? "meta_high" : "meta_mid") : (src === "AllThePlaces" || src === "DAC") ? "brand_feed" : null;
    if (!group) return null;
    const v = ["mke", "dane"].map((a) => CAL[a]?.[group]?.official).filter((x) => x != null);
    if (!v.length) return null;
    const lo = Math.round(Math.min(...v) * 100), hi = Math.round(Math.max(...v) * 100);
    return lo === hi ? `${lo}%` : `${lo}–${hi}%`;
  }

  function howWeKnow(p) {
    const src = SOURCES[p.s] || "meta";
    if (src === "research") return `On our hand-checked list (checked in ${CHECKED} against a 2025 or 2026 source). The open map data didn't list it as a place to eat, so it's placed from its own map listing or street address.`;
    if (p.t === 2) return src === "official"
      ? `From the ${JUR[p.j] || "official"} active license list. The open map data didn't have it, so its location comes from the license record or its street address.`
      : `Matched to an active license on the ${JUR[p.j] || "official"} list.`;
    const r = rate(p);
    return (p.t === 1 ? "A high-confidence listing in Overture's open map data." : "A single listing in Overture's open map data, so it may be closed or misfiled.")
      + (r ? ` Checked against Milwaukee's and Dane County's license lists, listings like this matched a licensed business ${r} of the time.` : "")
      + (p.hc ? ` It's also on our hand-checked list, checked in ${CHECKED} against a 2025 or 2026 source.` : "");
  }

  const kv = (k, v) => (v == null || v === "" ? "" : `<div class="ex-kv"><span>${esc(k)}</span><b>${esc(v)}</b></div>`);
  const section = (t, body) => `<section class="ex-sec"><h3>${esc(t)}</h3>${body}</section>`;
  const outside = () => [...document.body.children].filter((el) => el.id !== "ex-panel" && el.id !== "ex-scrim" && el.tagName !== "SCRIPT");

  let opener = null, openId = "";   // what had focus when a place was opened (to give it back on close), and the place
  function openPlace(p, push = true) {
    if (push || !st.p) opener = document.activeElement;
    st.p = openId = p.id;
    const d = (D && D[p.i]) || {};
    const addr = [p.a, [p.c, p.z].filter(Boolean).join(" ")].filter(Boolean).join(", ");
    const la = num(p.la), lo = num(p.lo);
    const apple = la != null && lo != null
      ? `https://maps.apple.com/?q=${encodeURIComponent(p.n)}&ll=${la},${lo}`
      : `https://maps.apple.com/?q=${encodeURIComponent(p.n + ", " + addr)}`;
    const dirs = la != null && lo != null ? `https://maps.apple.com/?daddr=${la},${lo}&dirflg=d` : apple;
    const site = safeSite(d.w), tel = telHref(d.ph);
    let html = `<button type="button" class="ex-close" id="ex-close" aria-label="Close">×</button>
      <p class="ex-kicker">${esc((p.c || "Wisconsin").toUpperCase())}</p>
      <h2 id="ex-pname">${esc(p.n)}</h2>
      <p class="ex-addr">${esc([addr, p.cu].filter(Boolean).join(" · "))}</p>
      ${here && la != null ? `<p class="ex-dist">${milesText(miles(here, p))} away</p>` : ""}
      <p class="ex-chips">${chips(p)}</p>
      <div class="ex-actions">
        <a class="btn ex-apple" href="${esc(apple)}" rel="noopener" target="_blank">Ratings, hours &amp; photos · Apple Maps</a>
        <div class="ex-act-row">
          <a href="${esc(dirs)}" rel="noopener" target="_blank">Directions</a>
          ${tel ? `<a href="${esc(tel)}">Call</a>` : ""}
          ${site ? `<a href="${esc(site)}" rel="noopener nofollow" target="_blank">Website</a>` : ""}
          <button type="button" id="ex-save" aria-pressed="${saved.has(p.id)}">${saved.has(p.id) ? "Saved" : "Save"}</button>
        </div>
      </div>`;
    if (!D) html += `<p class="ex-fine" id="ex-more-loading">Loading details…</p>`;
    if (p.g || d.note) {
      const facts = [];
      if (p.g & FISHFRY) facts.push(["Fish fry", [d.days && "Served " + d.days, p.fish && "Fish: " + p.fish, d.sides && "With " + d.sides].filter(Boolean).join(". ") || "Serves a Friday fish fry."]);
      if (p.g & SUPPER) facts.push(["Supper club", p.hc ? "Calls itself a supper club, or is widely known as one." : "Has “supper club” in its name in the map listing."]);
      if (p.g & CUSTARD) facts.push(["Frozen custard", p.hc ? "Serves frozen custard." : "Listed as a frozen custard stand in the map listing."]);
      if (p.g & BOIL) facts.push(["Fish boil", "Door County-style fish boil."]);
      html += section("Wisconsin classics", facts.map(([k, v]) => `<p><b>${k}</b><br>${esc(v)}</p>`).join("")
        + (d.note ? `<p>${esc(d.note)}</p>` : "")
        + `<p class="ex-fine">${p.hc ? `Hand-checked in ${esc(CHECKED)} against a 2025 or 2026 source: the place's own site or menu, local news, or its Travel Wisconsin listing. Days and menus change, so check before you go.` : "Not hand-checked yet, so it isn't in our supper club or custard guides. Check before you go."}</p>`);
    }
    if (p.h || p.f) {
      const lines = [...(d.jbf ? d.jbf.split("; ").map((x) => "James Beard: " + x) : []), ...(d.hon ? d.hon.split("; ") : [])];
      html += section("Honors & history", (d.icon ? `<p>${esc(d.icon)}</p>` : "") + (lines.length ? `<ul>${lines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>` : "") + (p.f ? kv("Open since", `${p.f} (verified)`) : ""));
    }
    if (d.in) {
      const i = d.in;
      html += section("Health inspections · Dane County, since Jan 2023",
        `<p class="ex-grade"><span class="ex-g ex-g-${esc(i.g)}">${esc(i.g)}</span> Score ${esc(i.sc ?? 0)}/100</p><p class="ex-fine">Our grade, on a curve, from Public Health Madison &amp; Dane County results. Not an official grade.</p>`
        + kv("Routine inspections", i.n) + kv("Needed a re-inspection", i.re) + kv("Violations per visit", i.vp?.toFixed?.(1))
        + kv("Foodborne-illness risk items per visit", i.rf?.toFixed?.(1)) + kv("Visits with a pest item", i.pe) + kv("Repeat violations", i.rp)
        + (i.su ? kv("Immediate suspensions", i.su) : "") + (i.ld ? kv("Last routine visit", i.ld + (i.lr === 1 ? " · re-inspection needed" : "")) : ""));
    }
    html += section("How we know it's here", kv("Listed as", TIER[p.t]) + (p.t === 2 ? kv("License list", JUR[p.j]) : "") + kv("License number", d.lic)
      + (p.ch >= 2 ? kv("Locations in Wisconsin", p.ch.toLocaleString()) : "") + `<p class="ex-fine">${esc(howWeKnow(p))}</p>`);
    html += `<p class="ex-app">Save it on your phone: <a class="store-btn" href="${BASE}/#download">get the free iPhone app</a>.</p>`;
    const panel = $("#ex-panel");
    panel.innerHTML = html;
    panel.hidden = false;
    $("#ex-scrim").hidden = false;
    outside().forEach((el) => { el.inert = true; });
    document.body.classList.add("ex-open");
    $("#ex-close").onclick = () => closePlace();
    $("#ex-save").onclick = (e) => {
      if (saved.has(p.id)) saved.delete(p.id); else saved.add(p.id);
      store.set("saved", [...saved]);
      e.target.textContent = saved.has(p.id) ? "Saved" : "Save";
      e.target.setAttribute("aria-pressed", String(saved.has(p.id)));
      if (st.g === "saved") render();
    };
    panel.scrollTop = 0;
    $("#ex-close").focus();
    saveHash(push);   // a new history entry, so the browser's Back closes the place instead of leaving the page
    if (!D) loadDetail().then(() => { if (st.p === p.id && !$("#ex-panel").hidden) openPlace(p, false); });   // details load on the first open only
  }

  function closePlace(fromHistory = false) {
    // a place opened here has its own history entry: going back to the entry before it closes the panel (in hashchange below)
    if (!fromHistory && history.state && history.state.exPlace) { history.back(); return; }
    const was = st.p || openId;   // Back has already taken the place out of the URL (and st) by the time this runs
    st.p = openId = "";
    $("#ex-panel").hidden = true;
    $("#ex-scrim").hidden = true;
    outside().forEach((el) => { el.inert = false; });
    document.body.classList.remove("ex-open");
    saveHash();
    // focus goes back to the row (list), the control that opened it, or the Map / current guide button (a map dot or a deep link)
    const row = was && view === "list" && document.querySelector(`.ex-row[data-i="${P.findIndex((p) => p.id === was)}"]`);
    const keep = opener && opener.isConnected && opener !== document.body && opener.closest("#ex-app") && !opener.closest("[hidden]") ? opener : null;
    const back = row || keep || document.querySelector(view === "map" ? '.ex-view button[data-v="map"]' : '.ex-guides button[aria-pressed="true"]');
    opener = null;
    if (back) back.focus();
  }

  // ---------------------------------------------------------------- map (canvas: county outlines + a dot per place)
  let SHAPES = null, cam = null;
  const LAT0 = 44.8, KX = Math.cos(LAT0 * Math.PI / 180);
  const proj = (lo, la) => [(lo + 90) * KX, -(la - LAT0)];

  function fitCam(w, h) {
    const [x0, y0] = proj(-92.95, 47.1), [x1, y1] = proj(-86.75, 42.45);
    const k = Math.min(w / (x1 - x0), h / (y1 - y0)) * 0.95;
    return { k, x: (w - (x1 - x0) * k) / 2 - x0 * k, y: (h - (y1 - y0) * k) / 2 - y0 * k };
  }

  async function drawMap() {
    const cv = $("#ex-map"), wrap = $("#ex-mapwrap");
    const w = wrap.clientWidth, h = wrap.clientHeight, dpr = window.devicePixelRatio || 1;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    if (!cam) cam = fitCam(w, h);
    if (!SHAPES) SHAPES = await fetchJSON(`${BASE}/data/wi_shapes.json`).catch(() => ({ state: [], counties: [] }));
    const css = getComputedStyle(document.documentElement), tok = (n, d) => css.getPropertyValue(n).trim() || d;   // light or dark
    const c = cv.getContext("2d");
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);
    const X = (lo, la) => { const [x, y] = proj(lo, la); return [x * cam.k + cam.x, y * cam.k + cam.y]; };
    const ring = (r) => { r.forEach(([lo, la], i) => { const [x, y] = X(lo, la); i ? c.lineTo(x, y) : c.moveTo(x, y); }); c.closePath(); };
    c.fillStyle = tok("--surface", "#fff");
    c.beginPath(); (SHAPES.state || []).forEach(ring); c.fill("evenodd");
    c.strokeStyle = tok("--county", "rgba(83,102,91,.35)"); c.lineWidth = 0.8;
    for (const co of SHAPES.counties || []) { c.beginPath(); co.c.forEach(ring); c.stroke(); }
    const pts = current.filter((p) => p.la != null);
    const r = Math.max(2.2, Math.min(5, 1.6 + cam.k / 120));
    for (const classic of [false, true]) {
      c.fillStyle = classic ? tok("--gold", "#ffb612") : tok("--dot", "#203731");
      c.strokeStyle = "#203731"; c.lineWidth = 1;
      for (const p of pts) {
        if (Boolean(p.hc && p.g) !== classic) continue;
        const [x, y] = X(p.lo, p.la);
        if (x < -5 || y < -5 || x > w + 5 || y > h + 5) continue;
        c.beginPath(); c.arc(x, y, classic ? r + 1 : r, 0, 6.2832); c.fill(); if (classic) c.stroke();
      }
    }
    $("#ex-maphint").textContent = pts.length ? `${pts.length.toLocaleString()} places · tap a dot` : "No places to show";
  }

  function nearestDot(px, py) {
    let best = null, bd = 14 * 14;
    for (const p of current) {
      if (p.la == null) continue;
      const [x0, y0] = proj(p.lo, p.la), x = x0 * cam.k + cam.x, y = y0 * cam.k + cam.y;
      const d = (x - px) ** 2 + (y - py) ** 2;
      if (d < bd) { bd = d; best = p; }
    }
    return best;
  }

  function zoomAt(f, px, py) {
    const k = Math.min(Math.max(cam.k * f, 40), 60000);
    const s = k / cam.k;
    cam = { k, x: px - (px - cam.x) * s, y: py - (py - cam.y) * s };
    drawMap();
  }

  function mapEvents() {
    const cv = $("#ex-map");
    const ptrs = new Map();
    let moved = false, pinch0 = null;
    cv.addEventListener("wheel", (e) => { e.preventDefault(); const b = cv.getBoundingClientRect(); zoomAt(e.deltaY < 0 ? 1.25 : 0.8, e.clientX - b.left, e.clientY - b.top); }, { passive: false });
    cv.addEventListener("pointerdown", (e) => { cv.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, [e.clientX, e.clientY]); moved = false; pinch0 = null; });
    cv.addEventListener("pointermove", (e) => {
      if (!ptrs.has(e.pointerId)) return;
      const prev = ptrs.get(e.pointerId);
      ptrs.set(e.pointerId, [e.clientX, e.clientY]);
      if (ptrs.size === 2) {
        const [a, b] = [...ptrs.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        const r = cv.getBoundingClientRect();
        if (pinch0) zoomAt(d / pinch0, (a[0] + b[0]) / 2 - r.left, (a[1] + b[1]) / 2 - r.top);
        pinch0 = d; moved = true; return;
      }
      const dx = e.clientX - prev[0], dy = e.clientY - prev[1];
      if (Math.abs(dx) + Math.abs(dy) > 2) moved = true;
      cam.x += dx; cam.y += dy; drawMap();
    });
    const up = (e) => {
      ptrs.delete(e.pointerId);
      if (!moved && ptrs.size === 0) {
        const b = cv.getBoundingClientRect(), p = nearestDot(e.clientX - b.left, e.clientY - b.top);
        if (p) openPlace(p);
      }
      if (ptrs.size < 2) pinch0 = null;
    };
    cv.addEventListener("pointerup", up);
    cv.addEventListener("pointercancel", (e) => ptrs.delete(e.pointerId));
    $("#ex-zin").onclick = () => zoomAt(1.6, cv.clientWidth / 2, cv.clientHeight / 2);
    $("#ex-zout").onclick = () => zoomAt(0.625, cv.clientWidth / 2, cv.clientHeight / 2);
    window.addEventListener("resize", () => { if (view === "map") drawMap(); });
    matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => { if (view === "map") drawMap(); });
  }

  function centerOn(pt) {
    const cv = $("#ex-map"), w = cv.clientWidth, h = cv.clientHeight;
    const k = 4000, [x, y] = proj(pt.lo, pt.la);
    cam = { k, x: w / 2 - x * k, y: h / 2 - y * k };
  }

  // ---------------------------------------------------------------- data, URL state, controls
  let SOURCES = [];
  async function fetchJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error(r.status + " " + url); return r.json(); }
  let detailPromise = null;
  function loadDetail() {   // phones, sites, notes and inspections: fetched when a place is first opened, not before
    detailPromise ||= fetchJSON(`${BASE}/data/detail.json`).then((d) => { D = Array.isArray(d) ? d : []; }).catch(() => { D = []; });
    return detailPromise;
  }

  async function load() {
    const d = await fetchJSON(`${BASE}/data/core.json`);
    CAL = d.calibration || {}; SOURCES = d.sources || []; CHECKED = d.checked || "";
    const C = d.cols, n = C.id.length, towns = new Map();
    P = new Array(n);
    TOWN_KEYS = new Map();
    for (let i = 0; i < n; i++) {
      const city = C.c[i] == null ? null : d.cities[C.c[i]], cu = d.cuisines[C.cu[i]], brand = C.b[i] == null ? null : d.brands[C.b[i]];
      const p = { i, id: C.id[i], n: C.n[i], c: city, cu, t: C.t[i], s: C.s[i], a: C.a[i], z: C.z[i], la: C.la[i], lo: C.lo[i],
        ch: C.ch[i] || 1, g: C.g[i] || 0, hc: C.hc[i] === 1, ip: C.ip[i], f: C.f[i], fish: C.fish[i], h: C.h[i] || 0,
        j: C.j[i], gr: C.gr[i], sc: C.sc[i], in: C.in[i] || 0, v: C.v[i] === 1 };
      p.search = " " + normalize([p.n, city, p.z, cu, brand, p.fish].filter(Boolean).join(" ")) + " " + normAddr(p.a || "") + " ";
      p.nameText = " " + normalize([p.n, brand].filter(Boolean).join(" ")) + " ";
      P[i] = p;
      if (city) towns.set(city, (towns.get(city) || 0) + 1);
    }
    const byCount = [...towns.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    for (const [name] of byCount) { const k = normAddr(name); if (!TOWN_KEYS.has(k)) TOWN_KEYS.set(k, name); }
    TOWN_KEYS_BY_LENGTH = [...TOWN_KEYS.keys()].sort((a, b) => b.length - a.length);
    $("#ex-town").innerHTML = '<option value="">All towns</option>' + [...towns.keys()].sort((a, b) => a.localeCompare(b)).map((t) => `<option>${esc(t)}</option>`).join("");
    const cuis = new Map();
    for (const p of P) cuis.set(p.cu, (cuis.get(p.cu) || 0) + 1);
    $("#ex-cuisine").innerHTML = '<option value="">All kinds</option>' + [...cuis.entries()].sort((a, b) => b[1] - a[1]).map(([c, k]) => `<option value="${esc(c)}">${esc(c)} (${k.toLocaleString()})</option>`).join("");
  }

  function readHash() {
    const h = new URLSearchParams(location.hash.slice(1));
    const last = store.get("guide", "fishfry");
    st.g = own(GUIDES, h.get("g")) ? h.get("g") : own(GUIDES, last) ? last : "fishfry";
    st.q = h.get("q") || ""; st.town = h.get("town") || ""; st.cuisine = h.get("kind") || ""; st.chains = h.get("chains") === "1";
    st.sort = h.get("sort") || ""; st.p = h.get("p") || "";
  }
  function saveHash(push = false) {
    const h = new URLSearchParams();
    h.set("g", st.g);
    if (st.q) h.set("q", st.q); if (st.town) h.set("town", st.town); if (st.cuisine) h.set("kind", st.cuisine);
    if (st.chains) h.set("chains", "1"); if (st.sort) h.set("sort", st.sort); if (st.p) h.set("p", st.p);
    if (push) history.pushState({ exPlace: true }, "", "#" + h.toString());
    else history.replaceState(history.state, "", "#" + h.toString());   // keeps the entry's place flag
    store.set("guide", st.g);
  }

  function locate() {
    if (!navigator.geolocation) { $("#ex-locmsg").textContent = "This browser can't share its location."; return; }
    $("#ex-locmsg").textContent = "Finding you…";
    navigator.geolocation.getCurrentPosition((pos) => {
      here = { la: pos.coords.latitude, lo: pos.coords.longitude };
      // every place is in Wisconsin: a reader elsewhere is told so, and the map stays on the state (as in the app's LocationService)
      const outside = !(here.la >= 42.4 && here.la <= 47.4 && here.lo >= -93.0 && here.lo <= -86.2);
      $("#ex-locmsg").textContent = outside
        ? "You're outside Wisconsin. Every place here is in Wisconsin, so distances are from where you are now."
        : "Sorted by distance. Your location stays in this page.";
      st.sort = GUIDES[st.g].sorts.includes("nearest") ? "nearest" : st.sort;
      if (view === "map" && !outside) centerOn(here);
      shown = 100; render();
    }, (err) => {
      $("#ex-locmsg").textContent = err && err.code === 1
        ? "Location is off for this site. Allow it in your browser settings to sort by distance."
        : "Couldn't find your location just now. Try Near me again.";   // no fix or a timeout: the button stays, so it can retry
    },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 0 });   // a fresh fix on every tap, as the app asks for
  }

  function setView(v) {
    view = v;
    document.querySelectorAll(".ex-view button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === v)));
    $("#ex-listwrap").hidden = v !== "list";
    $("#ex-mapwrap").hidden = v !== "map";
    render();
  }

  function controls() {
    document.querySelectorAll(".ex-guides button").forEach((b) => b.onclick = () => { st.g = b.dataset.g; st.sort = ""; shown = 100; render(); });
    let t = null;
    $("#ex-q").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { st.q = e.target.value; shown = 100; render(); }, 120); });
    $("#ex-sort").onchange = (e) => { st.sort = e.target.value; if (st.sort === "nearest" && !here) locate(); shown = 100; render(); };
    $("#ex-town").onchange = (e) => { st.town = e.target.value; shown = 100; render(); };
    $("#ex-cuisine").onchange = (e) => { st.cuisine = e.target.value; shown = 100; render(); };
    $("#ex-chains").onchange = (e) => { st.chains = e.target.checked; shown = 100; render(); };
    $("#ex-clear").onclick = () => { st.town = st.cuisine = ""; st.chains = false; syncInputs(); shown = 100; render(); };
    $("#ex-locate").onclick = locate;
    $("#ex-more").onclick = () => { shown += 200; renderList(order()); };
    document.querySelectorAll(".ex-view button").forEach((b) => b.onclick = () => setView(b.dataset.v));
    $("#ex-list").addEventListener("click", (e) => { const b = e.target.closest(".ex-row"); if (b) openPlace(P[+b.dataset.i]); });
    $("#ex-scrim").onclick = () => closePlace();
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && st.p) closePlace(); });
    // Back/Forward between a place's entry and the one before it, a link, or an edited address bar (pushState and replaceState
    // themselves don't fire this)
    window.addEventListener("hashchange", () => {
      readHash(); syncInputs(); shown = 100; render();
      const p = st.p && P.find((x) => x.id === st.p);
      if (p) openPlace(p, false); else if (!$("#ex-panel").hidden) closePlace(true);
    });
    mapEvents();
  }
  function syncInputs() {
    $("#ex-q").value = st.q; $("#ex-town").value = st.town; $("#ex-cuisine").value = st.cuisine; $("#ex-chains").checked = st.chains;
  }

  async function start() {
    const box = $("#ex-loading");
    box.hidden = false;
    box.textContent = "Loading Wisconsin's restaurants…";
    try { await load(); } catch {
      box.innerHTML = 'The restaurant list couldn’t load. Check your connection, then <button type="button" class="ex-linkbtn" id="ex-retry">try again</button>';
      $("#ex-retry").onclick = start;
      return;
    }
    document.querySelectorAll("#ex-app [disabled]").forEach((el) => { el.disabled = false; });
    syncInputs();
    if (!wired) { controls(); wired = true; }
    box.hidden = true;
    render();
    const open = st.p && P.find((p) => p.id === st.p);
    if (open) openPlace(open, false);
  }

  readHash();
  preRender();
  const chip = document.querySelector(`.ex-guides button[data-g="${st.g}"]`), row = $(".ex-guides");
  if (chip && chip.offsetLeft + chip.offsetWidth > row.clientWidth) row.scrollLeft = chip.offsetLeft - 16;   // show the current guide's chip
  start();
})();
