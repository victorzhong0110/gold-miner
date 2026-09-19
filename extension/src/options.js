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
}

document.getElementById("form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const byok = {
    baseUrl: document.getElementById("baseUrl").value.trim(),
    model: document.getElementById("model").value.trim(),
    apiKey: document.getElementById("apiKey").value,
  };
  await chrome.storage.local.set({
    readingLang: document.getElementById("readingLang").value,
    interests: document
      .getElementById("interests")
      .value.split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 12),
    personalization: document.getElementById("personalization").checked,
    historyEnabled: document.getElementById("historyEnabled").checked,
    byok,
  });
  show("已保存。密钥未写入页面日志。");
});

document.getElementById("clear").addEventListener("click", async () => {
  chrome.runtime.sendMessage({ type: "CLEAR_LOCAL" }, () => {
    show("已清除 seen / feedback / cache / 可选历史。密钥与兴趣仍在，除非你手动改。");
  });
});

document.getElementById("export").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "EXPORT_CACHE" }, (resp) => {
    const blob = new Blob([JSON.stringify(resp.bundle, null, 2)], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "gold-miner-cache.json";
    a.click();
    show("已导出。包内无密钥、无私有备注。");
  });
});

document.getElementById("importBtn").addEventListener("click", () => {
  document.getElementById("importFile").click();
});

document.getElementById("importFile").addEventListener("change", async (ev) => {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  const text = await file.text();
  let bundle;
  try {
    bundle = JSON.parse(text);
  } catch {
    show("导入失败：不是 JSON。");
    return;
  }
  chrome.runtime.sendMessage({ type: "IMPORT_CACHE", bundle }, (resp) => {
    show("导入条目：" + (resp && resp.imported));
  });
});

document.getElementById("probe").addEventListener("click", async () => {
  const data = await chrome.storage.local.get({ byok: {} });
  const byok = data.byok || {};
  if (!byok.apiKey) {
    show("未运行 / owner-blocked：没有 API key。");
    return;
  }
  if (!/^https?:\/\//.test(byok.baseUrl || "")) {
    show("invalid_endpoint");
    return;
  }
  try {
    const resp = await fetch(byok.baseUrl.replace(/\/$/, "") + "/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + byok.apiKey,
      },
      body: JSON.stringify({
        model: byok.model,
        max_tokens: 8,
        messages: [{ role: "user", content: "Reply with pong" }],
      }),
    });
    show(redact("http " + resp.status + " " + (resp.ok ? "ok" : "failed"), byok.apiKey));
  } catch (err) {
    show(redact("network_error " + (err && err.name), byok.apiKey));
  }
});

load();
