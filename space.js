/**
 * Aura Space & Interactions Core Script
 * Designed in Swiss Punk / Bauhaus Remix Style
 * Strictly no emojis, raw geometry, high-performance canvas
 */

document.addEventListener('DOMContentLoaded', () => {
    initSpaceCanvas();
    initMagneticElements();
    initInteractiveDemo();
    initDocsRouter();
});

/**
 * 1. HIGH-PERFORMANCE SPACE CANVAS BACKGROUND
 * Draws sharp, technical square stars and dynamic connection grids.
 */
function initSpaceCanvas() {
    const canvas = document.getElementById('space-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let animationFrameId;
    let stars = [];
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    // Mouse coordinates tracking for cosmic attraction
    const mouse = { x: null, y: null, radius: 150 };

    window.addEventListener('mousemove', (e) => {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
    });

    window.addEventListener('mouseout', () => {
        mouse.x = null;
        mouse.y = null;
    });

    // Handle resize with debouncing to prevent layout thrashing
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
            createStars();
        }, 100);
    });

    class Star {
        constructor() {
            this.x = Math.random() * width;
            this.y = Math.random() * height;
            this.size = Math.random() * 2 + 1; // 1px to 3px
            this.speedX = (Math.random() - 0.5) * 0.15;
            this.speedY = (Math.random() - 0.5) * 0.15;
            // Color selection: Emerald (#00f5d4) or Gold (#ffd166)
            this.color = Math.random() > 0.4 ? '#00f5d4' : '#ffd166';
            this.opacity = Math.random() * 0.7 + 0.3;
        }

        update() {
            this.x += this.speedX;
            this.y += this.speedY;

            // Bounce on boundaries
            if (this.x < 0 || this.x > width) this.speedX = -this.speedX;
            if (this.y < 0 || this.y > height) this.speedY = -this.speedY;

            // Mouse interaction (repel effect for Bauhaus precision)
            if (mouse.x != null && mouse.y != null) {
                const dx = this.x - mouse.x;
                const dy = this.y - mouse.y;
                const distance = Math.hypot(dx, dy);

                if (distance < mouse.radius) {
                    const force = (mouse.radius - distance) / mouse.radius;
                    const angle = Math.atan2(dy, dx);
                    this.x += Math.cos(angle) * force * 1.5;
                    this.y += Math.sin(angle) * force * 1.5;
                }
            }
        }

        draw() {
            ctx.save();
            ctx.globalAlpha = this.opacity;
            ctx.fillStyle = this.color;
            
            // Bauhaus Theme: Square Stars instead of generic circles
            ctx.fillRect(this.x, this.y, this.size, this.size);
            ctx.restore();
        }
    }

    function createStars() {
        stars = [];
        // Adaptive star density based on viewport size
        const starCount = Math.floor((width * height) / 12000);
        for (let i = 0; i < Math.min(starCount, 120); i++) {
            stars.push(new Star());
        }
    }

    function drawGridLines() {
        // Draw elegant, thin Bauhaus grid lines between nearby stars
        ctx.strokeStyle = 'rgba(0, 245, 212, 0.05)';
        ctx.lineWidth = 0.5;

        for (let i = 0; i < stars.length; i++) {
            for (let j = i + 1; j < stars.length; j++) {
                const dist = Math.hypot(stars[i].x - stars[j].x, stars[i].y - stars[j].y);

                if (dist < 100) {
                    ctx.beginPath();
                    ctx.moveTo(stars[i].x, stars[i].y);
                    ctx.lineTo(stars[j].x, stars[j].y);
                    ctx.stroke();
                }
            }
        }
    }

    let time = 0;
    function drawAurora() {
        time += 0.001; // Slow and organic movement
        ctx.save();
        ctx.globalCompositeOperation = 'screen';
        
        // Wave 1: Cosmic Emerald Glow (#00f5d4)
        const y1 = height * 0.4 + Math.sin(time * 1.5) * 60;
        const g1 = ctx.createLinearGradient(0, y1 - 250, 0, y1 + 350);
        g1.addColorStop(0, 'rgba(0, 245, 212, 0)');
        g1.addColorStop(0.5, 'rgba(0, 245, 212, 0.07)');
        g1.addColorStop(1, 'rgba(0, 245, 212, 0)');
        
        ctx.fillStyle = g1;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        for (let x = 0; x <= width; x += 15) {
            const yOffset = Math.sin(x * 0.0015 + time * 3) * 50 + Math.cos(x * 0.0008 - time * 2) * 25;
            ctx.lineTo(x, y1 + yOffset);
        }
        ctx.lineTo(width, 0);
        ctx.closePath();
        ctx.fill();
        
        // Wave 2: Stellar Gold Glow (#ffd166)
        const y2 = height * 0.5 + Math.cos(time * 1.2) * 50;
        const g2 = ctx.createLinearGradient(0, y2 - 300, 0, y2 + 300);
        g2.addColorStop(0, 'rgba(255, 209, 102, 0)');
        g2.addColorStop(0.5, 'rgba(255, 209, 102, 0.03)');
        g2.addColorStop(1, 'rgba(255, 209, 102, 0)');
        
        ctx.fillStyle = g2;
        ctx.beginPath();
        ctx.moveTo(0, height);
        for (let x = 0; x <= width; x += 15) {
            const yOffset = Math.cos(x * 0.0012 - time * 2.5) * 40 + Math.sin(x * 0.0022 + time * 1.8) * 20;
            ctx.lineTo(x, y2 + yOffset);
        }
        ctx.lineTo(width, height);
        ctx.closePath();
        ctx.fill();
        
        ctx.restore();
    }

    function animate() {
        ctx.fillStyle = '#0b0c10'; // Deep Obsidian Charcoal
        ctx.fillRect(0, 0, width, height);

        drawAurora();
        drawGridLines();

        stars.forEach((star) => {
            star.update();
            star.draw();
        });

        animationFrameId = requestAnimationFrame(animate);
    }

    createStars();
    animate();
}

/**
 * 2. MAGNETIC ELEMENTS
 * Interactive elements gravitate slightly toward the mouse.
 */
function initMagneticElements() {
    const magneticItems = document.querySelectorAll('.magnetic');

    magneticItems.forEach((el) => {
        // Set transition timing smoothly
        el.style.transition = 'transform 0.3s cubic-bezier(0.25, 1, 0.5, 1)';

        el.addEventListener('mousemove', (e) => {
            const rect = el.getBoundingClientRect();
            const elX = rect.left + rect.width / 2;
            const elY = rect.top + rect.height / 2;

            const mouseX = e.clientX;
            const mouseY = e.clientY;

            // Distance calculations
            const dx = mouseX - elX;
            const dy = mouseY - elY;

            // Limit displacement maximum to 15px for sharp UX control
            const strength = 0.35;
            const moveX = dx * strength;
            const moveY = dy * strength;

            el.style.transform = `translate(${moveX}px, ${moveY}px)`;
            el.style.borderColor = '#ffd166'; // Highlight with Stellar Gold on focus
            el.style.boxShadow = '0 0 10px rgba(255, 209, 102, 0.2)';
        });

        el.addEventListener('mouseleave', () => {
            el.style.transform = 'translate(0px, 0px)';
            el.style.borderColor = ''; // Revert to Emerald
            el.style.boxShadow = '';
        });
    });
}

/**
 * 3. INTERACTIVE CLI GENERATOR DEMO
 * Interactive system showing quick commands generated instantly.
 */
function initInteractiveDemo() {
    const buttons = document.querySelectorAll('.cli-builder-btn');
    const termCode = document.getElementById('glowing-terminal-code');
    const termTitle = document.getElementById('glowing-terminal-title');
    const copyBtn = document.getElementById('glowing-terminal-copy');

    if (!termCode || !buttons.length) return;

    // Predefined CLI patterns for interactive wow-factor
    const cliCommands = {
        new: {
            title: 'aura new --scaffold',
            command: 'aura new aura-app --dir ./workspace\ncd aura-app\npip install -e ".[dev]"\naura run --reload',
            desc: '# scaffold a full NestJS-inspired, async-first application structure'
        },
        module: {
            title: 'aura generate module posts',
            command: 'aura generate module posts --with-db --force\n# Output:\n#  ✔ Created modules/posts/models.py\n#  ✔ Created modules/posts/repository.py\n#  ✔ Created modules/posts/service.py\n#  ✔ Created modules/posts/controller.py\n#  ✔ Created modules/posts/module.py\n#  ✔ Created tests/test_posts.py',
            desc: '# generate a complete database-backed REST module with DI & tests'
        },
        migrate: {
            title: 'aura migrate up',
            command: 'aura migrate init\naura migrate make "create_posts_table"\naura migrate up\n# Applies pending migrations safely inside transactional context',
            desc: '# manage async database migrations using a robust SQLAlchemy 2.x wrapper'
        },
        worker: {
            title: 'aura worker --queue default',
            command: 'export AURA__JOBS__BROKER_URL=redis://localhost:6379\naura worker --queue emails --concurrency 4\n# Process tasks asynchronously using a high-performance Redis SAQ backend',
            desc: '# launch the asynchronous background job worker with queue control'
        },
        tinker: {
            title: 'aura tinker',
            command: 'aura tinker\n# Entering Aura Asynchronous Tinker REPL (IPython)\n# Available globals: app, db, modules\n# Run queries directly using standard async/await syntax',
            desc: '# inspect, debug, and query database models in an interactive shell'
        }
    };

    buttons.forEach((btn) => {
        btn.addEventListener('click', () => {
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const type = btn.getAttribute('data-cli-type');
            if (cliCommands[type]) {
                const item = cliCommands[type];
                termTitle.textContent = item.title;
                termCode.innerHTML = `<span class="term-comment">${item.desc}</span>\n<span class="term-prompt">$</span> ${item.command}`;
            }
        });
    });

    // Copy to clipboard utility
    copyBtn.addEventListener('click', () => {
        const textToCopy = termCode.innerText.replace(/^\$\s/gm, ''); // remove the CLI prompt symbol
        navigator.clipboard.writeText(textToCopy).then(() => {
            const originalText = copyBtn.textContent;
            copyBtn.textContent = 'COPIED';
            copyBtn.style.color = '#00f5d4';
            copyBtn.style.borderColor = '#00f5d4';
            setTimeout(() => {
                copyBtn.textContent = originalText;
                copyBtn.style.color = '';
                copyBtn.style.borderColor = '';
            }, 1500);
        });
    });
}

/**
 * 4. DOCUMENTATION ROUTER & EXPLORER
 * Handles tab transitions, sidebar activations, and dynamic code block swaps.
 */
function initDocsRouter() {
    const sidebar = document.querySelector('.docs-sidebar');
    const contentContainer = document.querySelector('.docs-content-container');
    const searchInput = document.getElementById('docs-search-input');

    if (!sidebar || !contentContainer) return;

    // 1. DYNAMIC RENDER OF DOCUMENTATION FROM WINDOW.DOCSDATA
    if (window.docsData && window.docsData.sections) {
        // Categories to map sections
        const categories = [
            {
                title: "GETTING STARTED",
                sections: ["introduction-motivation"]
            },
            {
                title: "CORE ARCHITECTURE",
                sections: ["dependency-injection", "templates-routing"]
            },
            {
                title: "DATA LAYER",
                sections: ["orm-querybuilder", "admin-dashboard"]
            },
            {
                title: "DISTRIBUTED SERVICES",
                sections: ["background-jobs"]
            }
        ];

        // Clean existing static menu groups (keep search input)
        const staticGroups = sidebar.querySelectorAll('.docs-menu-group');
        staticGroups.forEach(g => g.remove());

        // Clean existing content panels
        contentContainer.innerHTML = '';

        // Build Sidebar and Content dynamically
        categories.forEach((cat) => {
            const groupDiv = document.createElement('div');
            groupDiv.className = 'docs-menu-group';

            const groupTitle = document.createElement('div');
            groupTitle.className = 'docs-menu-title';
            groupTitle.textContent = cat.title;
            groupDiv.appendChild(groupTitle);

            const linksDiv = document.createElement('div');
            linksDiv.className = 'docs-sidebar-links';

            cat.sections.forEach((sectionId) => {
                const section = window.docsData.sections.find(s => s.id === sectionId);
                if (section) {
                    // Create link
                    const link = document.createElement('a');
                    link.href = '#';
                    link.className = 'docs-sidebar-link';
                    link.setAttribute('data-target', `doc-${section.id}`);
                    link.textContent = section.title.replace(/^\d+\.\s/, ''); // Clean leading numbering for aesthetic UI
                    linksDiv.appendChild(link);

                    // Create panel
                    const panel = document.createElement('div');
                    panel.className = 'docs-panel';
                    panel.id = `doc-${section.id}`;
                    panel.innerHTML = parseMarkdown(section.markdown);
                    contentContainer.appendChild(panel);
                }
            });

            groupDiv.appendChild(linksDiv);
            sidebar.appendChild(groupDiv);
        });

        // Set default active states
        const firstLink = sidebar.querySelector('.docs-sidebar-link');
        const firstPanel = contentContainer.querySelector('.docs-panel');
        if (firstLink) firstLink.classList.add('active');
        if (firstPanel) firstPanel.classList.add('active');
    }

    // Grab freshly created links and panels
    const sidebarLinks = document.querySelectorAll('.docs-sidebar-link');
    const docsPanels = document.querySelectorAll('.docs-panel');

    function switchSection(targetId) {
        docsPanels.forEach(panel => panel.classList.remove('active'));
        sidebarLinks.forEach(link => link.classList.remove('active'));

        const activePanel = document.getElementById(targetId);
        const activeLink = document.querySelector(`.docs-sidebar-link[data-target="${targetId}"]`);

        if (activePanel) {
            activePanel.classList.add('active');
            contentContainer.scrollTop = 0;
        }
        
        if (activeLink) {
            activeLink.classList.add('active');
        }
    }

    sidebarLinks.forEach((link) => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('data-target');
            switchSection(targetId);
        });
    });

    // Code blocks copy action
    setupCopyButtons();

    // Fuzzy search filter
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            
            sidebarLinks.forEach((link) => {
                const text = link.textContent.toLowerCase();
                const targetId = link.getAttribute('data-target');
                const panel = document.getElementById(targetId);
                const panelText = panel ? panel.textContent.toLowerCase() : '';
                
                if (text.includes(query) || panelText.includes(query)) {
                    link.style.display = 'block';
                } else {
                    link.style.display = 'none';
                }
            });

            // Show/Hide menu groups and manage state
            const groups = document.querySelectorAll('.docs-menu-group');
            groups.forEach((group) => {
                const visibleLinks = Array.from(group.querySelectorAll('.docs-sidebar-link')).filter(l => l.style.display !== 'none');
                if (visibleLinks.length === 0 && query !== '') {
                    group.style.display = 'none';
                } else {
                    group.style.display = 'block';
                }
            });
        });
    }

    // Connect landing-page CTA to document selector
    const exploreCTA = document.getElementById('cta-explore-docs');
    if (exploreCTA) {
        exploreCTA.addEventListener('click', (e) => {
            e.preventDefault();
            const docsSection = document.getElementById('aura-docs-section');
            if (docsSection) {
                docsSection.scrollIntoView({ behavior: 'smooth' });
                const firstSection = window.docsData?.sections[0]?.id || 'quickstart';
                switchSection(`doc-${firstSection}`);
            }
        });
    }
}

/**
 * 5. MARKDOWN PARSER UTILS
 * Highly optimized vanilla parser converting Markdown streams into premium styled HTML.
 */
function parseMarkdown(md) {
    if (!md) return '';
    
    const lines = md.split('\n');
    let html = [];
    let inList = false;
    let inTable = false;
    let tableRows = [];
    let inCode = false;
    let codeContent = [];
    let codeLang = '';
    let inBlockquote = false;
    let blockquoteContent = [];

    for (let i = 0; i < lines.length; i++) {
        let line = lines[i];

        // Code blocks
        if (line.trim().startsWith('```')) {
            if (inCode) {
                const escapedCode = codeContent.join('\n')
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');
                html.push(`<div class="docs-code-block">
                    <button class="copy-code-btn">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" style="stroke: currentColor; stroke-width: 2; display: inline-block; vertical-align: middle; margin-right: 4px;">
                            <rect x="9" y="9" width="13" height="13" />
                            <path d="M5 15H4V4H15V5" />
                        </svg>COPY
                    </button>
                    <pre><code class="language-${codeLang}">${escapedCode}</code></pre>
                </div>`);
                inCode = false;
                codeContent = [];
                codeLang = '';
            } else {
                inCode = true;
                codeLang = line.trim().substring(3).trim();
            }
            continue;
        }

        if (inCode) {
            codeContent.push(line);
            continue;
        }

        // Close list block
        if (inList && !line.trim().startsWith('- ') && !line.trim().startsWith('* ') && !/^\d+\.\s/.test(line.trim())) {
            html.push('</ul>');
            inList = false;
        }

        // Close table block
        if (inTable && !line.trim().startsWith('|')) {
            html.push(renderTable(tableRows));
            inTable = false;
            tableRows = [];
        }

        // Close blockquotes/alerts
        if (inBlockquote && !line.trim().startsWith('>')) {
            html.push(renderBlockquote(blockquoteContent));
            inBlockquote = false;
            blockquoteContent = [];
        }

        // Headers
        if (line.startsWith('# ')) {
            html.push(`<h2>${parseInline(line.substring(2))}</h2>`);
        } else if (line.startsWith('## ')) {
            html.push(`<h3>${parseInline(line.substring(3))}</h3>`);
        } else if (line.startsWith('### ')) {
            html.push(`<h4>${parseInline(line.substring(4))}</h4>`);
        } else if (line.trim() === '---') {
            html.push('<hr>');
        }
        // Blockquotes
        else if (line.trim().startsWith('>')) {
            inBlockquote = true;
            blockquoteContent.push(line.trim().substring(1).trim());
        }
        // Tables
        else if (line.trim().startsWith('|')) {
            inTable = true;
            tableRows.push(line.trim());
        }
        // Lists
        else if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
            if (!inList) {
                html.push('<ul class="docs-list">');
                inList = true;
            }
            html.push(`<li>${parseInline(line.trim().substring(2))}</li>`);
        }
        // Paragraphs
        else if (line.trim().length > 0) {
            html.push(`<p>${parseInline(line)}</p>`);
        }
    }

    if (inList) html.push('</ul>');
    if (inTable) html.push(renderTable(tableRows));
    if (inBlockquote) html.push(renderBlockquote(blockquoteContent));

    return html.join('\n');
}

function parseInline(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="accent-emerald">$1</a>');
}

function renderTable(rows) {
    if (rows.length === 0) return '';
    let tableHtml = ['<table class="matrix-table sharp-border">'];
    
    const headers = rows[0].split('|').map(c => c.trim()).filter(c => c.length > 0);
    tableHtml.push('<thead><tr>' + headers.map(h => `<th>${parseInline(h)}</th>`).join('') + '</tr></thead>');
    
    tableHtml.push('<tbody>');
    for (let i = 2; i < rows.length; i++) {
        const cells = rows[i].split('|').map(c => c.trim()).filter(c => c.length > 0);
        if (cells.length > 0) {
            tableHtml.push('<tr>' + cells.map(c => `<td>${parseInline(c)}</td>`).join('') + '</tr>');
        }
    }
    tableHtml.push('</tbody></table>');
    return tableHtml.join('\n');
}

function renderBlockquote(lines) {
    const fullText = lines.join(' ');
    if (fullText.startsWith('[!NOTE]')) {
        return `<div class="docs-alert">
            <div class="docs-alert-title">NOTE</div>
            <div class="docs-alert-content">${parseInline(fullText.substring(7).trim())}</div>
        </div>`;
    } else if (fullText.startsWith('[!WARNING]')) {
        return `<div class="docs-alert docs-alert-warning">
            <div class="docs-alert-title">WARNING</div>
            <div class="docs-alert-content">${parseInline(fullText.substring(10).trim())}</div>
        </div>`;
    } else if (fullText.startsWith('[!IMPORTANT]')) {
        return `<div class="docs-alert docs-alert-important">
            <div class="docs-alert-title">IMPORTANT</div>
            <div class="docs-alert-content">${parseInline(fullText.substring(12).trim())}</div>
        </div>`;
    }
    return `<div class="docs-alert"><div class="docs-alert-content">${parseInline(fullText)}</div></div>`;
}

function setupCopyButtons() {
    const copyBtns = document.querySelectorAll('.copy-code-btn');
    copyBtns.forEach((btn) => {
        btn.addEventListener('click', () => {
            const pre = btn.nextElementSibling;
            const code = pre ? pre.querySelector('code') : null;
            if (!code) return;

            navigator.clipboard.writeText(code.innerText).then(() => {
                const originalHTML = btn.innerHTML;
                btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" style="stroke: #00f5d4; stroke-width: 2; display: inline-block; vertical-align: middle; margin-right: 4px;">
                    <polyline points="20 6 9 17 4 12" />
                </svg><span style="color: #00f5d4">COPIED</span>`;
                btn.style.borderColor = '#00f5d4';
                setTimeout(() => {
                    btn.innerHTML = originalHTML;
                    btn.style.borderColor = '';
                }, 1500);
            });
        });
    });

    // Installation bar copy button logic
    const installBtn = document.getElementById('install-copy-btn');
    if (installBtn) {
        installBtn.addEventListener('click', () => {
            const installText = document.querySelector('.install-text');
            if (!installText) return;

            navigator.clipboard.writeText(installText.value).then(() => {
                const originalHTML = installBtn.innerHTML;
                installBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" style="stroke: #00f5d4; stroke-width: 2; display: inline-block; vertical-align: middle; margin-right: 4px;">
                    <polyline points="20 6 9 17 4 12" />
                </svg><span style="color: #00f5d4">COPIED</span>`;
                installBtn.style.borderColor = '#00f5d4';
                setTimeout(() => {
                    installBtn.innerHTML = originalHTML;
                    installBtn.style.borderColor = '';
                }, 1500);
            });
        });
    }
}
