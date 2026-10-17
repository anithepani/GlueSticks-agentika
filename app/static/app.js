/* Witness - casework console
   Hash-routed single page app. No framework, no build step. */

(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c]));

  const APP = $("#app");
  const LIVE = $("#live");
  const LIVE_TEXT = $("#live-text");

  const STATUS = {
    VERIFIED: { label: "Verified", tone: "ok" },
    NEEDS_REVIEW: { label: "Needs review", tone: "warn" },
    APPROVED: { label: "Approved", tone: "ok" },
    DENIED: { label: "Denied", tone: "bad" },
    INFO_REQUESTED: { label: "Information requested", tone: "info" },
    INTAKE: { label: "Received", tone: "neutral" },
  };

  const VERIFICATION = {
    OK: { label: "Verified", tone: "ok" },
    ABSTAIN: { label: "Abstained", tone: "warn" },
  };

  const OUTCOME = {
    ELIGIBLE: { label: "Eligible", tone: "ok" },
    NEEDS_REVIEW: { label: "Needs review", tone: "warn" },
  };

  const EVENT = {
    intake: { label: "Case received", tone: "" },
    intake_submitted: { label: "Case created", tone: "" },
    pipeline_run: { label: "Pipeline completed", tone: "" },
    assigned: { label: "Case assigned", tone: "" },
    human_decision: { label: "Decision recorded", tone: "ok" },
    resubmit: { label: "Evidence resubmitted", tone: "info" },
  };

  const state = {
    cases: [],
    stats: null,
    adapters: null,
    current: null,
    audit: [],
    evaluation: null,
    filter: "all",
    pendingCite: null,
    action: "approve",
  };

  /* ---------------- api ---------------- */

  async function api(path, options) {
    const res = await fetch(path, Object.assign({ cache: "no-store" }, options));
    let body = null;
    try {
      body = await res.json();
    } catch (e) {
      body = null;
    }
    if (!res.ok) {
      const message =
        (body && (body.detail || body.message)) || `Request failed (${res.status})`;
      throw new Error(typeof message === "string" ? message : JSON.stringify(message));
    }
    return body;
  }

  const post = (path, body) =>
    api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });

  /* ---------------- helpers ---------------- */

  const tag = (map, value) => {
    const item = map[value] || { label: value || "Unknown", tone: "neutral" };
    return `<span class="tag ${item.tone}">${esc(item.label)}</span>`;
  };

  const statusTag = (s) => tag(STATUS, s);
  const verifyTag = (s) => tag(VERIFICATION, s);
  const outcomeTag = (s) => tag(OUTCOME, s);

  function fmtAge(minutes) {
    if (minutes === null || minutes === undefined) return "";
    const m = Number(minutes);
    if (!isFinite(m)) return "";
    if (m < 1) return "just now";
    if (m < 60) return `${Math.round(m)} min ago`;
    if (m < 60 * 24) {
      const h = m / 60;
      return `${h < 10 ? h.toFixed(1) : Math.round(h)} h ago`;
    }
    return `${Math.round(m / (60 * 24))} d ago`;
  }

  function fmtClock(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleString(undefined, {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  const money = (n) => `PKR ${Number(n).toLocaleString("en-PK")}`;

  function fmtValue(key, value) {
    if (value === null || value === undefined || value === "") return "—";
    switch (key) {
      case "age":
        return `${value} years`;
      case "household_size":
        return `${value} ${Number(value) === 1 ? "person" : "people"}`;
      case "monthly_income_pkr":
        return `${money(value)} / month`;
      case "bank_balance_pkr":
        return money(value);
      case "land_acres":
        return `${value} ${Number(value) === 1 ? "acre" : "acres"}`;
      case "owns_car":
        return value ? "Yes" : "No";
      default:
        return String(value);
    }
  }

  const shortHash = (h) => (h ? String(h).slice(0, 10) + "…" : "");

  function notify(title, body, tone) {
    const el = document.createElement("div");
    el.className = `toast ${tone === "bad" ? "bad" : ""}`;
    el.setAttribute("role", "status");
    el.innerHTML = `
      <div>
        <div class="t-title">${esc(title)}</div>
        ${body ? `<div class="t-body">${esc(body)}</div>` : ""}
      </div>
      <button class="btn btn-quiet btn-sm" aria-label="Dismiss">Dismiss</button>`;
    el.querySelector("button").addEventListener("click", () => el.remove());
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 6000);
  }

  function setError(message) {
    const box = $("#view-error");
    if (!box) return;
    if (!message) {
      box.innerHTML = "";
      box.hidden = true;
      return;
    }
    box.hidden = false;
    box.className = "notice bad";
    box.innerHTML = `<div><strong>${esc(message)}</strong></div>`;
  }

  function empty(title, body, action) {
    return `<div class="empty"><h3>${esc(title)}</h3><p>${esc(body)}</p>${action || ""}</div>`;
  }

  function skeletonTable(rows = 5, cols = 6) {
    const head = Array.from({ length: cols }, () => "<th>&nbsp;</th>").join("");
    const body = Array.from({ length: rows }, () => {
      const cells = Array.from(
        { length: cols },
        () => `<td><div class="skel" style="height:12px;width:${60 + Math.random() * 30}%"></div></td>`
      ).join("");
      return `<tr class="skel-row">${cells}</tr>`;
    }).join("");
    return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  /* ---------------- markdown ---------------- */

  function inline(text) {
    return esc(text)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  }

  function markdown(md) {
    const lines = String(md || "").replace(/\r\n/g, "\n").split("\n");
    let html = "";
    let list = false;
    let table = false;
    let quote = false;

    const closeList = () => {
      if (list) {
        html += "</ul>";
        list = false;
      }
    };
    const closeTable = () => {
      if (table) {
        html += "</tbody></table>";
        table = false;
      }
    };
    const closeQuote = () => {
      if (quote) {
        html += "</blockquote>";
        quote = false;
      }
    };
    const closeAll = () => {
      closeList();
      closeTable();
      closeQuote();
    };

    const cells = (line) =>
      line
        .trim()
        .replace(/^\|/, "")
        .replace(/\|$/, "")
        .split("|")
        .map((c) => c.trim());

    for (let i = 0; i < lines.length; i += 1) {
      const raw = lines[i];
      const line = raw.trim();

      if (!line) {
        closeAll();
        continue;
      }

      if (/^---+$/.test(line)) {
        closeAll();
        html += "<hr/>";
        continue;
      }

      if (line.startsWith("|") && lines[i + 1] && /^\|[\s:|-]+\|?$/.test(lines[i + 1].trim())) {
        closeAll();
        const head = cells(line)
          .map((c) => `<th>${inline(c)}</th>`)
          .join("");
        html += `<table><thead><tr>${head}</tr></thead><tbody>`;
        table = true;
        i += 1;
        continue;
      }
      if (table && line.startsWith("|")) {
        const row = cells(line)
          .map((c) => `<td>${inline(c)}</td>`)
          .join("");
        html += `<tr>${row}</tr>`;
        continue;
      }
      if (table) closeTable();

      if (line.startsWith("> ")) {
        closeList();
        if (!quote) {
          html += "<blockquote>";
          quote = true;
        }
        html += `<p>${inline(line.slice(2))}</p>`;
        continue;
      }
      if (quote) closeQuote();

      const h = /^(#{1,3})\s+(.*)$/.exec(line);
      if (h) {
        closeList();
        const level = h[1].length;
        html += `<h${level}>${inline(h[2])}</h${level}>`;
        continue;
      }

      if (/^[-*]\s+/.test(line)) {
        if (!list) {
          html += "<ul>";
          list = true;
        }
        html += `<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`;
        continue;
      }
      if (list) closeList();

      html += `<p>${inline(line)}</p>`;
    }

    closeAll();
    return html;
  }

  /* ---------------- health ---------------- */

  async function pollHealth() {
    try {
      const [health, adapters] = await Promise.all([
        api("/health"),
        api("/api/adapters").catch(() => null),
      ]);
      state.adapters = adapters;
      LIVE.className = "live ok";
      LIVE_TEXT.textContent = "Live";
      LIVE.title = `Service online · v${health.version}`;
    } catch (e) {
      LIVE.className = "live bad";
      LIVE_TEXT.textContent = "Offline";
      LIVE.title = e.message;
    }
  }

  /* ---------------- routing ---------------- */

  function parseRoute() {
    const raw = location.hash.replace(/^#\/?/, "");
    const parts = raw.split("/").filter(Boolean);
    if (!parts.length || parts[0] === "cases") {
      if (parts.length >= 2) {
        return { name: "case", id: decodeURIComponent(parts[1]), tab: parts[2] || "evidence" };
      }
      return { name: "queue" };
    }
    if (["policy", "quality", "about", "new"].includes(parts[0])) {
      return { name: parts[0] };
    }
    return { name: "queue" };
  }

  function go(hash) {
    if (location.hash === hash) route();
    else location.hash = hash;
  }

  let routeToken = 0;

  async function route() {
    const token = ++routeToken;
    const r = parseRoute();
    nav(r);

    if (r.name === "queue") {
      document.title = "Case queue · Witness";
      await renderQueue(token);
    } else if (r.name === "case") {
      await renderCase(r, token);
    } else if (r.name === "policy") {
      document.title = "Policy · Witness";
      await renderPolicy(token);
    } else if (r.name === "quality") {
      document.title = "Quality · Witness";
      await renderQuality(token);
    } else if (r.name === "about") {
      document.title = "About · Witness";
      renderAbout();
    } else if (r.name === "new") {
      document.title = "New case · Witness";
      renderIntake();
    }
  }

  function nav(r) {
    const active = r.name === "case" ? "cases" : r.name;
    $$(".nav a").forEach((a) => {
      if (a.dataset.nav === active) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
  }

  /* ---------------- queue ---------------- */

  function filteredCases() {
    if (state.filter === "all") return state.cases;
    if (state.filter === "needs_review")
      return state.cases.filter((c) => c.status === "NEEDS_REVIEW");
    if (state.filter === "verified") return state.cases.filter((c) => c.status === "VERIFIED");
    if (state.filter === "decided")
      return state.cases.filter((c) => c.status === "APPROVED" || c.status === "DENIED");
    if (state.filter === "awaiting")
      return state.cases.filter((c) => c.status === "INFO_REQUESTED");
    return state.cases;
  }

  function countBy(predicate) {
    return state.cases.filter(predicate).length;
  }

  async function renderQueue(token) {
    APP.innerHTML = `<div class="view"><div id="view-error" hidden></div>${skeletonTable(5, 7)}</div>`;
    try {
      const data = await api("/api/cases");
      if (token !== routeToken) return;
      state.cases = data.cases || [];
      state.stats = data.stats || null;
    } catch (e) {
      if (token !== routeToken) return;
      APP.innerHTML = `<div class="view"><div class="notice bad"><div><strong>Could not load the case queue.</strong><div class="notice-body">${esc(
        e.message
      )}</div></div></div></div>`;
      return;
    }

    if (!state.cases.length) {
      APP.innerHTML = `<div class="view">
        <div class="page-head"><div><div class="page-title"><h1>Case queue</h1></div>
        <p>No cases have been received yet.</p></div>
        <a class="btn btn-primary" href="#/new">New case</a></div>
        ${empty("The queue is empty", "Create a case to run the eligibility pipeline.", '<a class="btn" href="#/new">New case</a>')}
      </div>`;
      return;
    }

    const chips = [
      ["all", "All", state.cases.length],
      ["needs_review", "Needs review", countBy((c) => c.status === "NEEDS_REVIEW")],
      ["verified", "Verified", countBy((c) => c.status === "VERIFIED")],
      ["awaiting", "Awaiting information", countBy((c) => c.status === "INFO_REQUESTED")],
      ["decided", "Decided", countBy((c) => c.status === "APPROVED" || c.status === "DENIED")],
    ]
      .map(
        ([key, label, count]) =>
          `<button class="chip" data-filter="${key}" aria-pressed="${
            state.filter === key ? "true" : "false"
          }">${esc(label)}<span class="count">${count}</span></button>`
      )
      .join("");

    APP.innerHTML = `<div class="view">
      <div class="page-head">
        <div>
          <div class="page-title"><h1>Case queue</h1></div>
          <p>Applications waiting for an eligibility decision. The pipeline proposes; an officer decides.</p>
        </div>
        <a class="btn btn-primary" href="#/new">New case</a>
      </div>
      <div style="margin-bottom:12px"><div class="chips">${chips}</div></div>
      <div id="queue-body"></div>
    </div>`;

    $$(".chip").forEach((chip) =>
      chip.addEventListener("click", () => {
        state.filter = chip.dataset.filter;
        $$(".chip").forEach((c) =>
          c.setAttribute("aria-pressed", c.dataset.filter === state.filter ? "true" : "false")
        );
        drawQueueBody();
      })
    );

    drawQueueBody();
  }

  function drawQueueBody() {
    const rows = filteredCases();
    const body = $("#queue-body");
    if (!body) return;

    if (!rows.length) {
      body.innerHTML = empty("Nothing in this filter", "Try a different filter, or clear it.");
      return;
    }

    body.innerHTML = `<div class="table-wrap"><table>
      <caption class="sr-only">Cases by status</caption>
      <thead><tr>
        <th>Applicant</th><th>Province</th><th>Status</th><th>Assessment</th>
        <th class="num">Age</th><th>Assignee</th>
      </tr></thead>
      <tbody>
        ${rows
          .map(
            (c) => `<tr class="clickable" tabindex="0" data-case="${esc(c.id)}">
              <td><div class="cell-main">${esc(c.applicant_name)}</div>
                  <div class="cell-sub mono">${esc(c.id)}</div></td>
              <td>${esc(c.province || "—")}</td>
              <td>${statusTag(c.status)}</td>
              <td>
                ${c.outcome ? outcomeTag(c.outcome) : '<span class="cell-sub">—</span>'}
                ${c.verification ? `<div class="cell-sub">${esc(
                  (VERIFICATION[c.verification] || {}).label || c.verification
                )}</div>` : ""}
              </td>
              <td class="num nowrap">${esc(fmtAge(c.age_minutes))}</td>
              <td>${c.assignee ? esc(c.assignee) : '<span class="cell-sub">Unassigned</span>'}</td>
            </tr>`
          )
          .join("")}
      </tbody></table></div>`;

    $$("tr.clickable", body).forEach((tr) => {
      const open = () => go(`#/cases/${encodeURIComponent(tr.dataset.case)}`);
      tr.addEventListener("click", open);
      tr.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          open();
        }
      });
    });
  }

  /* ---------------- case ---------------- */

  function citationsFor(c) {
    const byDoc = {};
    c.facts.forEach((f, index) => {
      if (!f.citation || !f.citation.grounded) return;
      (byDoc[f.citation.doc_id] = byDoc[f.citation.doc_id] || []).push({
        citation: f.citation,
        index,
      });
    });
    const markIds = new Map();
    const ranges = {};
    Object.keys(byDoc).forEach((docId) => {
      const sorted = byDoc[docId].slice().sort((a, b) => a.citation.start - b.citation.start);
      ranges[docId] = sorted.map((item, n) => {
        const id = `cite-${docId}-${n}`;
        markIds.set(item.index, id);
        return { start: item.citation.start, end: item.citation.end, id };
      });
    });
    return { ranges, markIds };
  }

  function conflictGroups(c) {
    const grouped = {};
    c.facts.forEach((f) => {
      (grouped[f.key] = grouped[f.key] || []).push(f);
    });
    return Object.entries(grouped).filter(
      ([, items]) => new Set(items.map((i) => JSON.stringify(i.value))).size > 1
    );
  }

  const TABS = [
    ["evidence", "Evidence"],
    ["rules", "Rules"],
    ["verification", "Verification"],
    ["documents", "Documents"],
    ["activity", "Activity"],
  ];

  async function renderCase(r, token) {
    const reuse = state.current && state.current.id === r.id;
    if (!reuse) {
      APP.innerHTML = `<div class="view"><div class="skel" style="height:20px;width:240px;margin-bottom:12px"></div>
        <div class="skel" style="height:14px;width:420px;margin-bottom:22px"></div>
        ${skeletonTable(4, 4)}</div>`;
      try {
        const [c, audit] = await Promise.all([
          api(`/api/cases/${encodeURIComponent(r.id)}`),
          api(`/api/cases/${encodeURIComponent(r.id)}/audit`).catch(() => ({ entries: [] })),
        ]);
        if (token !== routeToken) return;
        state.current = c;
        state.audit = audit.entries || [];
        state.action = "approve";
      } catch (e) {
        if (token !== routeToken) return;
        APP.innerHTML = `<div class="view"><div class="notice bad"><div><strong>Case not found.</strong>
          <div class="notice-body">${esc(e.message)}</div></div></div>
          <p style="margin-top:14px"><a href="#/cases">Back to the case queue</a></p></div>`;
        return;
      }
    } else {
      try {
        const audit = await api(`/api/cases/${encodeURIComponent(r.id)}/audit`).catch(() => ({ entries: [] }));
        if (token !== routeToken) return;
        state.audit = audit.entries || [];
      } catch (e) {
        /* keep existing */
      }
    }

    drawCase(r);
  }

  function drawCase(r) {
    const c = state.current;
    if (!c) return;
    const tab = TABS.some(([key]) => key === r.tab) ? r.tab : "evidence";
    const { ranges, markIds } = citationsFor(c);
    const conflicts = conflictGroups(c);
    const rec = c.recommendation || { outcome: null, reasons: [] };
    const ver = c.verification || { status: null, reasons: [], checks: [] };
    const decidable = c.status === "VERIFIED" || c.status === "NEEDS_REVIEW";
    const awaiting = c.status === "INFO_REQUESTED";

    document.title = `${c.applicant_name} · Witness`;

    APP.innerHTML = `<div class="view">
      <div class="case-head">
        <div><div class="page-title"><h1>${esc(c.applicant_name)} ${statusTag(c.status)}</h1></div>
        <div class="case-meta">
          <span class="mono">${esc(c.id)}</span>
          ${c.applicant_cnic ? `<span>CNIC ${esc(c.applicant_cnic)}</span>` : ""}
          ${c.province ? `<span>${esc(c.province)}</span>` : ""}
          <span>Received ${esc(fmtAge(c.age_minutes))}</span>
          <span>${c.assignee ? "Assigned to " + esc(c.assignee) : "Unassigned"}</span>
          ${c.sla_breached ? '<span class="tag bad">Past service level</span>' : ""}
        </div></div>
        <a class="btn" href="#/cases">Back to queue</a>
      </div>

      <div id="view-error" hidden></div>

      <div class="case-grid">
        <div class="case-main">
          <div class="callout ${rec.outcome === "ELIGIBLE" ? "ok" : "warn"}">
            <div class="callout-title">Assessment: ${rec.outcome ? esc((OUTCOME[rec.outcome] || {}).label || rec.outcome) : "Pending"}</div>
            <p>${(rec.reasons || []).map(esc).join(" ")}</p>
            <p style="margin-top:6px;color:var(--faint);font-size:12px">
              The pipeline cannot deny an application. The lowest state it can reach is “Needs review”; a denial requires the officer decision.
            </p>
          </div>

          <div class="tabs" role="tablist" aria-label="Case sections">
            ${TABS.map(
              ([key, label]) =>
                `<button class="tab" role="tab" id="tab-${key}" data-tab="${key}" aria-selected="${
                  tab === key ? "true" : "false"
                }" aria-controls="panel-${key}">${label}</button>`
            ).join("")}
          </div>

          <div id="tab-body" role="tabpanel" aria-labelledby="tab-${tab}" class="section"></div>
        </div>

        <aside class="panel" aria-label="Officer decision">
          ${panelHtml(c, decidable, awaiting)}
        </aside>
      </div>
    </div>`;

    $$(".tab").forEach((el) => {
      el.addEventListener("click", () => {
        go(`#/cases/${encodeURIComponent(c.id)}/${el.dataset.tab}`);
      });
      el.addEventListener("keydown", (e) => {
        const keys = TABS.map(([k]) => k);
        const i = keys.indexOf(el.dataset.tab);
        let next = null;
        if (e.key === "ArrowRight") next = keys[(i + 1) % keys.length];
        if (e.key === "ArrowLeft") next = keys[(i - 1 + keys.length) % keys.length];
        if (next) {
          e.preventDefault();
          go(`#/cases/${encodeURIComponent(c.id)}/${next}`);
          setTimeout(() => {
            const t = $(`#tab-${next}`);
            if (t) t.focus();
          }, 30);
        }
      });
    });

    drawTab(tab, c, ranges, markIds, conflicts);
    bindPanel(c);
    drawActivity(c);

    if (state.pendingCite) {
      const target = document.getElementById(state.pendingCite);
      if (target) {
        target.scrollIntoView({ block: "center", behavior: "smooth" });
        target.classList.remove("flash");
        void target.offsetWidth;
        target.classList.add("flash");
      }
      state.pendingCite = null;
    }
  }

  function drawTab(tab, c, ranges, markIds, conflicts) {
    const host = $("#tab-body");
    if (!host) return;
    if (tab === "evidence") host.innerHTML = evidenceHtml(c, markIds, conflicts);
    else if (tab === "rules") host.innerHTML = rulesHtml(c);
    else if (tab === "verification") host.innerHTML = verificationHtml(c);
    else if (tab === "documents") host.innerHTML = documentsHtml(c, ranges);
    else host.innerHTML = "";

    $$("[data-cite]", host).forEach((btn) => {
      btn.addEventListener("click", () => {
        state.pendingCite = btn.dataset.cite;
        go(`#/cases/${encodeURIComponent(c.id)}/documents`);
      });
    });

    $$("[data-clause]", host).forEach((btn) => {
      btn.addEventListener("click", () => {
        go("#/policy");
      });
    });
  }

  function evidenceHtml(c, markIds, conflicts) {
    const conflictHtml = conflicts.length
      ? `<div class="section">
          <div class="section-head"><h2>Conflicting evidence</h2>
            <span class="sub">The verifier abstains when two documents disagree.</span></div>
          ${conflicts
            .map(([key, items]) => {
              const label = items[0].label || key;
              return `<div class="callout warn">
                <div class="callout-title">${esc(label)}: ${items.length} different values</div>
                <table style="margin-top:8px">
                  <thead><tr><th>Value</th><th>Document</th><th>Quoted text</th></tr></thead>
                  <tbody>${items
                    .map(
                      (i) => `<tr>
                        <td class="fact-value">${esc(fmtValue(key, i.value))}</td>
                        <td class="fact-source">${esc(i.citation ? i.citation.doc_id : "no source")}</td>
                        <td>${i.citation ? `<blockquote class="quote">“${esc(i.citation.quote)}”</blockquote>` : '<span class="unverified">No supporting quote</span>'}</td>
                      </tr>`
                    )
                    .join("")}</tbody>
                </table>
              </div>`;
            })
            .join("")}
        </div>`
      : "";

    const rows = c.facts
      .map((f, index) => {
        const cit = f.citation;
        const markId = markIds.get(index);
        const source = cit
          ? markId
            ? `<button class="btn-link" data-cite="${esc(markId)}">${esc(
                docTitle(c, cit.doc_id)
              )} · span ${cit.start}–${cit.end}</button>`
            : `<span class="fact-source">${esc(docTitle(c, cit.doc_id))} · span ${cit.start}–${cit.end}</span>`
          : '<span class="unverified">No source</span>';
        const quote = cit ? `<blockquote class="quote">“${esc(cit.quote)}”</blockquote>` : "";
        return `<tr>
          <td><div class="cell-main">${esc(f.label || f.key)}</div>
              <div class="cell-sub mono">${esc(f.key)}</div></td>
          <td class="fact-value">${esc(fmtValue(f.key, f.value))}</td>
          <td>${source}${quote}</td>
          <td class="nowrap">${
            cit && cit.grounded
              ? '<span class="verified">Verified</span>'
              : '<span class="unverified">Unverified</span>'
          }</td>
        </tr>`;
      })
      .join("");

    return `${conflictHtml}
      <div class="section">
        <div class="section-head"><h2>Extracted facts</h2>
          <span class="sub">Each value is tied to a quotation from the documents.</span></div>
        <div class="table-wrap"><table class="facts">
          <caption class="sr-only">Facts extracted from the case documents</caption>
          <thead><tr><th>Field</th><th>Value</th><th>Source</th><th>Grounding</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="4" class="cell-sub">No facts were extracted.</td></tr>'}</tbody>
        </table></div>
      </div>`;
  }

  function docTitle(c, docId) {
    const doc = (c.documents || []).find((d) => d.doc_id === docId);
    return doc ? doc.title : docId;
  }

  function rulesHtml(c) {
    const rows = c.rules
      .map((rule) => {
        const tone =
          rule.status === "PASS" ? "ok" : rule.status === "FAIL" ? "bad" : "warn";
        const label =
          rule.status === "PASS" ? "Met" : rule.status === "FAIL" ? "Not met" : "Cannot decide";
        return `<tr>
          <td class="nowrap mono">${esc(rule.policy_ref || "")}</td>
          <td><div class="cell-main">${esc(rule.title)}</div>
              <div class="cell-sub mono">${esc(rule.rule_id)}</div></td>
          <td><span class="tag ${tone}">${label}</span></td>
          <td>${esc(rule.detail)}</td>
        </tr>`;
      })
      .join("");

    return `<div class="section">
      <div class="section-head"><h2>Clause checks</h2>
        <span class="sub">Rules are evaluated in code. The model never decides a clause.</span></div>
      <div class="table-wrap"><table>
        <caption class="sr-only">Policy clauses and their results</caption>
        <thead><tr><th>Clause</th><th>Requirement</th><th>Result</th><th>Basis</th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
      <p class="sub">Every clause is published in the <a href="#/policy">policy</a>.</p>
    </div>`;
  }

  function verificationHtml(c) {
    const v = c.verification || { status: null, reasons: [], checks: [] };
    const reasons = (v.reasons || []).length
      ? `<ul style="margin:0;padding-left:20px">${v.reasons
          .map((r) => `<li style="margin:4px 0">${esc(r)}</li>`)
          .join("")}</ul>`
      : '<p class="sub" style="margin:0">No problems found. Every fact is supported by a quotation and the clauses were decided.</p>';

    const checks = (v.checks || [])
      .map(
        (chk) => `<tr>
          <td class="nowrap"><span class="${chk.ok ? "verified" : "unverified"}">${
          chk.ok ? "Pass" : "Fail"
        }</span></td>
          <td>${esc(checkLabel(chk.check))}</td>
          <td class="mono">${esc(chk.fact)}</td>
          <td class="cell-sub">${esc(chk.note)}</td>
        </tr>`
      )
      .join("");

    return `<div class="section">
      <div class="section-head"><h2>Independent check ${verifyTag(v.status)}</h2></div>
      <div class="callout ${v.status === "OK" ? "ok" : "warn"}">
        <div class="callout-title">${
          v.status === "OK" ? "The assessment is supported" : "The assessment was not endorsed"
        }</div>
        ${reasons}
      </div>
      ${
        checks
          ? `<details><summary class="sub" style="cursor:pointer">Show ${v.checks.length} checks</summary>
             <div class="table-wrap" style="margin-top:8px"><table>
               <thead><tr><th>Result</th><th>Check</th><th>Field</th><th>Note</th></tr></thead>
               <tbody>${checks}</tbody></table></div></details>`
          : ""
      }
    </div>`;
  }

  function checkLabel(name) {
    return (
      {
        citation_grounding: "Quotation appears in the document",
        contradiction: "Values agree across documents",
        llm_adjudication: "Model review of the quotation",
        verifier_fallback: "Fallback to deterministic checks",
      }[name] || name
    );
  }

  function documentsHtml(c, ranges) {
    if (!c.documents || !c.documents.length) {
      return empty("No documents", "This case has no source documents attached.");
    }
    return `<div class="section">
      <div class="section-head"><h2>Source documents</h2>
        <span class="sub">Highlighted text is quoted by the extracted facts.</span></div>
      <div class="doc-list">${c.documents
        .map((doc) => {
          const docRanges = ranges[doc.doc_id] || [];
          let html = "";
          let pos = 0;
          docRanges.forEach((range) => {
            if (range.start < pos) return;
            html += esc(doc.text.slice(pos, range.start));
            html += `<mark id="${range.id}">${esc(doc.text.slice(range.start, range.end))}</mark>`;
            pos = range.end;
          });
          html += esc(doc.text.slice(pos));
          return `<section class="doc">
            <header class="doc-head">
              <span class="name">${esc(doc.title)}</span>
              <span class="meta mono">${esc(doc.doc_id)} · ${doc.text.length} characters</span>
            </header>
            <div class="doc-body">${html}</div>
          </section>`;
        })
        .join("")}</div>
    </div>`;
  }

  function panelHtml(c, decidable, awaiting) {
    if (decidable) {
      return `<div class="panel-head"><h2>Officer decision</h2><span class="tag neutral plain">Required</span></div>
        <form id="decision-form" novalidate>
          <div class="panel-body">
            <div class="field">
              <label id="action-label">Decision</label>
              <div class="actions" role="radiogroup" aria-labelledby="action-label">
                ${[
                  ["approve", "Approve", "Accept the assessment"],
                  ["deny", "Deny", "Refuse the application"],
                  ["request_info", "Request information", "Ask for more evidence"],
                ]
                  .map(
                    ([value, label, hint]) => `<button type="button" class="action ${
                      value === "deny" ? "danger" : ""
                    }" role="radio" data-action="${value}" aria-checked="${
                      state.action === value ? "true" : "false"
                    }"><span class="a-name">${label}</span><span class="a-hint">${hint}</span></button>`
                  )
                  .join("")}
              </div>
            </div>

            <div class="field">
              <label for="officer">Officer name</label>
              <input id="officer" type="text" autocomplete="name" placeholder="Your full name" required />
            </div>

            <div class="field">
              <label for="reason">Reason for the decision</label>
              <textarea id="reason" placeholder="Record the basis for this decision. This is written to the audit ledger." required></textarea>
              <div style="display:flex;justify-content:space-between">
                <span class="hint">Written reasons are required and retained.</span>
                <span class="hint" id="reason-count">0 characters</span>
              </div>
              <span class="error" id="form-error" hidden></span>
            </div>

            <div class="divider"></div>

            <div class="field">
              <label for="assignee">Assigned officer</label>
              <div class="assign-row">
                <input id="assignee" type="text" placeholder="Unassigned" value="${esc(
                  c.assignee || ""
                )}" />
                <button class="btn" type="button" id="assign-btn">Assign</button>
              </div>
            </div>
          </div>
          <div class="panel-foot">
            <button class="btn btn-primary" type="submit" style="width:100%" id="submit-btn">Record decision</button>
          </div>
        </form>`;
    }

    if (awaiting) {
      return `<div class="panel-head"><h2>Awaiting information</h2>${statusTag(c.status)}</div>
        <form id="resubmit-form" novalidate>
          <div class="panel-body">
            <div class="notice info">
              <div><strong>Officer request</strong>
                <div class="notice-body">${esc(
                  (c.decision && c.decision.reason) || "More evidence was requested."
                )}</div>
              </div>
            </div>
            <div class="field">
              <label for="doc-title">New document title</label>
              <input id="doc-title" type="text" value="Supplementary evidence" />
            </div>
            <div class="field">
              <label for="doc-text">New document text</label>
              <textarea id="doc-text" placeholder="Monthly household income: PKR 40,000" required></textarea>
              <span class="hint">Form labels are read automatically.</span>
              <span class="error" id="form-error" hidden></span>
            </div>
          </div>
          <div class="panel-foot">
            <button class="btn btn-primary" type="submit" style="width:100%">Resubmit and re-run</button>
          </div>
        </form>`;
    }

    const d = c.decision || {};
    return `<div class="panel-head"><h2>Decision record</h2>${statusTag(c.status)}</div>
      <div class="panel-body">
        <div class="decision-record">
          <div class="who">${esc(d.officer || "Unknown officer")} · ${
      d.action ? esc(actionLabel(d.action)) : ""
    }</div>
          <div class="reason">${esc(d.reason || "")}</div>
          <div class="when">${esc(fmtClock(d.decided_at))}</div>
        </div>
        <div class="divider"></div>
        <p class="sub" style="margin:0">This decision is final and recorded in the ledger. A new decision cannot be recorded for this case.</p>
      </div>`;
  }

  function actionLabel(action) {
    return (
      { approve: "Approved", deny: "Denied", request_info: "Requested information" }[action] ||
      action
    );
  }

  function bindPanel(c) {
    $$("[data-action]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.action = btn.dataset.action;
        $$("[data-action]").forEach((el) =>
          el.setAttribute("aria-checked", el.dataset.action === state.action ? "true" : "false")
        );
        const submit = $("#submit-btn");
        if (submit) {
          submit.textContent =
            state.action === "approve"
              ? "Approve application"
              : state.action === "deny"
              ? "Deny application"
              : "Request information";
          submit.className =
            state.action === "deny" ? "btn btn-danger" : "btn btn-primary";
        }
      });
    });

    const reason = $("#reason");
    if (reason) {
      const counter = $("#reason-count");
      const update = () => {
        counter.textContent = `${reason.value.trim().length} characters`;
      };
      reason.addEventListener("input", update);
      update();
    }

    const form = $("#decision-form");
    if (form) form.addEventListener("submit", onDecision);

    const assignBtn = $("#assign-btn");
    if (assignBtn) assignBtn.addEventListener("click", onAssign);

    const resubmit = $("#resubmit-form");
    if (resubmit) resubmit.addEventListener("submit", onResubmit);
  }

  function formError(message) {
    const el = $("#form-error");
    if (!el) {
      notify("Could not record the decision", message, "bad");
      return;
    }
    el.hidden = false;
    el.textContent = message;
  }

  async function onDecision(event) {
    event.preventDefault();
    const c = state.current;
    if (!c) return;
    const officer = ($("#officer") && $("#officer").value.trim()) || "";
    const reason = ($("#reason") && $("#reason").value.trim()) || "";

    if (!officer) return formError("Enter the officer name.");
    if (reason.length < 3) return formError("Write a reason for the decision.");

    const btn = $("#submit-btn");
    btn.disabled = true;
    try {
      state.current = await post(`/api/cases/${encodeURIComponent(c.id)}/decision`, {
        officer,
        action: state.action,
        reason,
      });
      notify("Decision recorded", `${actionLabel(state.action)} · written to the audit ledger.`);
      go(`#/cases/${encodeURIComponent(c.id)}/activity`);
    } catch (e) {
      formError(e.message);
    } finally {
      btn.disabled = false;
    }
  }

  async function onAssign() {
    const c = state.current;
    const input = $("#assignee");
    if (!c || !input) return;
    const officer = input.value.trim();
    if (!officer) {
      notify("Assignment", "Enter an officer name first.", "bad");
      return;
    }
    try {
      state.current = await post(`/api/cases/${encodeURIComponent(c.id)}/assign`, { officer });
      notify("Case assigned", `Now assigned to ${officer}.`);
      state.audit = (await api(`/api/cases/${encodeURIComponent(c.id)}/audit`)).entries || [];
      drawCase(parseRoute());
    } catch (e) {
      notify("Could not assign", e.message, "bad");
    }
  }

  async function onResubmit(event) {
    event.preventDefault();
    const c = state.current;
    const text = ($("#doc-text") && $("#doc-text").value.trim()) || "";
    const title = ($("#doc-title") && $("#doc-title").value.trim()) || "Supplementary evidence";
    if (!text) return formError("Paste the new evidence first.");
    try {
      state.current = await post(`/api/cases/${encodeURIComponent(c.id)}/resubmit`, {
        documents: [{ title, text }],
      });
      notify("Evidence added", "The pipeline re-ran. No previous decision is carried over.");
      go(`#/cases/${encodeURIComponent(c.id)}/evidence`);
    } catch (e) {
      formError(e.message);
    }
  }

  /* ---------------- activity ---------------- */

  function drawActivity(c) {
    const host = $("#tab-body");
    if (!host || parseRoute().tab !== "activity") return;

    const items = state.audit.length
      ? state.audit
      : (c.history || []).map((h, i) => ({
          seq: i + 1,
          event: h.event,
          actor: null,
          ts: h.at,
          payload: { detail: h.detail },
        }));

    const rows = items
      .map((entry) => {
        const meta = EVENT[entry.event] || { label: entry.event, tone: "" };
        let tone = meta.tone;
        if (entry.event === "pipeline_run" && entry.payload) {
          tone = entry.payload.status === "NEEDS_REVIEW" ? "warn" : "ok";
        }
        if (entry.event === "human_decision" && entry.payload) {
          tone =
            entry.payload.action === "deny"
              ? "bad"
              : entry.payload.action === "request_info"
              ? "warn"
              : "ok";
        }
        const bits = [];
        if (entry.actor) bits.push(entry.actor);
        if (entry.payload && entry.payload.action)
          bits.push(actionLabel(entry.payload.action));
        if (entry.payload && entry.payload.detail) bits.push(entry.payload.detail);
        if (entry.payload && entry.payload.status && entry.event !== "human_decision")
          bits.push(
            (STATUS[entry.payload.status] || {}).label || entry.payload.status
          );
        return `<div class="tl-item ${tone}">
          <div class="tl-title">${esc(meta.label)}</div>
          <div class="tl-meta">${esc(fmtClock(entry.ts))}${
          bits.length ? " · " + esc(bits.join(" · ")) : ""
        }</div>
          <div class="tl-detail">#${entry.seq} · ${esc(shortHash(entry.hash))}</div>
        </div>`;
      })
      .join("");

    host.innerHTML = `<div class="section">
      <div class="section-head"><h2>Activity</h2>
        <span class="sub">Append-only ledger. Each entry includes the hash of the one before it.</span></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn" id="verify-btn">Verify ledger</button>
        <button class="btn" id="tamper-btn">Simulate tampering</button>
        <span class="sub" id="ledger-result" role="status" aria-live="polite" style="align-self:center"></span>
      </div>
      <div class="timeline">${rows || '<p class="sub">No activity recorded.</p>'}</div>
    </div>`;

    $("#verify-btn").addEventListener("click", verifyLedger);
    $("#tamper-btn").addEventListener("click", tamperLedger);
  }

  async function verifyLedger() {
    const out = $("#ledger-result");
    out.textContent = "Checking…";
    try {
      const r = await api("/api/audit/verify");
      out.innerHTML = r.ok
        ? `<span class="verified">Ledger intact</span> · ${r.checked} entries`
        : `<span class="unverified">Chain broken at entry ${r.broken_at}</span>`;
    } catch (e) {
      out.textContent = "Verification failed.";
    }
  }

  async function tamperLedger() {
    const out = $("#ledger-result");
    out.textContent = "Trying a forged copy…";
    try {
      const r = await post("/api/audit/tamper-demo");
      if (!r.tampered) {
        out.textContent = "The ledger is empty, so there is nothing to tamper with.";
        return;
      }
      out.innerHTML = `Forged copy rejected at entry ${r.tampered.broken_at} · <span class="verified">original ledger intact</span>`;
    } catch (e) {
      out.textContent = "The demonstration could not run.";
    }
  }

  /* ---------------- policy ---------------- */

  async function renderPolicy(token) {
    APP.innerHTML = `<div class="view"><div class="skel" style="height:18px;width:180px;margin-bottom:16px"></div>
      <div class="skel" style="height:220px;width:100%"></div></div>`;
    try {
      const r = await api("/api/policy");
      if (token !== routeToken) return;
      APP.innerHTML = `<div class="view">
        <div class="page-head">
          <div><div class="page-title"><h1>Policy</h1></div>
          <p>The eligibility rules this desk applies, and how each rule is decided.</p></div>
        </div>
        <div class="md">${markdown(r.rules_markdown)}</div>
      </div>`;
    } catch (e) {
      APP.innerHTML = `<div class="view"><div class="notice bad"><div><strong>Policy could not be loaded.</strong>
        <div class="notice-body">${esc(e.message)}</div></div></div></div>`;
    }
  }

  /* ---------------- quality ---------------- */

  async function renderQuality(token) {
    APP.innerHTML = `<div class="view"><div class="skel" style="height:18px;width:200px;margin-bottom:16px"></div>
      <div class="metrics-grid">${Array.from(
        { length: 4 },
        () => `<div class="metric"><div class="skel" style="height:12px;width:60%"></div>
        <div class="skel" style="height:24px;width:40%;margin-top:8px"></div></div>`
      ).join("")}</div></div>`;
    try {
      const r = await api("/api/eval");
      if (token !== routeToken) return;
      state.evaluation = r;
      const m = r.metrics || {};
      const inv = r.invariants || {};
      const rows = (r.details || [])
        .map(
          (d) => `<tr>
            <td class="mono">${esc(d.id)}</td>
            <td>${statusTag(d.status)}</td>
            <td>${d.outcome ? outcomeTag(d.outcome) : "—"}</td>
            <td>${d.verification ? verifyTag(d.verification) : "—"}</td>
            <td class="num">${d.grounded} / ${d.facts}</td>
            <td class="num">${(d.checks || []).filter((c) => c.ok).length} / ${
            (d.checks || []).length
          }</td>
          </tr>`
        )
        .join("");

      APP.innerHTML = `<div class="view">
        <div class="page-head">
          <div><div class="page-title"><h1>Quality gate</h1>${
            r.all_passed ? '<span class="tag ok">Passing</span>' : '<span class="tag bad">Failing</span>'
          }</div>
          <p>Witness re-runs the pipeline over a fixed set of cases at start-up and compares each result with a recorded expectation.</p></div>
          <button class="btn" id="rerun">Re-run</button>
        </div>

        <div class="notice ${r.all_passed ? "ok" : "bad"}" style="margin-bottom:16px">
          <div><strong>${
            r.all_passed
              ? "All expectations are met."
              : "One or more expectations are not met."
          }</strong>
            <div class="notice-body">${
              r.all_passed
                ? "The service is permitted to start. With the strict setting enabled, a failure here would stop the service from serving requests."
                : "The service would refuse to start with the strict setting enabled."
            }</div>
          </div>
        </div>

        <div class="metrics-grid">
          <div class="metric"><div class="m-label">Expectations met</div>
            <div class="m-value">${m.expectations_met || 0} / ${m.expectations_total || 0}</div>
            <div class="m-note">Recorded outcomes matched</div></div>
          <div class="metric"><div class="m-label">Grounded facts</div>
            <div class="m-value">${Math.round((m.grounding_rate || 0) * 100)}%</div>
            <div class="m-note">Facts with a verbatim quotation</div></div>
          <div class="metric"><div class="m-label">Abstention rate</div>
            <div class="m-value">${Math.round((m.abstain_rate || 0) * 100)}%</div>
            <div class="m-note">Cases escalated instead of guessed</div></div>
          <div class="metric ${inv.no_auto_deny ? "ok" : "bad"}"><div class="m-label">No automatic denial</div>
            <div class="m-value">${inv.no_auto_deny ? "Holds" : "Violated"}</div>
            <div class="m-note">Before a human decision</div></div>
        </div>

        <div class="section" style="margin-top:22px">
          <div class="section-head"><h2>Case-by-case</h2></div>
          <div class="table-wrap"><table>
            <caption class="sr-only">Quality results by case</caption>
            <thead><tr><th>Case</th><th>State</th><th>Assessment</th><th>Verification</th>
              <th class="num">Grounded</th><th class="num">Expectations</th></tr></thead>
            <tbody>${rows}</tbody>
          </table></div>
        </div>
      </div>`;

      $("#rerun").addEventListener("click", () => route());
    } catch (e) {
      APP.innerHTML = `<div class="view"><div class="notice bad"><div><strong>Quality report unavailable.</strong>
        <div class="notice-body">${esc(e.message)}</div></div></div></div>`;
    }
  }

  /* ---------------- about ---------------- */

  async function renderAbout() {
    APP.innerHTML = `<div class="view"><div class="skel" style="height:200px;width:100%"></div></div>`;
    const adapters = state.adapters || (await api("/api/adapters").catch(() => null));
    const info = await api("/api/info").catch(() => null);

    const pipeline = [
      ["Read", "The case packet is read into documents. PDF pages become citable units."],
      ["Extract", "A model proposes each value together with the exact quotation it relies on."],
      ["Check", "The quotation is verified verbatim, then seven policy clauses are evaluated in code."],
      ["Audit", "An independent verifier re-reads the result and abstains if anything is unsupported."],
      ["Decide", "An officer approves, denies or requests information, with a written reason."],
    ];

    APP.innerHTML = `<div class="view">
      <div class="page-head">
        <div><div class="page-title"><h1>About Witness</h1></div>
        <p>A decision desk for high-stakes eligibility screening. Built for Agentika 2.0 on Alternate Clouds.</p></div>
      </div>

      <div class="card" style="padding:18px 20px;margin-bottom:20px">
        <div class="callout-title" style="margin-bottom:6px">AI proposes. An independent check audits. A human decides.</div>
        <p class="sub" style="margin:0;max-width:80ch">
          Witness screens applicants against a simplified income-support policy. The model extracts
          evidence and may recommend an outcome, but it cannot decide a clause and it cannot deny an
          application. Every final decision is made by a named officer, with a written reason, and is
          recorded in a tamper-evident ledger.
        </p>
      </div>

      <div class="section">
        <div class="section-head"><h2>How a case is processed</h2></div>
        <div class="table-wrap"><table>
          <thead><tr><th style="width:110px">Stage</th><th>What happens</th></tr></thead>
          <tbody>${pipeline
            .map(
              ([name, text]) =>
                `<tr><td class="cell-main">${esc(name)}</td><td>${esc(text)}</td></tr>`
            )
            .join("")}</tbody>
        </table></div>
      </div>

      <div class="section" style="margin-top:22px">
        <div class="section-head"><h2>Deployment</h2></div>
        <dl class="kv">
          <dt>Platform</dt><dd>Alternate Clouds</dd>
          <dt>Version</dt><dd class="mono">${esc(info ? info.version : "—")}</dd>
          <dt>Document reader</dt><dd>${esc((adapters && adapters.reader) || "—")}</dd>
          <dt>Fact extraction</dt><dd>${esc((adapters && adapters.extractor) || "—")}</dd>
          <dt>Language model</dt><dd>${
            adapters && adapters.llm_configured
              ? `${esc(adapters.llm_provider)} · <span class="mono">${esc(adapters.llm_model)}</span>`
              : "Not configured"
          }</dd>
          <dt>Rule engine</dt><dd>${esc((adapters && adapters.rules) || "—")}</dd>
          <dt>Verifier</dt><dd>${esc((adapters && adapters.verifier) || "—")}</dd>
          <dt>Audit ledger</dt><dd>${esc((adapters && adapters.audit) || "—")}</dd>
        </dl>
      </div>

      <div class="section" style="margin-top:22px">
        <div class="section-head"><h2>Demonstration tools</h2>
          <span class="sub">For the live walkthrough only.</span></div>
        <div class="card" style="padding:16px;display:flex;gap:10px;flex-wrap:wrap;align-items:center">
          <button class="btn" id="reset-demo">Reset demonstration data</button>
          <span class="sub">Restores the five sample cases to their initial state. The ledger is not erased.</span>
        </div>
      </div>

      <div class="section" style="margin-top:22px">
        <div class="section-head"><h2>Credits and disclaimer</h2></div>
        <p class="sub" style="margin:0;max-width:80ch">
          Built by Glue Sticks for Agentika 2.0 (NaSCon 2026). Uses FastAPI and Uvicorn, pypdf for
          document text extraction, and a hosted language model for fact extraction. The policy is a
          simplified, synthetic demonstration inspired by social protection programmes; it is not the
          official policy of any government or agency.
        </p>
      </div>
    </div>`;

    $("#reset-demo").addEventListener("click", async (e) => {
      e.target.disabled = true;
      try {
        await post("/api/reseed");
        state.current = null;
        state.filter = "all";
        notify("Demonstration data reset", "Five sample cases restored.");
        go("#/cases");
      } catch (err) {
        notify("Reset failed", err.message, "bad");
      } finally {
        e.target.disabled = false;
      }
    });
  }

  /* ---------------- intake ---------------- */

  function samplePacket() {
    return `Form B-1: Income Support Application
Name: Fatima Noor
Age: 46 years
Province of residence: Punjab
Household size: 6 persons
Monthly household income: PKR 38,000
Owns a car: No
Land owned (acres): 0
Bank balance: PKR 9,000`;
  }

  function renderIntake() {
    APP.innerHTML = `<div class="view">
      <div class="page-head">
        <div><div class="page-title"><h1>New case</h1></div>
        <p>A case packet is read, its facts are extracted with quotations, and the policy is applied immediately.</p></div>
        <a class="btn" href="#/cases">Cancel</a>
      </div>

      <div id="view-error" hidden></div>

      <form id="intake-form" novalidate>
        <div class="form-grid">
          <div class="form-section">
            <header><h2>Applicant</h2><p>Identifies the case in the queue.</p></header>
            <div style="display:flex;flex-direction:column;gap:12px">
              <div class="field">
                <label for="i-name">Full name</label>
                <input id="i-name" type="text" placeholder="e.g. Fatima Noor" required />
              </div>
              <div class="field">
                <label for="i-cnic">CNIC <span class="hint">(optional)</span></label>
                <input id="i-cnic" type="text" placeholder="35202-0000000-0" />
              </div>
              <div class="field">
                <label for="i-province">Province <span class="hint">(optional)</span></label>
                <input id="i-province" type="text" placeholder="Punjab" />
              </div>
            </div>
          </div>

          <div class="form-section">
            <header><h2>Documents</h2><p>Upload a PDF, or paste the text of the application form.</p></header>
            <div style="display:flex;flex-direction:column;gap:12px">
              <label class="dropzone" id="dropzone" for="i-pdf">
                <input id="i-pdf" type="file" accept="application/pdf" />
                <div class="file" id="file-name">Choose a PDF</div>
                <div>or drag it here</div>
              </label>
              <div class="field">
                <label for="i-doc1">Form text</label>
                <textarea id="i-doc1" style="min-height:190px" placeholder="Paste the application form text. Use one field per line, for example:&#10;Age: 46 years&#10;Monthly household income: PKR 38,000"></textarea>
                <div style="display:flex;justify-content:space-between;align-items:center">
                  <span class="hint">Labels are read automatically.</span>
                  <button type="button" class="btn-link" id="load-sample">Load a sample packet</button>
                </div>
              </div>
            </div>
          </div>

          <div class="form-section full">
            <header><h2>Additional evidence <span class="hint">(optional)</span></h2>
              <p>Add a second document to demonstrate conflicting evidence.</p></header>
            <div>
              <textarea id="i-doc2" style="min-height:90px" placeholder="For example: Monthly household income (revised): PKR 90,000"></textarea>
            </div>
          </div>
        </div>

        <span class="error" id="form-error" hidden style="display:block;margin-top:12px"></span>

        <div style="display:flex;gap:10px;margin-top:16px">
          <button class="btn btn-primary" type="submit" id="run-btn">Run the pipeline</button>
          <a class="btn" href="#/cases">Cancel</a>
        </div>
      </form>
    </div>`;

    const dropzone = $("#dropzone");
    const fileInput = $("#i-pdf");
    const fileName = $("#file-name");

    fileInput.addEventListener("change", () => {
      fileName.textContent = fileInput.files[0] ? fileInput.files[0].name : "Choose a PDF";
    });
    ["dragenter", "dragover"].forEach((evt) =>
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.add("drag");
      })
    );
    ["dragleave", "drop"].forEach((evt) =>
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.remove("drag");
      })
    );
    dropzone.addEventListener("drop", (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        fileName.textContent = e.dataTransfer.files[0].name;
      }
    });

    $("#load-sample").addEventListener("click", () => {
      $("#i-doc1").value = samplePacket();
      $("#i-name").value = $("#i-name").value || "Fatima Noor";
    });

    $("#intake-form").addEventListener("submit", onIntake);
  }

  function readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
      reader.onerror = () => reject(new Error("The file could not be read."));
      reader.readAsDataURL(file);
    });
  }

  async function onIntake(event) {
    event.preventDefault();
    const err = $("#form-error");
    err.hidden = true;

    const name = $("#i-name").value.trim();
    if (!name) {
      err.hidden = false;
      err.textContent = "Enter the applicant name.";
      $("#i-name").focus();
      return;
    }

    const file = $("#i-pdf").files[0];
    let documents;
    if (file) {
      const base64 = await readFile(file).catch(() => "");
      if (!base64) {
        err.hidden = false;
        err.textContent = "The selected file could not be read.";
        return;
      }
      documents = [{ title: file.name, pdf_base64: base64 }];
    } else {
      const text = $("#i-doc1").value.trim();
      if (!text) {
        err.hidden = false;
        err.textContent = "Upload a PDF or paste the form text.";
        return;
      }
      documents = [{ title: "Application form", text }];
      const extra = $("#i-doc2").value.trim();
      if (extra) documents.push({ title: "Additional evidence", text: extra });
    }

    const btn = $("#run-btn");
    btn.disabled = true;
    btn.textContent = "Running…";
    try {
      const created = await post("/api/cases", {
        applicant_name: name,
        applicant_cnic: $("#i-cnic").value.trim(),
        province: $("#i-province").value.trim(),
        documents,
      });
      state.current = null;
      notify("Case created", `${created.applicant_name} · ${created.id}`);
      go(`#/cases/${encodeURIComponent(created.id)}`);
    } catch (e) {
      err.hidden = false;
      err.textContent = e.message;
    } finally {
      btn.disabled = false;
      btn.textContent = "Run the pipeline";
    }
  }

  /* ---------------- boot ---------------- */

  window.addEventListener("hashchange", route);

  if (!location.hash) {
    history.replaceState(null, "", "#/cases");
  }

  pollHealth();
  setInterval(pollHealth, 15000);
  route();
})();
