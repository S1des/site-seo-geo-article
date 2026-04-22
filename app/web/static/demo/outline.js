document.addEventListener("DOMContentLoaded", () => {
  const authForm = document.getElementById("auth-form");
  const outlineForm = document.getElementById("outline-form");
  const tokenBtn = document.getElementById("token-btn");
  const outlineBtn = document.getElementById("outline-btn");
  const copyBtn = document.getElementById("copy-outline-btn");
  const clearBtn = document.getElementById("clear-outline-btn");
  const tokenPill = document.getElementById("token-pill");
  const tokenNote = document.getElementById("token-note");
  const tokenDisplay = document.getElementById("token-display");
  const tokenMeta = document.getElementById("token-meta");
  const tokenValue = document.getElementById("token-value");
  const outlineMeta = document.getElementById("outline-meta");
  const outlineOutput = document.getElementById("outline-output");
  const suggestionsNode = document.getElementById("outline-suggestions");
  const linksNode = document.getElementById("outline-links");
  const apiJson = document.getElementById("api-json");
  let accessToken = "";

  async function requestJson(url, options = {}) {
    try {
      const response = await fetch(url, options);
      const rawText = await response.text();
      let data = null;
      try {
        data = rawText ? JSON.parse(rawText) : {};
      } catch {
        data = {
          success: false,
          message: rawText ? `Non-JSON response: ${rawText.slice(0, 180)}` : "Empty response body",
        };
      }
      return {
        ok: response.ok,
        status: response.status,
        data,
      };
    } catch (error) {
      return {
        ok: false,
        status: 0,
        data: {
          success: false,
          message: error?.message || "Network request failed",
        },
      };
    }
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function renderTokenState(payload) {
    accessToken = payload?.data?.access_token || "";
    const tier = payload?.data?.access_tier || "authorized";
    const expiresAt = payload?.data?.expires_at || "";
    tokenPill.textContent = accessToken ? `${tier} token` : "No token";
    if (accessToken) {
      tokenNote.textContent = `Bearer token is active until ${expiresAt}. The demo will attach it automatically to outline requests.`;
      tokenMeta.textContent = `${tier.toUpperCase()} access · expires at ${expiresAt}`;
      tokenValue.textContent = accessToken;
      tokenDisplay.classList.remove("hidden");
      return;
    }
    tokenNote.textContent =
      "Token exchange happens once here, then the demo automatically sends `Authorization: Bearer ...` when you generate outlines.";
    tokenMeta.textContent = "Standard access · valid for 1 day";
    tokenValue.textContent = "";
    tokenDisplay.classList.add("hidden");
  }

  function resetOutlineUi(message) {
    outlineBtn.disabled = false;
    outlineBtn.innerHTML = "Generate Outline";
    outlineMeta.textContent = message || "No outline yet";
  }

  function renderSuggestions(items) {
    if (!Array.isArray(items) || !items.length) {
      suggestionsNode.innerHTML = '<div class="empty">Writing suggestions will appear here.</div>';
      return;
    }
    suggestionsNode.innerHTML = items
      .map((item) => `<article class="outline-item"><p>${escapeHtml(item)}</p></article>`)
      .join("");
  }

  function renderLinks(items) {
    if (!Array.isArray(items) || !items.length) {
      linksNode.innerHTML = '<div class="empty">Recommended internal links will appear here.</div>';
      return;
    }
    linksNode.innerHTML = items
      .map(
        (item) => `
          <article class="outline-item">
            <strong>${escapeHtml(item.label || item.url)}</strong>
            <p><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.url)}</a></p>
            <p>${escapeHtml(item.reason || "")}</p>
          </article>
        `
      )
      .join("");
  }

  function bindShellTabs() {
    document.querySelectorAll(".shell-tab-button").forEach((button) => {
      button.addEventListener("click", () => {
        const tab = button.dataset.shellTab;
        document
          .querySelectorAll(".shell-tab-button")
          .forEach((item) => item.classList.toggle("active", item === button));
        document.querySelectorAll(".shell-tab-panel").forEach((panel) => {
          panel.classList.toggle("active", panel.dataset.shellPanel === tab);
        });
      });
    });
  }

  authForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    tokenBtn.disabled = true;
    tokenBtn.innerHTML = "Requesting...";
    const formData = new FormData(authForm);
    const result = await requestJson("/api/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_key: formData.get("access_key") }),
    });
    const data = result.data || {};
    apiJson.textContent = JSON.stringify(data, null, 2);
    renderTokenState(data.success ? data : null);
    tokenBtn.disabled = false;
    tokenBtn.innerHTML = "Get 1-Day Token";
  });

  outlineForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!accessToken) {
      outlineMeta.textContent = "Exchange a bearer token first";
      return;
    }

    outlineBtn.disabled = true;
    outlineBtn.innerHTML = "Generating...";
    outlineMeta.textContent = "Generating outline...";
    outlineOutput.textContent = "Generating outline...";
    renderSuggestions([]);
    renderLinks([]);
    apiJson.textContent = JSON.stringify({ status: "submitting" }, null, 2);

    const formData = new FormData(outlineForm);
    const productUrls = String(formData.get("product_urls") || "")
      .split(/\n+/)
      .map((item) => item.trim())
      .filter(Boolean);
    const payload = {
      category: formData.get("category"),
      provider: formData.get("provider") || "openai",
      keyword: formData.get("keyword"),
      site_url: formData.get("site_url"),
      product_urls: productUrls,
    };

    const result = await requestJson("/api/outline", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(payload),
    });
    const data = result.data || {};
    apiJson.textContent = JSON.stringify(data, null, 2);

    if (!data.success) {
      outlineOutput.textContent = data.message || "Unable to generate outline.";
      resetOutlineUi("Outline failed");
      return;
    }

    const outline = data.data || {};
    outlineMeta.textContent = `${outline.category?.toUpperCase() || "OUTLINE"} · ${outline.generation_mode || "ready"}`;
    outlineOutput.textContent = outline.outline_markdown || "";
    renderSuggestions(outline.writing_suggestions || []);
    renderLinks(outline.recommended_internal_links || []);
    resetOutlineUi(outlineMeta.textContent);
  });

  copyBtn.addEventListener("click", async () => {
    const value = outlineOutput.textContent || "";
    if (!value || value === "Generate an outline to preview the result here.") {
      outlineMeta.textContent = "No outline to copy";
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      outlineMeta.textContent = "Outline copied";
    } catch {
      outlineMeta.textContent = "Copy failed";
    }
  });

  clearBtn.addEventListener("click", () => {
    outlineOutput.textContent = "Generate an outline to preview the result here.";
    renderSuggestions([]);
    renderLinks([]);
    apiJson.textContent = "{}";
    resetOutlineUi("No outline yet");
  });

  renderTokenState(null);
  bindShellTabs();
});
