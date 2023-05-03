const projects = document.querySelectorAll("#projects > div");

const showAll = () => {
    projects.forEach(p => {
        p.classList.remove("d-none");
    });
}

const hideNon = (tag) => {
    showAll();
    projects.forEach(p => {
        if (p.getAttribute(`data-${tag}`) != "True") {
            p.classList.add("d-none");
        }
    });
}

const hide = (tag) => {
    showAll();
    projects.forEach(p => {
        if (p.getAttribute(`data-${tag}`) == "True") {
            p.classList.add("d-none");
        }
    });
}

document.querySelectorAll('input[name="projectRadio"]').forEach(el => {
    el.addEventListener("click", e => {
        if (e.target.getAttribute("id") == "allRadio") {
            showAll();
        } else if (e.target.getAttribute("id") == "defaultRadio") {
            hide("archived");
        } else if (e.target.getAttribute("id") == "favoriteRadio") {
            hideNon("favorite");
        } else if (e.target.getAttribute("id") == "resumeRadio") {
            hideNon("resume");
        } else if (e.target.getAttribute("id") == "archivedRadio") {
            hideNon("archived");
        }
    });
});