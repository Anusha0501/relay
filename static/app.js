const state = {
  tenant: "northwind",
  scenario: null,
  graph: null,
  sessionId: "",
};

const $ = (id) => document.getElementById(id);

async function api(path, options) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || response.statusText);
  }
  return body;
}

function showError(error) {
  const node = $("error");
  node.hidden = !error;
  node.textContent = error ? error.message || String(error) : "";
}

async function boot() {
  const health = await api("/api/health");
  $("backend").textContent = health.backend;
  const note = $("note");
  note.hidden = !health.note;
  note.textContent = health.note || "";
  const select = $("tenant");
  select.innerHTML = "";
  health.tenants.forEach((tenant) => {
    const option = document.createElement("option");
    option.value = tenant;
    option.textContent = tenant;
    select.appendChild(option);
  });
  select.value = state.tenant;
  select.addEventListener("change", () => loadTenant(select.value));
  $("reset").addEventListener("click", resetGraph);
  $("run-memory").addEventListener("click", () => run("memory"));
  $("run-next").addEventListener("click", () => run("memory"));
  $("run-owner").addEventListener("click", () => run("owner"));
  $("outcome-box").addEventListener("click", onOutcome);
  const cypher = await api("/api/cypher");
  $("cypher").innerHTML = cypher
    .map((item) => `<h3>${item.name}</h3><pre>${escapeHtml(item.query)}</pre>`)
    .join("");
  await loadTenant(state.tenant);
}

async function loadTenant(tenant) {
  state.tenant = tenant;
  state.sessionId = "";
  showError(null);
  const detail = await api(`/api/tenants/${tenant}`);
  $("blurb").textContent = detail.blurb;
  $("scenarios").innerHTML = "";
  detail.scenarios.forEach((scenario, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "scenario" + (index === 0 ? " active" : "");
    button.innerHTML = `<strong>${escapeHtml(scenario.title)}</strong><span>${escapeHtml(scenario.detail)}</span>`;
    button.addEventListener("click", () => {
      state.scenario = scenario;
      document.querySelectorAll(".scenario").forEach((node) => node.classList.remove("active"));
      button.classList.add("active");
    });
    $("scenarios").appendChild(button);
    if (index === 0) state.scenario = scenario;
  });
  $("questions").innerHTML = "";
  detail.questions.forEach((question) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = question.title;
    button.addEventListener("click", () => ask(question));
    $("questions").appendChild(button);
  });
  $("answer").textContent = "Ask a question. The answer is a traversal, with the Cypher beside the submission.";
  await Promise.all([refreshGraph(), refreshMemory()]);
  clearDecision();
}

function clearDecision() {
  $("kicker").textContent = "No decision yet";
  $("headline").textContent = "The owner policy and the graph crew disagree.";
  $("summary").textContent = "Run the crew. It follows a prior incident to the cause, skips the runbook that failed, and writes a handoff.";
  $("contrast").hidden = true;
  $("path").innerHTML = "";
  $("agents").innerHTML = "";
  $("coord").innerHTML = "";
  $("outcome-box").hidden = true;
  $("algos").innerHTML = "";
}

async function refreshGraph() {
  state.graph = await api(`/api/tenants/${state.tenant}/graph`);
  $("counts").textContent = `${state.graph.counts.nodes} nodes · ${state.graph.counts.edges} edges`;
  drawGraph();
  const people = state.graph.nodes.filter((node) => node.label === "Person");
  $("roster").innerHTML = people
    .map((person) => {
      const flags = [
        person.on_call ? "on call" : "",
        person.available ? "available" : "off shift",
      ].filter(Boolean).join(" · ");
      return `<li class="${person.on_call ? "on" : ""}"><strong>${escapeHtml(person.name)}</strong> ${escapeHtml(flags)}</li>`;
    })
    .join("");
}

async function refreshMemory() {
  const memory = await api(`/api/tenants/${state.tenant}/memory`);
  for (const kind of ["episodic", "semantic", "procedural"]) {
    const items = memory[kind] || [];
    $(`mem-${kind}`).innerHTML = items.length
      ? items.map((item) => `<li>${escapeHtml(item.text)}</li>`).join("")
      : "<li>Nothing written yet.</li>";
  }
}

async function run(policy) {
  if (!state.scenario) return;
  showError(null);
  const buttons = [$("run-memory"), $("run-owner")];
  buttons.forEach((button) => { button.disabled = true; });
  try {
    const result = await api(`/api/tenants/${state.tenant}/incidents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        service: state.scenario.service,
        symptom: state.scenario.symptom,
        policy,
      }),
    });
    renderDecision(result);
    await Promise.all([refreshGraph(), refreshMemory()]);
    drawGraph(result);
    markRoster(result);
  } catch (error) {
    showError(error);
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
}

function renderDecision(result) {
  const decision = result.decision;
  state.sessionId = result.policy === "memory" ? result.session_id : "";
  $("kicker").textContent = result.policy === "owner"
    ? "Owner policy"
    : result.continued_from
      ? "Next shift read the handoff"
      : "Graph crew";
  $("headline").textContent = `${decision.assignee_name} · ${decision.procedure_name}`;
  $("summary").textContent = decision.summary;
  const owner = result.owner_would_have;
  const changed = owner && (owner.assignee_id !== decision.assignee_id || owner.procedure_id !== decision.procedure_id);
  $("contrast").hidden = !changed;
  if (changed) {
    $("contrast").innerHTML = `
      <article class="wrong"><span class="kicker">On-call policy</span><strong>${escapeHtml(owner.assignee_name)}</strong><p>${escapeHtml(owner.procedure_name)}</p></article>
      <article class="right"><span class="kicker">Graph crew</span><strong>${escapeHtml(decision.assignee_name)}</strong><p>${escapeHtml(decision.procedure_name)}</p></article>`;
  }
  $("path").innerHTML = (result.path || []).map((step) => `<li><strong>${escapeHtml(step.title)}</strong><span>${escapeHtml(step.detail)}</span></li>`).join("");
  $("agents").innerHTML = (result.agents || []).map((agent) => `<article><strong>${escapeHtml(agent.name)}</strong><small>${escapeHtml(agent.track)}</small><span>${escapeHtml(agent.summary)}</span></article>`).join("");
  $("coord").innerHTML = (result.coordination || []).map((edge) => `<span>${escapeHtml(edge.agent)} ${escapeHtml(edge.rel)} ${escapeHtml(edge.label)}</span>`).join("");
  $("outcome-box").hidden = result.policy !== "memory";
  $("outcome-note").textContent = result.continued_from ? `Continued handoff ${result.continued_from}.` : "";
  const algos = result.algorithms || {};
  const rank = (algos.pagerank || []).slice(0, 3).map((row) => row.name).join(", ");
  const parts = [];
  if (rank) parts.push(`PageRank: ${rank}`);
  if (algos.shortest_path && algos.shortest_path.length) parts.push(`Path: ${algos.shortest_path.join(" → ")}`);
  if (algos.components && algos.components.length) {
    const ids = new Set(algos.components.map((row) => row.component));
    parts.push(`${ids.size} components`);
  }
  $("algos").textContent = parts.join("  ·  ");
}

function markRoster(result) {
  const picked = result.decision.assignee_name;
  document.querySelectorAll(".roster li").forEach((item) => {
    if (item.textContent.includes(picked)) item.classList.add("picked");
  });
}

async function onOutcome(event) {
  const result = event.target.dataset.result;
  if (!result || !state.sessionId) return;
  showError(null);
  try {
    await api(`/api/tenants/${state.tenant}/sessions/${state.sessionId}/outcome`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result, note: result === "failed" ? "Recorded from the demo." : "Recovered." }),
    });
    $("outcome-note").textContent = result === "failed"
      ? "Failure is now procedural memory. Run the crew again."
      : "Success is in episodic memory. Run the crew again and it will continue this handoff only if you left it open — a success closes it.";
    state.sessionId = "";
    await refreshMemory();
  } catch (error) {
    showError(error);
  }
}

async function ask(question) {
  showError(null);
  try {
    const service = question.needs_service ? state.scenario.service : null;
    const result = await api(`/api/tenants/${state.tenant}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question.id, service }),
    });
    const lines = result.rows.length
      ? result.rows.map((row) => Object.values(row).flat().filter((value) => value !== null && value !== "").join(" · ")).join("\n")
      : "No matching path.";
    $("answer").textContent = `${result.title}\n${lines}`;
  } catch (error) {
    showError(error);
  }
}

async function resetGraph() {
  showError(null);
  await api(`/api/tenants/${state.tenant}/reset`, { method: "POST" });
  await loadTenant(state.tenant);
}

function drawGraph(result) {
  const canvas = $("graph");
  const ctx = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 640;
  const height = Math.round(width * 0.62);
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#14180f";
  ctx.fillRect(0, 0, width, height);

  const nodes = (state.graph.nodes || []).filter((node) => node.label === "Service");
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const edges = (state.graph.edges || []).filter((edge) => edge.type === "DEPENDS_ON" || edge.type === "ROUTES_TO");
  const alertId = result && result.service ? result.service.id : state.scenario && state.scenario.service;
  const causeId = result && result.decision ? result.decision.cause_id : "";

  const point = (node) => ({
    x: 28 + (Number(node.x) / 100) * (width - 56),
    y: 20 + (Number(node.y) / 100) * (height - 48),
  });

  ctx.lineWidth = 1.4;
  edges.forEach((edge) => {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) return;
    const a = point(source);
    const b = point(target);
    ctx.strokeStyle = edge.type === "ROUTES_TO" ? "#e6a85c" : "#59614c";
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  });

  nodes.forEach((node) => {
    const { x, y } = point(node);
    const picked = node.id === alertId || node.id === causeId;
    ctx.beginPath();
    ctx.fillStyle = node.id === causeId ? "#d5e2b8" : node.id === alertId ? "#e6a85c" : "#262b1d";
    ctx.strokeStyle = picked ? "#f3ecdf" : "#3a4030";
    ctx.lineWidth = picked ? 2 : 1;
    ctx.arc(x, y, picked ? 8 : 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = picked ? "#f3ecdf" : "#b7b09f";
    ctx.font = "11px Outfit, sans-serif";
    ctx.textAlign = "center";
    const short = {
      storefront: "Storefront",
      "billing-api": "Billing",
      notifications: "Notify",
      "checkout-api": "Checkout",
      "payments-gateway": "Payments",
      "fraud-service": "Fraud",
      "redis-cache": "Redis",
      ledger: "Ledger",
      "postgres-primary": "Primary",
      "postgres-replica": "Replica",
      "experiments-lab": "Lab",
      "shop-web": "Shop",
      "search-api": "Search",
      "ranking-model": "Ranker",
      elastic: "Elastic",
      ingest: "Ingest",
      "sandbox-lab": "Lab",
    };
    ctx.fillText(short[node.id] || node.name, x, y + 18);
  });
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}

window.addEventListener("resize", () => drawGraph());
boot().catch(showError);
