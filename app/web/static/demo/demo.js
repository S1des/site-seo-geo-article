document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("task-form");
  const submitBtn = document.getElementById("submit-btn");
  const taskMeta = document.getElementById("task-meta");
  const summary = document.getElementById("summary");
  const results = document.getElementById("results");
  const apiJson = document.getElementById("api-json");
  const clearBtn = document.getElementById("clear-results");
  let pollTimer = null;

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function renderSummary(progress) {
    const info = progress || { total: 0, completed: 0, cached: 0, failed: 0 };
    summary.innerHTML = `
      <div class="summary-card"><strong>${info.total || 0}</strong><span>Total</span></div>
      <div class="summary-card"><strong>${info.completed || 0}</strong><span>Completed</span></div>
      <div class="summary-card"><strong>${info.cached || 0}</strong><span>Cached</span></div>
      <div class="summary-card"><strong>${info.failed || 0}</strong><span>Failed</span></div>
    `;
  }

  function bindResultTabs() {
    results.querySelectorAll(".result-tabs").forEach((tabs) => {
      const buttons = tabs.querySelectorAll(".result-tab-button");
      const panels = tabs.querySelectorAll(".result-tab-panel");
      buttons.forEach((button) => {
        button.addEventListener("click", () => {
          const tab = button.dataset.tab;
          buttons.forEach((item) => item.classList.toggle("active", item === button));
          panels.forEach((panel) => {
            panel.classList.toggle("active", panel.dataset.panel === tab);
          });
        });
      });
    });
  }

  function renderResults(task) {
    taskMeta.textContent = `Task ${task.task_id} · ${task.status}`;
    if (task.access_tier) {
      taskMeta.textContent += ` · ${task.access_tier}`;
    }

    renderSummary(task.progress);
    apiJson.textContent = JSON.stringify(task, null, 2);
    const items = task.items || [];

    if (!items.length) {
      results.innerHTML = '<div class="empty">No task items returned.</div>';
      return;
    }

    results.innerHTML = items
      .map((item) => {
        const article = item.article || {};
        const statusClass =
          item.status === "failed" ? "pill-failed" : item.status === "completed" ? "pill-done" : "";
        const previewHtml = article.html ? article.html : "<p>Waiting for article output...</p>";
        const images = Array.isArray(article.images) ? article.images : [];
        const galleryHtml = images.length
          ? `
          <div class="gallery">
            ${images
              .map(
                (image) => `
              <article class="gallery-card">
                <img src="${escapeHtml(image.url)}" alt="${escapeHtml(image.alt)}" />
                <div class="gallery-card-body">
                  <strong>${escapeHtml(image.role)}</strong>
                  <p>${escapeHtml(image.alt)}</p>
                </div>
              </article>
            `,
              )
              .join("")}
          </div>
        `
          : "";

        return `
          <article class="result-card">
            <div class="result-head">
              <div>
                <h3>${escapeHtml(item.keyword)}</h3>
                <div class="result-meta">
                  <span class="pill ${statusClass}">${escapeHtml(item.status)}</span>
                  ${item.cache_hit ? '<span class="pill pill-cache">cache hit</span>' : ""}
                  ${article.generation_mode ? `<span class="pill">${escapeHtml(article.generation_mode)}</span>` : ""}
                  ${
                    article.image_generation_mode
                      ? `<span class="pill">${escapeHtml(article.image_generation_mode)} images</span>`
                      : ""
                  }
                  ${task.access_tier ? `<span class="pill">${escapeHtml(task.access_tier)} access</span>` : ""}
                </div>
              </div>
            </div>
            ${item.error ? `<p class="muted" style="color:#b91c1c">${escapeHtml(item.error)}</p>` : ""}
            ${
              article.title
                ? `
              <div class="article-meta">
                <div><strong>Title:</strong> ${escapeHtml(article.title)}</div>
                <div><strong>Meta Title:</strong> ${escapeHtml(article.meta_title)}</div>
                <div><strong>Meta Description:</strong> ${escapeHtml(article.meta_description)}</div>
              </div>
              <div class="result-tabs">
                <div class="result-tab-buttons">
                  <button class="result-tab-button active" type="button" data-tab="preview">Preview</button>
                  <button class="result-tab-button" type="button" data-tab="html">View HTML</button>
                </div>
                <div class="result-tab-panel active" data-panel="preview">
                  <div class="preview-surface">${previewHtml}</div>
                </div>
                <div class="result-tab-panel" data-panel="html">
                  <pre class="code-block">${escapeHtml(article.html)}</pre>
                </div>
              </div>
              ${galleryHtml}
            `
                : '<div class="muted">Waiting for article output...</div>'
            }
          </article>
        `;
      })
      .join("");

    bindResultTabs();
  }

  async function fetchTask(taskId) {
    const response = await fetch(`/api/tasks/${taskId}`);
    const payload = await response.json();

    if (!payload.success) {
      taskMeta.textContent = payload.message || "Task lookup failed";
      submitBtn.disabled = false;
      submitBtn.innerHTML = "Start Task";
      return;
    }

    const task = payload.data;
    renderResults(task);

    if (!["completed", "failed", "partial_failed"].includes(task.status)) {
      pollTimer = setTimeout(() => fetchTask(taskId), 1500);
    } else {
      submitBtn.disabled = false;
      submitBtn.innerHTML = "Start Task";
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearTimeout(pollTimer);
    submitBtn.disabled = true;
    submitBtn.innerHTML =
      '<span class="spinner" style="width:18px;height:18px;border-width:3px;margin:0"></span> Starting...';
    taskMeta.textContent = "Submitting task...";
    results.innerHTML = `
      <div class="loading-card">
        <div>
          <div class="spinner"></div>
          <strong>Creating task and generating content...</strong>
          <div>The app is analyzing keywords, drafting the article, and preparing images.</div>
        </div>
      </div>
    `;
    apiJson.textContent = JSON.stringify({ status: "submitting" }, null, 2);
    renderSummary();

    const formData = new FormData(form);
    const payload = {
      token: formData.get("token"),
      category: formData.get("category"),
      language: formData.get("language"),
      keywords: formData.get("keywords"),
      info: formData.get("info"),
      force_refresh: formData.get("force_refresh") === "true",
      generate_images: formData.get("generate_images") === "true",
    };

    const response = await fetch("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    if (!data.success) {
      taskMeta.textContent = data.message || "Task creation failed";
      results.innerHTML = '<div class="empty">The request could not be processed.</div>';
      apiJson.textContent = JSON.stringify(data, null, 2);
      submitBtn.disabled = false;
      submitBtn.innerHTML = "Start Task";
      return;
    }

    taskMeta.textContent = `Task ${data.data.task_id} created · ${data.data.access_tier || "authorized"}`;
    apiJson.textContent = JSON.stringify(data, null, 2);
    fetchTask(data.data.task_id);
  });

  clearBtn.addEventListener("click", () => {
    clearTimeout(pollTimer);
    submitBtn.disabled = false;
    submitBtn.innerHTML = "Start Task";
    taskMeta.textContent = "No active task";
    renderSummary();
    results.innerHTML = '<div class="empty">Submit a task to preview generated SEO or GEO article output.</div>';
    apiJson.textContent = "{}";
  });

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
});
