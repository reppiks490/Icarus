"use strict";
(() => {
  let bearer = "";
  let currentWorkId = "";
  const $ = (id) => document.getElementById(id);
  const notice = (message) => { $("notice").textContent = message; };
  const split = (value) => value.split(",").map((v) => v.trim()).filter(Boolean);
  const requestId = () => crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

  async function api(path, options = {}) {
    if (!bearer) throw new Error("Connect first.");
    const response = await fetch(path, {
      ...options,
      headers: { Authorization: `Bearer ${bearer}`, "Content-Type": "application/json", ...(options.headers || {}) },
      cache: "no-store",
      credentials: "same-origin",
      referrerPolicy: "no-referrer",
    });
    const value = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(value.message || `Request failed (${response.status}).`);
    return value;
  }

  async function refreshWork() {
    if (!currentWorkId) throw new Error("Load or create a work item first.");
    const value = await api(`/v1/work/${encodeURIComponent(currentWorkId)}`);
    $("work-view").textContent = JSON.stringify({ work: value.work, events: value.events }, null, 2);
    return value.work;
  }

  $("auth-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    bearer = $("token").value;
    $("token").value = "";
    try {
      const value = await api("/v1/identity");
      $("identity").textContent = `Connected as ${value.principal_id} (${value.principal_kind})`;
      $("disconnect").hidden = false;
      notice("Authenticated command access is ready.");
    } catch (error) {
      bearer = "";
      $("identity").textContent = "Disconnected";
      notice(error.message);
    }
  });

  $("disconnect").addEventListener("click", () => {
    bearer = "";
    currentWorkId = "";
    $("identity").textContent = "Disconnected";
    $("disconnect").hidden = true;
    $("work-view").textContent = "No work loaded.";
    $("incident-view").textContent = "";
    notice("Disconnected. The token was cleared from page memory.");
  });

  $("create-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const constraints = JSON.parse(form.get("constraints") || "{}");
      const value = await api("/v1/work", { method: "POST", body: JSON.stringify({
        target_kind: "principal", target_id: form.get("target_id"), work_kind: form.get("work_kind"),
        idempotency_key: requestId(), objective: form.get("objective"),
        constraints,
        required_capabilities: split(form.get("required_capabilities")),
      }) });
      currentWorkId = value.work.work_id;
      $("work-id").value = currentWorkId;
      $("work-view").textContent = JSON.stringify({ work: value.work, events: value.events }, null, 2);
      notice(`Created work ${currentWorkId}.`);
    } catch (error) { notice(error.message); }
  });

  $("load-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    currentWorkId = $("work-id").value.trim();
    try { await refreshWork(); notice("Work loaded."); } catch (error) { notice(error.message); }
  });

  $("work-list-refresh").addEventListener("click", async () => {
    try {
      const value = await api("/v1/work?limit=100");
      $("work-list").textContent = JSON.stringify(value.works, null, 2);
    } catch (error) { notice(error.message); }
  });

  $("transition-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const data = JSON.parse(form.get("data") || "{}");
      const work = await refreshWork();
      const value = await api(`/v1/work/${encodeURIComponent(currentWorkId)}/transitions`, { method: "POST", body: JSON.stringify({
        transition: form.get("transition"), operation_id: form.get("operation_id"),
        expected_head_event_id: work.head_event_id, data,
      }) });
      $("work-view").textContent = JSON.stringify({ work: value.work, events: value.events }, null, 2);
      const state = value.result.conflict_code || value.result.state || "applied";
      const coordination = value.automatic_coordination?.status === "decomposition_pending" ? " The declared child plan needs a manual retry." : "";
      notice(`Transition recorded: ${state}.${coordination}`);
    } catch (error) { notice(error.message); }
  });

  $("presence-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const value = await api("/v1/presence", { method: "POST", body: JSON.stringify({
        capabilities: split(form.get("capabilities")), ttl_seconds: Number(form.get("ttl_seconds")), status: "available",
      }) });
      $("presence-view").textContent = JSON.stringify(value, null, 2);
      notice("Capability presence advertised with an expiring lease.");
    } catch (error) { notice(error.message); }
  });

  $("presence-refresh").addEventListener("click", async () => {
    try { const value = await api("/v1/presence"); $("presence-view").textContent = JSON.stringify(value.presence, null, 2); }
    catch (error) { notice(error.message); }
  });

  $("presence-withdraw").addEventListener("click", async () => {
    try {
      const value = await api("/v1/presence/withdraw", { method: "POST", body: "{}" });
      notice(value.withdrawn ? "Presence withdrawn." : "No active presence lease was found.");
    } catch (error) { notice(error.message); }
  });

  $("escalation-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!currentWorkId) return notice("Load or create a work item first.");
    const form = new FormData(event.currentTarget);
    try {
      const value = await api(`/v1/work/${encodeURIComponent(currentWorkId)}/escalations`, { method: "POST", body: JSON.stringify({
        target_principal: form.get("target_principal"), operation_id: form.get("operation_id"),
      }) });
      notice(`Escalation routed to ${value.result.selected_principal}.`);
    } catch (error) { notice(error.message); }
  });

  $("council-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!currentWorkId) return notice("Load or create a work item first.");
    const form = new FormData(event.currentTarget);
    const council = encodeURIComponent(form.get("council_id"));
    try {
      const value = await api(`/v1/work/${encodeURIComponent(currentWorkId)}/councils/${council}/votes`, { method: "POST", body: JSON.stringify({
        vote: form.get("vote"), claim: form.get("claim"), operation_id: form.get("operation_id"),
      }) });
      notice(`Council review recorded: ${value.result.conflict_code || "applied"}.`);
    } catch (error) { notice(error.message); }
  });

  $("council-refresh").addEventListener("click", async () => {
    if (!currentWorkId) return notice("Load or create a work item first.");
    const council = encodeURIComponent(new FormData($("council-form")).get("council_id"));
    try {
      const value = await api(`/v1/work/${encodeURIComponent(currentWorkId)}/councils/${council}`);
      $("council-view").textContent = JSON.stringify(value.council, null, 2);
    } catch (error) { notice(error.message); }
  });

  $("decompose-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!currentWorkId) return notice("Load or create a work item first.");
    const form = new FormData(event.currentTarget);
    try {
      const tasks = JSON.parse(form.get("tasks"));
      const value = await api(`/v1/work/${encodeURIComponent(currentWorkId)}/decompositions`, { method: "POST", body: JSON.stringify({
        decomposition_id: form.get("decomposition_id"), tasks,
      }) });
      notice(`Created ${value.result.children.length} child work item(s).`);
    } catch (error) { notice(error.message); }
  });

  $("synthesis-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!currentWorkId) return notice("Load or create a work item first.");
    const form = new FormData(event.currentTarget);
    try {
      const value = await api(`/v1/work/${encodeURIComponent(currentWorkId)}/syntheses`, { method: "POST", body: JSON.stringify({
        child_work_ids: split(form.get("child_work_ids")), summary: form.get("summary"),
        operation_id: form.get("operation_id"), complete: form.get("complete") === "on",
      }) });
      await refreshWork();
      notice("Synthesis event recorded with child-head evidence references.");
    } catch (error) { notice(error.message); }
  });

  $("incident-open-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const members = split(new FormData(event.currentTarget).get("members"));
      const value = await api(`/v1/work/${encodeURIComponent(currentWorkId)}/incidents`, { method: "POST", body: JSON.stringify({ members }) });
      $("incident-view").textContent = JSON.stringify(value.result, null, 2);
      notice("Incident room opened in the canonical event journal.");
    } catch (error) { notice(error.message); }
  });

  $("incident-message-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const value = await api(`/v1/work/${encodeURIComponent(currentWorkId)}/incidents/messages`, { method: "POST", body: JSON.stringify({
        body: form.get("body"), operation_id: form.get("operation_id"),
      }) });
      notice(`Incident update recorded as event ${value.result.event_id}.`);
    } catch (error) { notice(error.message); }
  });

  $("incident-refresh").addEventListener("click", async () => {
    try { const value = await api(`/v1/work/${encodeURIComponent(currentWorkId)}/incidents`); $("incident-view").textContent = JSON.stringify(value.result.events, null, 2); }
    catch (error) { notice(error.message); }
  });

  $("incident-close").addEventListener("click", async () => {
    if (!currentWorkId) return notice("Load or create a work item first.");
    try {
      await api(`/v1/work/${encodeURIComponent(currentWorkId)}/incidents/close`, { method: "POST", body: "{}" });
      notice("Incident room closed.");
    } catch (error) { notice(error.message); }
  });
})();
