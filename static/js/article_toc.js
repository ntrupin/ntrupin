(() => {
  const root = document.querySelector("[data-toc-root]");
  if (!root) return;

  const article = root.querySelector("[data-article-body]");
  const tocColumn = root.querySelector("[data-toc-column]");
  if (!article || !tocColumn) return;

  const headings = Array.from(article.querySelectorAll("h2, h3, h4"));
  if (headings.length === 0) {
    tocColumn.hidden = true;
    return;
  }

  const slugCounts = new Map();

  const slugify = (value) => {
    const normalized = value
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9\s-]/g, "")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-");
    return normalized || "section";
  };

  for (const heading of headings) {
    if (heading.id) continue;
    const base = slugify(heading.textContent || "");
    const count = slugCounts.get(base) || 0;
    slugCounts.set(base, count + 1);
    heading.id = count === 0 ? base : `${base}-${count + 1}`;
  }

  const title = document.createElement("p");
  title.className = "toc-title";
  title.textContent = "On this page";

  const list = document.createElement("ol");
  list.className = "toc-list";

  const linkMap = new Map();
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  for (const heading of headings) {
    const item = document.createElement("li");
    item.className = "toc-item";
    item.dataset.level = heading.tagName.toLowerCase();

    const link = document.createElement("a");
    link.href = `#${heading.id}`;
    link.className = "toc-link";
    link.textContent = heading.textContent || heading.id;
    link.addEventListener("click", (event) => {
      event.preventDefault();
      heading.scrollIntoView({
        behavior: prefersReducedMotion ? "auto" : "smooth",
        block: "start",
      });
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", `#${heading.id}`);
      }
      setActive(heading);
    });

    item.appendChild(link);
    list.appendChild(item);
    linkMap.set(heading, link);
  }

  const stick = document.createElement("div");
  stick.className = "toc-stick";
  stick.appendChild(title);
  stick.appendChild(list);
  tocColumn.appendChild(stick);

  const setActive = (heading) => {
    for (const link of linkMap.values()) {
      link.dataset.active = "false";
    }
    const activeLink = linkMap.get(heading);
    if (activeLink) activeLink.dataset.active = "true";
  };

  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visible.length > 0) {
        setActive(visible[0].target);
      }
    },
    {
      rootMargin: "0px 0px -70% 0px",
      threshold: [0, 1],
    },
  );

  for (const heading of headings) {
    observer.observe(heading);
  }

  setActive(headings[0]);
})();
