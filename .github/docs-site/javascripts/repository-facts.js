(() => {
  "use strict";

  const RELEASE_VERSION = "v7.0.0";
  const SOURCE_CACHE_MARKER = "__source";
  const VERSION_SELECTOR = ".md-source__fact--version";

  const repairCachedFacts = () => {
    try {
      for (let index = 0; index < sessionStorage.length; index += 1) {
        const key = sessionStorage.key(index);
        if (!key || !key.includes(SOURCE_CACHE_MARKER)) {
          continue;
        }
        const raw = sessionStorage.getItem(key);
        if (!raw) {
          continue;
        }
        const facts = JSON.parse(raw);
        if (!facts || typeof facts !== "object" || Array.isArray(facts)) {
          continue;
        }
        if (typeof facts.version === "string" && facts.version !== RELEASE_VERSION) {
          facts.version = RELEASE_VERSION;
          sessionStorage.setItem(key, JSON.stringify(facts));
        }
      }
    } catch (_error) {
      // The visible value is still repaired when storage is unavailable or restricted.
    }
  };

  const repairVisibleFacts = () => {
    for (const version of document.querySelectorAll(VERSION_SELECTOR)) {
      if (version.textContent.trim() !== RELEASE_VERSION) {
        version.textContent = RELEASE_VERSION;
      }
    }
  };

  repairCachedFacts();
  repairVisibleFacts();

  const observer = new MutationObserver(repairVisibleFacts);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.setTimeout(() => observer.disconnect(), 5000);
})();
