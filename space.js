/* Aura Space & Interactions Core Script */
document.addEventListener("DOMContentLoaded", function () {
  initSpaceCanvas();
  initMagneticElements();
  initInteractiveDemo();
  initDocsSystem();
  initMobileNav();
  initCopyButtons();
  initVersionSync();
  fetchGitHubStars();
});

/* 1. AURORA CANVAS BACKGROUND */
function initSpaceCanvas() {
  const canvas = document.getElementById("space-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let animId, stars = [];
  let w = canvas.width = window.innerWidth;
  let h = canvas.height = window.innerHeight;
  const mouse = { x: null, y: null, radius: 150 };

  window.addEventListener("mousemove", function (e) { mouse.x = e.clientX; mouse.y = e.clientY; });
  window.addEventListener("mouseout", function () { mouse.x = null; mouse.y = null; });

  let resizeTimer;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
      createStars();
    }, 100);
  });

  function Star() {
    this.x = Math.random() * w; this.y = Math.random() * h;
    this.size = Math.random() * 2 + 1;
    this.speedX = (Math.random() - 0.5) * 0.15;
    this.speedY = (Math.random() - 0.5) * 0.15;
    this.color = Math.random() > 0.4 ? "#00f5d4" : "#ffd166";
    this.opacity = Math.random() * 0.7 + 0.3;
  }
  Star.prototype.update = function () {
    this.x += this.speedX; this.y += this.speedY;
    if (this.x < 0 || this.x > w) this.speedX = -this.speedX;
    if (this.y < 0 || this.y > h) this.speedY = -this.speedY;
    if (mouse.x != null && mouse.y != null) {
      const dx = this.x - mouse.x, dy = this.y - mouse.y, dist = Math.hypot(dx, dy);
      if (dist < mouse.radius) {
        const force = (mouse.radius - dist) / mouse.radius, angle = Math.atan2(dy, dx);
        this.x += Math.cos(angle) * force * 1.5;
        this.y += Math.sin(angle) * force * 1.5;
      }
    }
  };
  Star.prototype.draw = function () {
    ctx.save(); ctx.globalAlpha = this.opacity; ctx.fillStyle = this.color;
    ctx.fillRect(this.x, this.y, this.size, this.size); ctx.restore();
  };

  function createStars() {
    stars = [];
    const count = Math.min(Math.floor((w * h) / 12000), 120);
    for (let i = 0; i < count; i++) stars.push(new Star());
  }

  function drawGrid() {
    ctx.strokeStyle = "rgba(0,245,212,0.04)"; ctx.lineWidth = 0.5;
    for (let i = 0; i < stars.length; i++) {
      for (let j = i + 1; j < stars.length; j++) {
        if (Math.hypot(stars[i].x - stars[j].x, stars[i].y - stars[j].y) < 100) {
          ctx.beginPath(); ctx.moveTo(stars[i].x, stars[i].y); ctx.lineTo(stars[j].x, stars[j].y); ctx.stroke();
        }
      }
    }
  }

  let time = 0;
  const cE = "rgba(0,245,212,", cG = "rgba(255,209,102,";

  function drawRibbon(cy, amp, spd, freq, c1, c2, mult) {
    const rw = 160 + Math.sin(time * 0.7) * 40;
    const grad = ctx.createLinearGradient(0, cy - rw, 0, cy + rw);
    grad.addColorStop(0, "rgba(0,245,212,0)");
    grad.addColorStop(0.3, c1 + (0.05 * mult) + ")");
    grad.addColorStop(0.5, c2 + (0.10 * mult) + ")");
    grad.addColorStop(0.7, c1 + (0.06 * mult) + ")");
    grad.addColorStop(1, "rgba(0,245,212,0)");
    ctx.beginPath();
    for (let x = 0; x <= w; x += 20) {
      const y = cy + Math.sin(x * freq + time * spd) * amp + Math.cos(x * (freq * 2.1) - time * (spd * 0.85)) * (amp * 0.35) + Math.sin(x * (freq * 0.55) + time * (spd * 0.4)) * (amp * 0.5);
      x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = grad; ctx.lineWidth = rw; ctx.lineCap = "round"; ctx.stroke();
  }

  function drawCurtain(cy, amp, spd, freq, colorStr, mult) {
    const cw = 220 + Math.sin(time * 0.5) * 50; ctx.lineWidth = 3;
    for (let x = 0; x <= w; x += 12) {
      const y = cy + Math.sin(x * freq + time * spd) * amp + Math.cos(x * (freq * 2.3) - time * (spd * 0.75)) * (amp * 0.3);
      const ph = cw * (0.8 + Math.sin(x * 0.007 + time * 3.5) * 0.25);
      const alpha = (0.03 + Math.sin(x * 0.005 - time * 2.2) * 0.02) * mult;
      if (alpha <= 0) continue;
      const grad = ctx.createLinearGradient(0, y - ph / 2, 0, y + ph / 2);
      grad.addColorStop(0, "rgba(0,245,212,0)");
      grad.addColorStop(0.5, colorStr + alpha + ")");
      grad.addColorStop(1, "rgba(0,245,212,0)");
      ctx.strokeStyle = grad; ctx.beginPath(); ctx.moveTo(x, y - ph / 2); ctx.lineTo(x, y + ph / 2); ctx.stroke();
    }
  }

  function drawAurora() {
    time += 0.0006; ctx.save(); ctx.globalCompositeOperation = "screen";
    drawRibbon(h * 0.35, 75, 1.1, 0.0008, cE, cE, 1.2);
    drawCurtain(h * 0.42, 90, 1.3, 0.0011, cE, 1.3);
    drawRibbon(h * 0.48, 105, -0.85, 0.0007, cG, cE, 0.85);
    drawRibbon(h * 0.58, 85, 0.6, 0.0005, cE, cG, 1.0);
    ctx.restore();
  }

  function animate() {
    ctx.fillStyle = "#0b0c10"; ctx.fillRect(0, 0, w, h);
    drawAurora(); drawGrid();
    stars.forEach(function (s) { s.update(); s.draw(); });
    animId = requestAnimationFrame(animate);
  }

  createStars(); animate();
}

/* 2. MAGNETIC ELEMENTS */
function initMagneticElements() {
  document.querySelectorAll(".magnetic").forEach(function (el) {
    el.addEventListener("mousemove", function (e) {
      const rect = el.getBoundingClientRect();
      const dx = e.clientX - (rect.left + rect.width / 2);
      const dy = e.clientY - (rect.top + rect.height / 2);
      el.style.transform = "translate(" + (dx * 0.35) + "px," + (dy * 0.35) + "px)";
    });
    el.addEventListener("mouseleave", function () { el.style.transform = ""; });
  });
}

/* 3. INTERACTIVE CLI DEMO */
function initInteractiveDemo() {
  const buttons = document.querySelectorAll(".cli-builder-btn");
  const termCode = document.getElementById("glowing-terminal-code");
  const termTitle = document.getElementById("glowing-terminal-title");
  const copyBtn = document.getElementById("glowing-terminal-copy");
  if (!termCode || !buttons.length) return;

  var cliCommands = {
    new: { title: "aura new --scaffold", command: "aura new aura-app --dir ./workspace\ncd aura-app\npip install -e \".[dev]\"\naura run --reload", desc: "# scaffold a NestJS-inspired, async-first application" },
    module: { title: "aura generate module posts", command: "aura generate module posts --with-db --force\n# Output:\n#  Created modules/posts/{models,repository,service,controller,module}.py\n#  Created tests/test_posts.py", desc: "# generate a complete REST module with DI & tests" },
    migrate: { title: "aura migrate up", command: "aura migrate init\naura migrate make \"create_posts_table\"\naura migrate up", desc: "# manage async database migrations" },
    worker: { title: "aura worker --queue default", command: "export AURA__JOBS__BROKER_URL=redis://localhost:6379\naura worker --queue emails --concurrency 4", desc: "# launch async background job worker" },
    tinker: { title: "aura tinker", command: "aura tinker\n# Entering Aura Asynchronous Tinker REPL\n# Available: app, db, modules", desc: "# inspect, debug, and query models interactively" }
  };

  buttons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      buttons.forEach(function (b) { b.classList.remove("active"); b.setAttribute("aria-selected", "false"); });
      btn.classList.add("active"); btn.setAttribute("aria-selected", "true");
      var item = cliCommands[btn.getAttribute("data-cli-type")];
      if (item) { termTitle.textContent = item.title; termCode.innerHTML = "<span class=\"term-comment\">" + item.desc + "</span>\n<span class=\"term-prompt\">$</span> " + item.command; }
    });
  });

  if (copyBtn) {
    copyBtn.addEventListener("click", function () {
      var text = termCode.innerText.replace(/^\$\s/gm, "");
      navigator.clipboard.writeText(text).then(function () {
        var orig = copyBtn.textContent; copyBtn.textContent = "COPIED"; copyBtn.style.color = "#00f5d4"; copyBtn.style.borderColor = "#00f5d4";
        setTimeout(function () { copyBtn.textContent = orig; copyBtn.style.color = ""; copyBtn.style.borderColor = ""; }, 1500);
      });
    });
  }
}

/* 4. DOCS SYSTEM (LAZY LOAD, SIDEBAR, SEARCH, HIGHLIGHT) */
function initDocsSystem() {
  const sidebarLinks = document.querySelectorAll(".docs-sidebar-link");
  const docsPanels = document.querySelectorAll(".docs-panel");
  const searchInput = document.getElementById("docs-search-input");
  const contentPanels = document.getElementById("docs-panels");
  const docsSection = document.getElementById("aura-docs-section");
  const breadcrumbCurrent = document.getElementById("breadcrumb-current");
  const docsEditLink = document.getElementById("docs-edit-link");
  var docsLoaded = false;

  // Category collapsible toggles
  document.querySelectorAll(".docs-category-toggle").forEach(function (btn) {
    var links = btn.nextElementSibling;
    if (links) {
      links.style.maxHeight = links.scrollHeight + "px";
      btn.addEventListener("click", function () {
        var expanded = btn.getAttribute("aria-expanded") === "true";
        btn.setAttribute("aria-expanded", !expanded);
        if (expanded) { links.style.maxHeight = "0px"; } else { links.style.maxHeight = links.scrollHeight + "px"; }
      });
    }
  });

  // Sidebar link switching
  function switchSection(targetId) {
    docsPanels.forEach(function (p) { p.classList.remove("active"); });
    sidebarLinks.forEach(function (l) { l.classList.remove("active"); });
    var panel = document.getElementById(targetId);
    if (panel) { panel.classList.add("active"); document.getElementById("docs-content").scrollTop = 0; }
    var link = document.querySelector('.docs-sidebar-link[data-target="' + targetId + '"]');
    if (link) { link.classList.add("active"); }
    // Update breadcrumb
    if (link && breadcrumbCurrent) { breadcrumbCurrent.textContent = link.textContent; }
  }

  sidebarLinks.forEach(function (link) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      switchSection(link.getAttribute("data-target"));
    });
  });

  // Lazy load docs-data.js
  if (docsSection && !docsLoaded) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && !docsLoaded) {
          docsLoaded = true;
          loadDocsData();
          observer.disconnect();
        }
      });
    }, { rootMargin: "300px" });
    observer.observe(docsSection);
  }

  function loadDocsData() {
    var script = document.createElement("script");
    script.src = "docs-data.js";
    script.onload = function () {
      if (window.docsData && window.docsData.sections) {
        injectDocsData(window.docsData);
      }
      applyHighlighting();
    };
    script.onerror = function () {
      // fallback: static HTML panels remain visible
      applyHighlighting();
    };
    document.body.appendChild(script);
  }

  function injectDocsData(data) {
    var sidebarNav = document.querySelector(".docs-nav");
    var panelsContainer = document.getElementById("docs-panels");
    if (!sidebarNav || !panelsContainer) return;

    var categoryMap = {
      "getting-started": { title: "Getting Started", sections: ["introduction-motivation"] },
      "architecture": { title: "Core Architecture", sections: ["dependency-injection", "templates-routing"] },
      "database": { title: "Data Layer", sections: ["orm-querybuilder", "admin-dashboard"] },
      "backstage": { title: "Distributed Services", sections: ["background-jobs"] }
    };

    Object.keys(categoryMap).forEach(function (catKey) {
      var catConfig = categoryMap[catKey];
      var existingCat = sidebarNav.querySelector('.docs-category[data-category="' + catKey + '-ext"]');
      if (existingCat) return;

      var catDiv = document.createElement("div");
      catDiv.className = "docs-category";
      catDiv.setAttribute("data-category", catKey + "-ext");

      var toggle = document.createElement("button");
      toggle.className = "docs-category-toggle";
      toggle.setAttribute("aria-expanded", "true");
      toggle.innerHTML = '<svg class="category-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true"><polyline points="9 18 15 12 9 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg> ' + catConfig.title;
      catDiv.appendChild(toggle);

      var linksDiv = document.createElement("div");
      linksDiv.className = "docs-category-links";

      catConfig.sections.forEach(function (secId) {
        var section = data.sections.find(function (s) { return s.id === secId; });
        if (!section) return;

        var link = document.createElement("a");
        link.href = "#";
        link.className = "docs-sidebar-link";
        link.setAttribute("data-target", "doc-ext-" + section.id);
        link.textContent = section.title.replace(/^\d+\.\s*/, "");
        linksDiv.appendChild(link);

        // Create panel from markdown
        var panel = document.createElement("div");
        panel.className = "docs-panel";
        panel.id = "doc-ext-" + section.id;
        panel.innerHTML = parseMarkdown(section.markdown);
        if (section.editUrl) {
          panel.setAttribute("data-edit-url", section.editUrl);
        }
        panelsContainer.appendChild(panel);

        // Add click handler
        link.addEventListener("click", function (e) {
          e.preventDefault();
          switchSection(link.getAttribute("data-target"));
        });
      });

      catDiv.appendChild(linksDiv);
      sidebarNav.appendChild(catDiv);

      // Set max-height for animation
      var links = toggle.nextElementSibling;
      if (links) { links.style.maxHeight = links.scrollHeight + "px"; }
      toggle.addEventListener("click", function () {
        var expanded = toggle.getAttribute("aria-expanded") === "true";
        toggle.setAttribute("aria-expanded", !expanded);
        if (expanded) { links.style.maxHeight = "0px"; } else { links.style.maxHeight = links.scrollHeight + "px"; }
      });
    });

    applyHighlighting();
  }

  // Search
  if (searchInput) {
    searchInput.addEventListener("input", function (e) {
      var q = e.target.value.toLowerCase().trim();
      document.querySelectorAll(".docs-sidebar-link").forEach(function (link) {
        var text = link.textContent.toLowerCase();
        var targetId = link.getAttribute("data-target");
        var panel = document.getElementById(targetId);
        var panelText = panel ? panel.textContent.toLowerCase() : "";
        link.classList.toggle("hidden", q && !text.includes(q) && !panelText.includes(q));
      });
      document.querySelectorAll(".docs-category").forEach(function (cat) {
        var visible = Array.from(cat.querySelectorAll(".docs-sidebar-link:not(.hidden)"));
        cat.style.display = (visible.length > 0 || q === "") ? "" : "none";
      });
    });
  }

  // "Edit on GitHub" update
  sidebarLinks.forEach(function (link) {
    link.addEventListener("click", function () {
      var targetId = link.getAttribute("data-target");
      var panel = document.getElementById(targetId);
      if (panel && docsEditLink) {
        var editUrl = panel.getAttribute("data-edit-url");
        docsEditLink.href = editUrl || "https://github.com/Rip4568/Aura";
      }
    });
  });
}

/* 5. HIGHLIGHTING */
function applyHighlighting() {
  if (typeof hljs !== "undefined") {
    document.querySelectorAll(".docs-code-block pre code, .docs-panel pre code").forEach(function (block) {
      hljs.highlightElement(block);
    });
  }
}

/* 6. MOBILE NAV */
function initMobileNav() {
  var hamburger = document.getElementById("hamburger-btn");
  var overlay = document.getElementById("mobile-nav-overlay");
  if (!hamburger || !overlay) return;

  hamburger.addEventListener("click", function () {
    var open = hamburger.getAttribute("aria-expanded") === "true";
    hamburger.setAttribute("aria-expanded", !open);
    overlay.setAttribute("aria-hidden", open);
    overlay.classList.toggle("open");
    document.body.style.overflow = open ? "" : "hidden";
  });

  overlay.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () {
      hamburger.setAttribute("aria-expanded", "false");
      overlay.setAttribute("aria-hidden", "true");
      overlay.classList.remove("open");
      document.body.style.overflow = "";
    });
  });

  // Docs sidebar toggle (mobile)
  var sidebarToggle = document.getElementById("docs-sidebar-toggle");
  var sidebar = document.getElementById("docs-sidebar");
  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener("click", function () {
      var open = sidebarToggle.getAttribute("aria-expanded") === "true";
      sidebarToggle.setAttribute("aria-expanded", !open);
      sidebar.classList.toggle("open");
    });
    // Close sidebar when clicking a link on mobile
    sidebar.querySelectorAll(".docs-sidebar-link").forEach(function (link) {
      link.addEventListener("click", function () {
        if (window.innerWidth <= 900) {
          sidebar.classList.remove("open");
          sidebarToggle.setAttribute("aria-expanded", "false");
        }
      });
    });
  }
}

/* 7. COPY BUTTONS (ALL) */
function initCopyButtons() {
  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".copy-code-btn, .install-copy-btn");
    if (!btn) return;

    var codeEl;
    if (btn.classList.contains("install-copy-btn")) {
      var input = document.querySelector(".install-text");
      codeEl = input ? { innerText: input.value } : null;
    } else {
      var pre = btn.nextElementSibling;
      codeEl = pre ? pre.querySelector("code") || pre : null;
    }
    if (!codeEl) return;

    navigator.clipboard.writeText(codeEl.innerText).then(function () {
      var orig = btn.innerHTML;
      btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true"><polyline points="20 6 9 17 4 12" stroke="#00f5d4" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg><span style="color:#00f5d4">Copied</span>';
      btn.style.borderColor = "#00f5d4";
      setTimeout(function () { btn.innerHTML = orig; btn.style.borderColor = ""; }, 1500);
    });
  });
}

/* 8. VERSION SYNC */
function initVersionSync() {
  var ver = window.AURA_VERSION || "0.4.9";
  document.querySelectorAll("[data-aura-version]").forEach(function (el) { el.textContent = ver; });
}

/* 9. GITHUB STARS */
function fetchGitHubStars() {
  var starEls = [document.getElementById("github-star-count"), document.getElementById("github-stars-display")];
  fetch("https://api.github.com/repos/Rip4568/Aura", { signal: AbortSignal.timeout(5000) })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.stargazers_count !== undefined) {
        var stars = data.stargazers_count;
        var label = "★ " + (stars >= 1000 ? (stars / 1000).toFixed(1) + "k" : stars);
        starEls.forEach(function (el) { if (el) el.textContent = label; });
      }
    })
    .catch(function () {
      starEls.forEach(function (el) { if (el && el.id === "github-star-count") el.textContent = ""; });
    });
}

/* 10. MARKDOWN PARSER (for docs-data.js content) */
function parseMarkdown(md) {
  if (!md) return "";
  var lines = md.split("\n"), html = [], inCode = false, codeContent = [], codeLang = "";
  var inList = false, inTable = false, tableRows = [], inBlockquote = false, bqLines = [];

  function escape(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function inline(s) { return escape(s).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="accent-emerald">$1</a>'); }
  function renderTable(rows) {
    if (!rows.length) return "";
    var h = rows[0].split("|").map(function (c) { return c.trim(); }).filter(Boolean);
    var out = '<div class="docs-table-wrapper"><table class="matrix-table"><thead><tr>' + h.map(function (c) { return "<th>" + inline(c) + "</th>"; }).join("") + "</tr></thead><tbody>";
    for (var i = 2; i < rows.length; i++) {
      var cells = rows[i].split("|").map(function (c) { return c.trim(); }).filter(Boolean);
      if (cells.length) out += "<tr>" + cells.map(function (c) { return "<td>" + inline(c) + "</td>"; }).join("") + "</tr>";
    }
    return out + "</tbody></table></div>";
  }
  function renderBq(lines) {
    var t = lines.join(" ");
    var cls = "docs-alert", title = "Note";
    if (t.startsWith("[!WARNING]")) { cls += " docs-alert-warning"; title = "Warning"; t = t.substring(10).trim(); }
    else if (t.startsWith("[!IMPORTANT]")) { cls += " docs-alert-important"; title = "Important"; t = t.substring(12).trim(); }
    else if (t.startsWith("[!NOTE]")) { t = t.substring(7).trim(); }
    return '<div class="' + cls + '"><div class="docs-alert-title">' + title + "</div><div class=\"docs-alert-content\">" + inline(t) + "</div></div>";
  }

  lines.forEach(function (line) {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        var escaped = escape(codeContent.join("\n"));
        html.push('<div class="docs-code-block"><button class="copy-code-btn" aria-label="Copy code"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="9" y="9" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none"/><path d="M5 15H4V4H15V5" stroke="currentColor" stroke-width="2" fill="none"/></svg> Copy</button><pre><code class="language-' + codeLang + '">' + escaped + "</code></pre></div>");
        inCode = false; codeContent = []; codeLang = "";
      } else { inCode = true; codeLang = line.trim().substring(3).trim(); }
      return;
    }
    if (inCode) { codeContent.push(line); return; }
    if (inList && !line.trim().match(/^[-*]\s/) && !line.trim().match(/^\d+\.\s/)) { html.push("</ul>"); inList = false; }
    if (inTable && !line.trim().startsWith("|")) { html.push(renderTable(tableRows)); inTable = false; tableRows = []; }
    if (inBlockquote && !line.trim().startsWith(">")) { html.push(renderBq(bqLines)); inBlockquote = false; bqLines = []; }

    if (line.startsWith("# ")) { html.push("<h2>" + inline(line.substring(2)) + "</h2>"); }
    else if (line.startsWith("## ")) { html.push("<h3>" + inline(line.substring(3)) + "</h3>"); }
    else if (line.startsWith("### ")) { html.push("<h4>" + inline(line.substring(4)) + "</h4>"); }
    else if (line.trim() === "---") { html.push("<hr>"); }
    else if (line.trim().startsWith(">")) { inBlockquote = true; bqLines.push(line.trim().substring(1).trim()); }
    else if (line.trim().startsWith("|")) { inTable = true; tableRows.push(line.trim()); }
    else if (line.trim().match(/^[-*]\s/)) { if (!inList) { html.push('<ul class="docs-list">'); inList = true; } html.push("<li>" + inline(line.trim().substring(2)) + "</li>"); }
    else if (line.trim().length > 0) { html.push("<p>" + inline(line) + "</p>"); }
  });

  if (inCode) html.push("<pre><code>" + escape(codeContent.join("\n")) + "</code></pre>");
  if (inList) html.push("</ul>");
  if (inTable) html.push(renderTable(tableRows));
  if (inBlockquote) html.push(renderBq(bqLines));

  return html.join("\n");
}
