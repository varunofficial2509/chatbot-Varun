"""Shared, presentation-only building blocks used across every page.

Raw HTML/CSS goes through ``st.html()``, not ``st.markdown(...,
unsafe_allow_html=True)``: the markdown renderer strips <style> tags and
forces target="_blank" on every anchor (including same-origin nav links),
while st.html() inserts the markup as-is (DOMPurify-sanitized, but without
either of those side effects).
"""

import base64
import mimetypes
import re

import streamlit as st

from app import config as settings

NAV_ITEMS = [
    ("home", "#top"),
    ("skills", "#skills"),
    ("experience", "#experience"),
    ("projects", "#projects"),
]

@st.cache_data(show_spinner=False)
def _avatar_data_uri() -> str | None:
    assets_dir = settings.BASE_DIR / "assets"
    if not assets_dir.exists():
        return None
    for ext in ("png", "jpg", "jpeg", "webp"):
        candidates = sorted(assets_dir.glob(f"avatar.{ext}"))
        if candidates:
            path = candidates[0]
            mime = mimetypes.guess_type(path.name)[0] or "image/png"
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{encoded}"
    return None


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def render_nav_header(name: str = "") -> None:
    handle = " ".join(name.split()[:2]).lower() if name else ""
    links_html = "".join(f'<a href="{href}">/{label}</a>' for label, href in NAV_ITEMS)
    st.html(
        f"""
        <div class="vt-nav" id="top">
            <a class="vt-nav-brand" href="#top"><span class="accent">$</span> {handle}.</a>
            <div class="vt-nav-links">{links_html}</div>
        </div>
        """
    )


def render_hero(profile: dict) -> None:
    name = profile.get("name", "")
    first_name = " ".join(name.split()[:2]) if name else ""
    avatar_uri = _avatar_data_uri()
    if avatar_uri:
        avatar_html = f'<img class="vt-avatar-img" src="{avatar_uri}" alt="{name}" />'
    else:
        avatar_html = f'<div class="vt-avatar-fallback">{_initials(name)}</div>'

    st.html(
        f"""
        <div class="vt-hero">
            {avatar_html}
            <div>
                <div class="vt-hero-name">Hey, I'm {first_name}</div>
                <div class="vt-hero-title">{profile.get("title", "")}</div>
            </div>
        </div>
        <div class="vt-hero-tagline mono">{profile.get("tagline", "")}</div>
        <div class="vt-hero-summary">{profile.get("summary", "")}</div>
        """
    )


def render_hero_visual() -> None:
    """A floating wireframe node-graph beside the hero text — an abstract
    stand-in for "systems / networks / knowledge". A sparse ambient dot
    field gives it atmosphere; a rotating node cluster (built from a
    Fibonacci-sphere point set, edged to its nearest neighbours) is the
    focal object. Each main node carries a small mono-font technology
    label (Java, Spring Boot, Kafka, RAG, ...) that tracks it every frame
    and anchors toward the cluster's center so it never runs off the edge
    of the canvas. Both layers brighten and draw new connections near the
    cursor, and the cluster keeps a slow autonomous rotate/bob/breathe even
    at rest. No card chrome — it draws straight onto the page background
    (see .st-key-vt_hero_visual, which has no border/fill of its own).
    Scales down on narrow viewports (shorter container + the `fit` factor
    below) rather than disappearing — Streamlit stacks the hero columns
    under it automatically, so it ends up below the CTA buttons on mobile.
    Labels are dropped below a `fit` threshold so the mobile graph stays
    clean rather than cluttered.
    """
    st.html(
        """
        <canvas id="vtGrid"></canvas>
        <script>
        (function () {
            const canvas = document.getElementById("vtGrid");
            if (!canvas || canvas.dataset.vtInit) return;
            canvas.dataset.vtInit = "1";

            const ctx = canvas.getContext("2d");
            const container = canvas.closest(".st-key-vt_hero_visual") || canvas.parentElement;
            const ACCENT = "183, 123, 232";
            const BASE = "242, 242, 242";

            let width = 0, height = 0;
            const dpr = Math.min(window.devicePixelRatio || 1, 2);

            // --- ambient background dots -----------------------------------
            const AMBIENT_SPACING = 96;
            const AMBIENT_RADIUS = 130;
            let ambient = [];

            function buildAmbient() {
                ambient = [];
                for (let y = AMBIENT_SPACING / 2; y < height; y += AMBIENT_SPACING) {
                    for (let x = AMBIENT_SPACING / 2; x < width; x += AMBIENT_SPACING) {
                        ambient.push({ x: x, y: y });
                    }
                }
            }

            // --- central node cluster (Fibonacci sphere) --------------------
            // One label per main node, so every point in the focal cluster
            // reads as a named technology — no unlabeled filler nodes mixed
            // in, and no icons (a single consistent glowing-point + label
            // visual language throughout).
            const TECH_LABELS = [
                "Java", "Spring Boot", "Microservices", "Kafka",
                "Angular", "PostgreSQL", "Redis", "RAG",
                "LangChain", "LangGraph", "GenAI", "pgvector"
            ];
            const NODE_COUNT = TECH_LABELS.length;
            const NODE_RADIUS_3D = 210;
            const NEIGHBOURS = 3;
            let nodes = [];
            const edgeKeys = new Set();
            let edges = [];

            function buildNodeGraph() {
                nodes = [];
                const golden = Math.PI * (3 - Math.sqrt(5));
                for (let i = 0; i < NODE_COUNT; i++) {
                    const yv = 1 - (i / (NODE_COUNT - 1)) * 2;
                    const r = Math.sqrt(Math.max(0, 1 - yv * yv));
                    const theta = golden * i;
                    nodes.push({
                        bx: Math.cos(theta) * r * NODE_RADIUS_3D,
                        by: yv * NODE_RADIUS_3D,
                        bz: Math.sin(theta) * r * NODE_RADIUS_3D,
                        label: TECH_LABELS[i]
                    });
                }
                edges = [];
                edgeKeys.clear();
                for (let i = 0; i < nodes.length; i++) {
                    const dists = [];
                    for (let j = 0; j < nodes.length; j++) {
                        if (i === j) continue;
                        const dx = nodes[i].bx - nodes[j].bx;
                        const dy = nodes[i].by - nodes[j].by;
                        const dz = nodes[i].bz - nodes[j].bz;
                        dists.push([j, dx * dx + dy * dy + dz * dz]);
                    }
                    dists.sort(function (a, b) { return a[1] - b[1]; });
                    for (let k = 0; k < NEIGHBOURS; k++) {
                        const j = dists[k][0];
                        const key = i < j ? i + "_" + j : j + "_" + i;
                        if (!edgeKeys.has(key)) {
                            edgeKeys.add(key);
                            edges.push([i, j]);
                        }
                    }
                }
            }
            buildNodeGraph();

            // Node radius/focal length are tuned for the desktop canvas
            // size; on smaller viewports (the graph now scales down rather
            // than disappearing) everything shrinks together via this
            // factor instead of clipping against the canvas edge.
            let fit = 1;

            function resize() {
                width = container.clientWidth;
                height = container.clientHeight;
                canvas.width = width * dpr;
                canvas.height = height * dpr;
                canvas.style.width = width + "px";
                canvas.style.height = height + "px";
                ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
                buildAmbient();
                fit = Math.max(0.42, Math.min(1, Math.min(width, height) / 560));
            }

            let mouse = { x: -9999, y: -9999 };
            let raf = null;

            function draw(t) {
                ctx.clearRect(0, 0, width, height);

                // ambient field: quiet, brightens slightly near the cursor
                for (let i = 0; i < ambient.length; i++) {
                    const d = ambient[i];
                    const dx = d.x - mouse.x, dy = d.y - mouse.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    const near = Math.max(0, 1 - dist / (AMBIENT_RADIUS * fit));
                    const color = near > 0.06 ? ACCENT : BASE;
                    ctx.beginPath();
                    ctx.arc(d.x, d.y, (0.8 + near * 1.0) * Math.max(0.6, fit), 0, Math.PI * 2);
                    ctx.fillStyle = "rgba(" + color + ", " + (0.035 + near * 0.3) + ")";
                    ctx.fill();
                }

                // slow autonomous motion: rotation, tilt, breathing, bob
                const angle = t * 0.00016;
                const tilt = 0.2 + Math.sin(t * 0.00035) * 0.18;
                const breathe = 1 + Math.sin(t * 0.0004) * 0.035;
                const bob = Math.sin(t * 0.0006) * 10;
                const cosA = Math.cos(angle), sinA = Math.sin(angle);
                const cosT = Math.cos(tilt), sinT = Math.sin(tilt);

                // centred in its column (the column itself is already the
                // hero's right side) so the larger object has even margin
                // on both sides and doesn't clip against the canvas edge
                const centerX = width * 0.5;
                const centerY = height * 0.5 + bob;
                const FOCAL = 780;

                const projected = nodes.map(function (n) {
                    let x = n.bx * cosA - n.bz * sinA;
                    let z = n.bx * sinA + n.bz * cosA;
                    let y = n.by * cosT - z * sinT;
                    z = n.by * sinT + z * cosT;
                    x *= breathe; y *= breathe; z *= breathe;
                    const scale = FOCAL / (FOCAL + z);
                    const sx = centerX + x * scale * fit;
                    const sy = centerY + y * scale * fit;
                    const dx = sx - mouse.x, dy = sy - mouse.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    const near = Math.max(0, 1 - dist / (320 * fit));
                    // restrained pull toward the cursor, never a scatter
                    const pull = near * 19 * fit;
                    return {
                        x: sx - (dx / dist) * pull,
                        y: sy - (dy / dist) * pull,
                        scale: scale,
                        near: near,
                        label: n.label
                    };
                });

                // skeleton edges: always faintly present, brighten near cursor
                for (let i = 0; i < edges.length; i++) {
                    const a = projected[edges[i][0]], b = projected[edges[i][1]];
                    const near = Math.max(a.near, b.near);
                    const color = near > 0.08 ? ACCENT : BASE;
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(b.x, b.y);
                    ctx.strokeStyle = "rgba(" + color + ", " + (0.32 + near * 0.5) + ")";
                    ctx.lineWidth = (near > 0.08 ? 1.4 : 0.9) * Math.max(0.6, fit);
                    ctx.stroke();
                }

                // opportunistic links: nodes that drift close together as the
                // cluster rotates connect briefly — a living structure even
                // when the cursor isn't near it
                for (let i = 0; i < projected.length; i++) {
                    for (let j = i + 1; j < projected.length; j++) {
                        const key = i < j ? i + "_" + j : j + "_" + i;
                        if (edgeKeys.has(key)) continue;
                        const dx = projected[i].x - projected[j].x;
                        const dy = projected[i].y - projected[j].y;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        if (dist < 90 * fit) {
                            const near = Math.max(projected[i].near, projected[j].near);
                            ctx.beginPath();
                            ctx.moveTo(projected[i].x, projected[i].y);
                            ctx.lineTo(projected[j].x, projected[j].y);
                            ctx.strokeStyle = "rgba(" + ACCENT + ", " + (0.05 + near * 0.3) + ")";
                            ctx.lineWidth = 0.7 * Math.max(0.6, fit);
                            ctx.stroke();
                        }
                    }
                }

                // nodes: closer to camera (bigger scale) reads brighter/larger.
                // Ones the cursor is near get a soft accent glow — the one
                // spot glow is allowed to show, kept tight to the node itself
                // rather than a wash over the whole structure.
                // Technology labels ride along beside each node. Dropped
                // below a fit threshold (small/mobile canvases) so the graph
                // stays clean rather than cluttered, per the "large + smooth
                // over labels" fallback.
                const showLabels = fit > 0.55;
                const labelCandidates = [];
                for (let i = 0; i < projected.length; i++) {
                    const p = projected[i];
                    const depth = Math.max(0, Math.min(1, (p.scale - 0.75) / 0.5));
                    const color = p.near > 0.08 ? ACCENT : BASE;
                    const nodeR = (2.5 + depth * 1.6 + p.near * 3.0) * Math.max(0.55, fit);
                    if (p.near > 0.15) {
                        ctx.shadowColor = "rgba(" + ACCENT + ", " + Math.min(0.85, p.near) + ")";
                        ctx.shadowBlur = 16 * p.near;
                    }
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, nodeR, 0, Math.PI * 2);
                    ctx.fillStyle = "rgba(" + color + ", " + Math.min(1, 0.6 + depth * 0.35 + p.near * 0.4) + ")";
                    ctx.fill();
                    ctx.shadowBlur = 0;

                    // label anchors toward the cluster's own center rather
                    // than outward, so it reads inward on both sides of the
                    // sphere and never runs off the canvas edge
                    if (showLabels && p.label) {
                        const anchorLeft = p.x > centerX;
                        const offset = nodeR + 7 * fit;
                        const fontSize = 10 * Math.max(0.65, fit);
                        const textW = p.label.length * fontSize * 0.62;
                        const lx = p.x + (anchorLeft ? -offset : offset);
                        const boxLeft = anchorLeft ? lx - textW : lx;
                        labelCandidates.push({
                            text: p.label, x: lx, y: p.y,
                            align: anchorLeft ? "right" : "left",
                            color: color,
                            alpha: Math.min(0.9, 0.28 + depth * 0.18 + p.near * 0.4),
                            fontSize: fontSize,
                            prominence: depth + p.near * 2,
                            box: { left: boxLeft, right: boxLeft + textW, top: p.y - fontSize * 0.65, bottom: p.y + fontSize * 0.65 }
                        });
                    }
                }

                // Labels are drawn most-prominent-first with simple box
                // collision suppression, so two nodes that briefly rotate
                // close together never render overlapping text — the
                // less-prominent one just sits out that frame.
                if (showLabels) {
                    labelCandidates.sort(function (a, b) { return b.prominence - a.prominence; });
                    ctx.textBaseline = "middle";
                    const placed = [];
                    for (let i = 0; i < labelCandidates.length; i++) {
                        const c = labelCandidates[i];
                        let overlaps = false;
                        for (let j = 0; j < placed.length; j++) {
                            const b = placed[j];
                            if (c.box.left < b.right + 6 && c.box.right > b.left - 6 &&
                                c.box.top < b.bottom + 3 && c.box.bottom > b.top - 3) {
                                overlaps = true;
                                break;
                            }
                        }
                        if (overlaps) continue;
                        ctx.font = c.fontSize.toFixed(1) + "px 'JetBrains Mono', monospace";
                        ctx.textAlign = c.align;
                        ctx.fillStyle = "rgba(" + c.color + ", " + c.alpha + ")";
                        ctx.fillText(c.text, c.x, c.y);
                        placed.push(c.box);
                    }
                }

                raf = requestAnimationFrame(draw);
            }

            canvas.addEventListener("mousemove", function (e) {
                const rect = canvas.getBoundingClientRect();
                mouse.x = e.clientX - rect.left;
                mouse.y = e.clientY - rect.top;
            });
            canvas.addEventListener("mouseleave", function () {
                mouse.x = -9999;
                mouse.y = -9999;
            });

            new ResizeObserver(resize).observe(container);
            resize();

            new IntersectionObserver(function (entries) {
                const visible = entries[0].isIntersecting;
                if (visible && !raf) raf = requestAnimationFrame(draw);
                if (!visible && raf) { cancelAnimationFrame(raf); raf = null; }
            }).observe(canvas);
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def render_section_title(label: str, anchor_id: str | None = None) -> None:
    anchor_html = f'<div class="vt-section-anchor" id="{anchor_id}"></div>' if anchor_id else ""
    st.html(
        f"""
        {anchor_html}
        <div class="vt-section-title mono"><span class="accent">$</span> {label}</div>
        """
    )


def render_skills(categories: dict[str, list[str]]) -> None:
    columns_html = ""
    for category, skills in categories.items():
        items_html = "".join(
            f'<span class="vt-skill-chip">{skill}</span>' for skill in skills
        )
        columns_html += (
            f'<div class="vt-skill-card"><div class="vt-skill-cat-label mono">{category}</div>'
            f'<div class="vt-skill-items">{items_html}</div></div>'
        )
    st.html(f'<div class="vt-skills">{columns_html}</div>')


def _experience_highlight_html(item: dict) -> str:
    contributions = "".join(f"<li>{c}</li>" for c in item.get("contributions", []))
    impact_html = (
        f'<div class="vt-exp-hl-impact"><span class="mono accent">Impact →</span> {item["impact"]}</div>'
        if item.get("impact")
        else ""
    )
    return f"""
        <div class="vt-exp-hl">
            <div class="vt-exp-hl-title">{item.get("title", "")}</div>
            <div class="vt-exp-hl-problem"><span class="vt-exp-hl-label">Problem</span> {item.get("problem", "")}</div>
            <div class="vt-exp-hl-stack mono">{item.get("stack", "")}</div>
            <ul class="vt-exp-hl-list">{contributions}</ul>
            {impact_html}
        </div>
        """


def render_experience(experience: dict) -> None:
    if not experience:
        return
    company = experience.get("company", "")
    role = experience.get("role", "")
    heading = f"{company} · {role}" if company and role else (company or role)
    overview_html = (
        f'<div class="vt-exp-overview">{experience["overview"]}</div>'
        if experience.get("overview")
        else ""
    )
    highlights_html = "".join(
        _experience_highlight_html(item) for item in experience.get("highlights", [])
    )
    st.html(
        f"""
        <div class="vt-exp">
            <div class="vt-exp-role">{heading}</div>
            <div class="vt-exp-period mono">{experience.get("period", "")}</div>
            <div class="vt-exp-company">{experience.get("product", "")}</div>
            {overview_html}
            <div class="vt-exp-highlights">{highlights_html}</div>
        </div>
        """
    )


def _project_card_html(index: int, project: dict) -> str:
    tech = " · ".join(project.get("technologies", []))
    num = f"{index:02d}"
    github_link = (
        f'<a class="vt-project-link" href="{project["github_url"]}" '
        f'target="_blank" rel="noopener noreferrer">GitHub →</a>'
        if project.get("github_url")
        else ""
    )
    return f"""
        <div class="vt-project">
            <div class="vt-project-head">
                <span class="vt-project-num mono">{num}</span>
                <span class="vt-project-title">{project.get("name", "")}</span>
            </div>
            <div class="vt-project-category">{project.get("category", "")}</div>
            <div class="vt-project-desc">{project.get("description", "")}</div>
            {f'<div class="vt-project-result">{project["result"]}</div>' if project.get("result") else ""}
            <div class="vt-project-tech mono">{tech}</div>
            {github_link}
        </div>
        """


def render_projects_grid(projects: list[dict]) -> None:
    cards = "".join(_project_card_html(i, project) for i, project in enumerate(projects, start=1))
    st.html(f'<div class="vt-projects-grid">{cards}</div>')


_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}[ \t]+.*$\n?", re.MULTILINE)


def _strip_markdown_headings(text: str) -> str:
    """Drops ATX headings (# through ######) from a knowledge chunk before
    display. The expander's own label (source + score) already gives
    context, so a section heading repeated inside the body is just noise —
    chunk overlap often carries one into several consecutive chunks.
    """
    return _MARKDOWN_HEADING_RE.sub("", text).strip()


def render_retrieved_sources(chunks: list[dict], key_prefix: str) -> None:
    """Transparency panel under an assistant answer: which knowledge-base
    documents and chunks grounded it, and how each chunk scored against the
    question (0-1, higher = more relevant). ``key_prefix`` must be unique
    per rendered answer (e.g. the message index) so repeated calls across
    the chat history don't collide on widget identity.
    """
    if not chunks:
        return

    unique_sources = sorted({chunk.get("source", "unknown") for chunk in chunks})
    with st.expander(f"📄 Sources ({len(unique_sources)})", key=f"{key_prefix}_sources"):
        for name in unique_sources:
            st.markdown(f"- `{name}`")
        st.markdown("**Retrieved chunks:**")

        # st.popover, not st.expander -- Streamlit doesn't allow nesting one
        # expander inside another, but a popover nests fine and gives the
        # same "click to see details" interaction, all kept under the one
        # Sources dropdown instead of spilling out as top-level rows.
        for i, chunk in enumerate(chunks):
            score = chunk.get("score")
            score_label = f"{score:.3f}" if isinstance(score, (int, float)) else "n/a"
            source = chunk.get("source", "unknown")
            with st.popover(
                f"{source}  (score: {score_label})",
                use_container_width=True,
                key=f"{key_prefix}_chunk_{i}",
            ):
                st.markdown(_strip_markdown_headings(chunk.get("content", "")))


@st.dialog("Contact")
def _render_contact_dialog(contact: dict) -> None:
    has_any = False
    if contact.get("email"):
        has_any = True
        st.markdown(f"**Email** — [{contact['email']}](mailto:{contact['email']})")
    if contact.get("linkedin"):
        has_any = True
        st.markdown(f"**LinkedIn** — [{contact['linkedin']}]({contact['linkedin']})")
    if contact.get("github"):
        has_any = True
        st.markdown(f"**GitHub** — [{contact['github']}]({contact['github']})")
    if not has_any:
        st.caption("No contact details configured yet.")


def render_chat_sidebar(profile: dict) -> None:
    """Sidebar for the standalone AI assistant page: conversation controls
    plus a way to reach the owner. Pinned permanently open -- its own
    collapse button is hidden (see .st-key-vt_side_panel's sibling rule,
    [data-testid="stSidebarCollapseButton"], in theme.py) so there's no
    open/close state to get stuck in.
    """
    name = profile.get("name", "AI Assistant")
    contact = profile.get("contact", {})

    with st.sidebar:
        st.html(f'<div class="vt-side-panel-title mono"><span class="accent">$</span> {name}</div>')
        st.caption("Personal AI Assistant")
        st.divider()

        if st.button("Clear current conversation", use_container_width=True, key="vt_side_clear_chat"):
            st.session_state.messages = []
            st.rerun()

        if st.button("✉️ Contact", use_container_width=True, key="vt_side_contact"):
            _render_contact_dialog(contact)

        portfolio_url = contact.get("portfolio")
        if portfolio_url:
            st.link_button("🔗 Portfolio", portfolio_url, use_container_width=True, key="vt_side_portfolio")


def render_footer() -> None:
    st.html(
        """
        <div class="vt-footer">
            <span class="vt-footer-credit">Built with Streamlit · LangGraph · RAG</span>
            <a class="vt-footer-credit" href="/admin">Owner</a>
        </div>
        """
    )
