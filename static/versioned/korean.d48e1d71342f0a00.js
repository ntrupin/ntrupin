document.querySelectorAll("form[data-busy], form[data-confirm]").forEach((form) => {
  const button = form.querySelector('button[type="submit"]');
  const label = button.textContent;
  form.addEventListener("submit", (event) => {
    if (button.disabled || (form.dataset.confirm && !window.confirm(form.dataset.confirm))) {
      event.preventDefault();
      return;
    }
    if (form.dataset.busy) {
      button.textContent = form.dataset.busy;
      button.disabled = true;
    }
  });
  window.addEventListener("pageshow", () => {
    button.textContent = label;
    button.disabled = false;
  });
});

const passageInput = document.querySelector("[data-passage-limit]");

if (passageInput) {
  const limit = Number(passageInput.dataset.passageLimit);
  let pastedText = passageInput.dataset.original ? JSON.parse(passageInput.dataset.original) : null;

  function originalText() {
    return pastedText?.replace(/\r\n?/g, "\n") === passageInput.value ? pastedText : passageInput.value;
  }

  passageInput.addEventListener("paste", (event) => {
    if (passageInput.selectionStart === 0 && passageInput.selectionEnd === passageInput.value.length) {
      pastedText = event.clipboardData?.getData("text/plain");
    }
  });
  passageInput.addEventListener("input", () => {
    passageInput.setCustomValidity(Array.from(originalText()).length > limit
      ? `Use a passage of at most ${limit} characters.`
      : "");
  });
  passageInput.form.addEventListener("formdata", (event) => {
    // Forms normalize line endings. Encode the editor value before submission.
    event.formData.delete(passageInput.name);
    event.formData.set("text_json", JSON.stringify(originalText()));
  });
}

const readerData = document.getElementById("reader-data");

if (readerData) {
  const { annotations, concepts, csrf, knowledgeUrl } = JSON.parse(readerData.textContent);
  const spans = Array.from(document.querySelectorAll("[data-annotations]"), (element) => ({
    element,
    ids: element.dataset.annotations.split(",").map(Number),
  }));
  const tooltip = document.getElementById("reader-tooltip");
  const dialog = document.getElementById("reader-inspection");
  const details = document.getElementById("inspection-details");
  const status = document.getElementById("inspection-status");
  const conceptList = document.getElementById("inspection-concepts");
  const related = document.getElementById("inspection-related");
  const closeButton = dialog.querySelector('button[aria-label="Close explanation"]');
  let activeSpan;
  let activeId;
  let updating = false;

  function isUnknown(id) {
    return annotations[id].concept_ids.some((conceptId) => concepts[conceptId]?.recognition === "learning");
  }

  function ranked(ids) {
    return [...ids].sort((a, b) => {
      const aLength = annotations[a].end - annotations[a].start;
      const bLength = annotations[b].end - annotations[b].start;
      return Number(isUnknown(b)) - Number(isUnknown(a)) || aLength - bLength || a - b;
    });
  }

  function hideTooltip() {
    tooltip.hidden = true;
    tooltip.owner?.removeAttribute("aria-describedby");
    tooltip.owner = null;
  }

  function showTooltip(span, event) {
    if (dialog.open) return;
    hideTooltip();
    tooltip.textContent = annotations[ranked(span.ids)[0]].gloss;
    tooltip.hidden = false;
    tooltip.owner = span.element;
    span.element.setAttribute("aria-describedby", tooltip.id);
    const rect = span.element.getBoundingClientRect();
    const x = event.clientX ?? rect.left;
    const y = event.clientY ?? rect.bottom;
    const left = Math.max(8, Math.min(x, window.innerWidth - tooltip.offsetWidth - 8));
    const top = y + tooltip.offsetHeight + 18 < window.innerHeight
      ? y + 18
      : Math.max(8, y - tooltip.offsetHeight - 15);
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  }

  function stateLabel(concept) {
    return concept.recognition === "known" ? "Mark learning" : "Mark known";
  }

  async function updateKnowledge(concept, button) {
    if (updating) return;
    updating = true;
    status.textContent = "";
    status.classList.remove("reader-message");
    button.setAttribute("aria-disabled", "true");
    const recognition = concept.recognition === "known" ? "learning" : "known";
    try {
      const url = knowledgeUrl.replace("00000000-0000-0000-0000-000000000000", concept.id);
      const response = await fetch(url, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ recognition }),
      });
      if (response.redirected) {
        location.assign(location.href);
        return;
      }
      if (!response.ok) throw new Error("Request failed");
      concept.recognition = (await response.json()).recognition;
      button.textContent = stateLabel(concept);
      button.setAttribute("aria-label", `${button.textContent}: ${concept.form}`);
      spans.forEach((span) => span.element.classList.toggle("is-unknown", span.ids.some(isUnknown)));
      status.textContent = recognition === "known" ? "Marked known." : "Marked learning.";
    } catch {
      status.textContent = "Could not save that change. Please try again.";
      status.classList.add("reader-message");
    } finally {
      updating = false;
      button.removeAttribute("aria-disabled");
    }
  }

  function showAnnotation(id, expanded) {
    activeId = id;
    const annotation = annotations[id];
    document.getElementById("inspection-surface").textContent = annotation.surface;
    document.getElementById("inspection-gloss").textContent = annotation.gloss;
    document.getElementById("inspection-breakdown").textContent = annotation.breakdown;
    document.getElementById("inspection-explanation").textContent = annotation.explanation;
    status.textContent = "";
    details.open = expanded;
    conceptList.replaceChildren();

    annotation.concept_ids.forEach((conceptId) => {
      const concept = concepts[conceptId];
      if (!concept) return;
      const item = document.createElement("li");
      const label = document.createElement("span");
      const form = document.createElement("strong");
      const button = document.createElement("button");
      form.lang = "ko";
      form.textContent = concept.form;
      label.append(form, ` · ${concept.meaning}`);
      button.type = "button";
      button.className = "text-button";
      button.textContent = stateLabel(concept);
      button.setAttribute("aria-label", `${button.textContent}: ${concept.form}`);
      button.addEventListener("click", () => updateKnowledge(concept, button));
      item.append(label, button);
      conceptList.append(item);
    });

    related.replaceChildren();
    ranked(activeSpan.ids).filter((other) => other !== activeId).slice(0, 4).forEach((other) => {
      const button = document.createElement("button");
      const surface = document.createElement("span");
      surface.lang = "ko";
      surface.textContent = annotations[other].surface;
      button.type = "button";
      button.append(surface, ` · ${annotations[other].gloss}`);
      button.addEventListener("click", () => {
        if (updating) return;
        showAnnotation(other, details.open);
        document.getElementById("inspection-surface").focus();
      });
      related.append(button);
    });
    related.hidden = !related.childElementCount;
  }

  function openInspection(span, expanded) {
    hideTooltip();
    activeSpan = span;
    showAnnotation(ranked(span.ids)[0], expanded);
    dialog.showModal();
    closeButton.focus();
  }

  spans.forEach((span) => {
    span.element.addEventListener("pointerenter", (event) => {
      if (event.pointerType !== "touch") showTooltip(span, event);
    });
    span.element.addEventListener("pointerleave", hideTooltip);
    span.element.addEventListener("focus", (event) => showTooltip(span, event));
    span.element.addEventListener("blur", hideTooltip);
    span.element.addEventListener("click", (event) => {
      if (getSelection()?.type === "Range") return;
      openInspection(span, event.pointerType !== "touch" && !matchMedia("(pointer: coarse)").matches);
    });
    span.element.addEventListener("keydown", (event) => {
      if (event.key === "Escape") hideTooltip();
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openInspection(span, true);
      }
    });
  });
  dialog.addEventListener("close", () => {
    activeSpan?.element.focus();
    hideTooltip();
  });
  window.addEventListener("scroll", hideTooltip, { passive: true });
  window.addEventListener("resize", hideTooltip);
}
