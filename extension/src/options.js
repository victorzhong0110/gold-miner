/* Options page is a trusted extension context. */

function show(msg) {
  document.getElementById("status").textContent = msg;
}

function redact(text, key) {
  let s = String(text || "");
  if (key) s = s.split(key).join("[redacted]");
  return s.replace(/sk-[A-Za-z0-9]{8,}/g, "[redacted]");
}

async function load() {
  const data = await chrome.storage.local.get({
    readingLang: "zh",
    interests: [],
    personalization: true,
    historyEnabled: false,
    byok: { baseUrl: "", model: "", apiKey: "" },
  });
  document.getElementById("readingLang").value = data.readingLang;
  document.getElementById("interests").value = (data.interests || []).join(", ");
  document.getElementById("personalization").checked = data.personalization !== false;
  document.getElementById("historyEnabled").checked = Boolean(data.historyEnabled);
  document.getElementById("baseUrl").value = data.byok.baseUrl || "";
  document.getElementById("model").value = data.byok.model || "";
  document.getElementById("apiKey").value = data.byok.apiKey || "";
  chrome.runtime.sendMessage({ type: "GET_PUBLIC_SETTINGS" }, (resp) => {
    if (resp && resp.settings && resp.settings.storageIsolated === false) {
      show("存储隔离失败，密钥不会保存。");
    }
  });
}

document.getElementById("form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const settings = {
    readingLang: document.getElementById("readingLang").value,
    interests: document
      .getElementById("interests")
      .value.split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 12),
    personalization: document.getElementById("personalization").checked,
    historyEnabled: document.getElementById("historyEnabled").checked,
    byok: {
      baseUrl: document.getElementById("baseUrl").value.trim(),
      model: document.getElementById("model").value.trim(),
      apiKey: document.getElementById("apiKey").value,
    },
  };
  if (settings.byok.baseUrl) {
    const endpoint = GoldMinerShared.endpointUrl(settings.byok.baseUrl);
    if (!endpoint) { show("端点无效 / Invalid endpoint"); return; }
    const granted = await chrome.permissions.request({origins: [new URL(endpoint).origin + "/*"]});
    if (!granted) { show("未授予端点权限 / Endpoint permission denied"); return; }
    settings.byok.baseUrl = endpoint;
  }
  chrome.runtime.sendMessage({ type: "SAVE_SETTINGS", settings }, (resp) => {
    if (chrome.runtime.lastError) {
      show("保存失败。");
      return;
    }
    if (resp && resp.code === "storage_isolation_failed") {
      show("存储隔离失败，密钥未保存。语言与兴趣已保存。");
      return;
    }
    if (!resp || resp.code !== "ok") {
      show("保存失败：" + ((resp && resp.code) || "bad_response"));
      return;
    }
    show("已保存。密钥未写入页面日志。");
  });
});

document.getElementById("clear").addEventListener("click", async () => {
  chrome.runtime.sendMessage({ type: "CLEAR_LOCAL" }, () => {
    show("已清除 seen / feedback / cache / 可选历史。密钥与兴趣仍在，除非你手动改。");
  });
});

document.getElementById("export").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "EXPORT_CACHE" }, (resp) => {
    if (chrome.runtime.lastError || !resp || resp.code !== "ok") { show("导出失败 / Export failed"); return; }
    const blob = new Blob([JSON.stringify(resp.bundle, null, 2)], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "gold-miner-cache.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    show("已导出。包内无密钥、无私有备注。");
  });
});

document.getElementById("importBtn").addEventListener("click", () => {
  document.getElementById("importFile").click();
});

document.getElementById("importFile").addEventListener("change", async (ev) => {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) { show("文件超过 2 MB / File exceeds 2 MB"); return; }
  const text = await file.text();
  let bundle;
  try {
    bundle = JSON.parse(text);
  } catch {
    show("导入失败：不是 JSON。");
    return;
  }
  chrome.runtime.sendMessage({ type: "IMPORT_CACHE", bundle }, (resp) => {
    if (chrome.runtime.lastError || !resp || resp.code !== "ok") { show("导入失败 / Import failed"); return; }
    show("导入条目 / Imported entries: " + resp.imported);
  });
});

let probeRevision = 0;
let probeController = null;
function currentByok() {
  return {baseUrl: document.getElementById("baseUrl").value.trim(),
    model: document.getElementById("model").value.trim(),
    apiKey: document.getElementById("apiKey").value};
}
for (const id of ["baseUrl", "model", "apiKey"]) {
  for (const event of ["input", "change"]) document.getElementById(id).addEventListener(event, () => {
    probeRevision++;
    probeController?.abort();
    show("配置已修改，当前输入未探测 / Changed inputs have not been tested");
  });
}

document.getElementById("probe").addEventListener("click", async () => {
  probeController?.abort();
  const revision = ++probeRevision;
  const byok = currentByok();
  const current = () => revision === probeRevision;
  const report = msg => { if (current()) show(redact(msg, byok.apiKey)); };
  if (!byok.apiKey.trim()) { report("未运行 / owner-blocked：没有 API key。"); return; }
  if (!byok.model) { report("invalid_model"); return; }
  const endpoint = GoldMinerShared.endpointUrl(byok.baseUrl);
  if (!endpoint) { report("invalid_endpoint"); return; }
  const host = new URL(endpoint).hostname;
  try {
    // Probe current inputs without saving credentials or other settings.
    const granted = await chrome.permissions.request({origins: [new URL(endpoint).origin + "/*"]});
    if (!current()) return;
    if (!granted) { report("未授予端点权限 / Endpoint permission denied"); return; }
    const controller = new AbortController();
    probeController = controller;
    const timer = setTimeout(() => controller.abort(), 12000);
    report("探测中 / Testing " + host + " · " + byok.model);
    try {
      const resp = await fetch(endpoint + "/chat/completions", {
        method: "POST", redirect: "error", signal: controller.signal,
        headers: {"Content-Type": "application/json", Authorization: "Bearer " + byok.apiKey},
        body: JSON.stringify({model: byok.model, max_tokens: 2048,
          messages: [{role: "user", content: "Reply with the single word pong."}]}),
      });
      let data;
      try { data = await resp.json(); } catch {}
      let code = GoldMinerShared.modelResponseCode(resp.status, data);
      if (code === "ok" && !/^pong[.!]?$/i.test(GoldMinerShared.finalModelText(data.choices[0].message.content))) code = "unexpected_model_output";
      report("http " + resp.status + " " + code + " (" + host + " · " + byok.model + ")" +
        (code === "auth_rejected" ? GoldMinerShared.authHint(endpoint) : ""));
    } finally { clearTimeout(timer); if (probeController === controller) probeController = null; }
  } catch (err) { report("network_error " + (err?.name || "Error") + " (" + host + ")"); }
});

load();
