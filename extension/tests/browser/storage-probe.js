// TEST ONLY content-world probe of actual Chromium API access restrictions.
(async () => {
  try {
    await chrome.storage.local.get('byok');
    document.documentElement.dataset.gmStorageProbe = 'accessible';
  } catch {
    document.documentElement.dataset.gmStorageProbe = 'denied';
  }
  const reply = await chrome.runtime.sendMessage({type:'EXPORT_CACHE'});
  document.documentElement.dataset.gmPrivilegeProbe = reply.code;
})();
