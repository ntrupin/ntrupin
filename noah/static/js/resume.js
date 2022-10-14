const projects = document.querySelectorAll("#projects > div");

const showAll = () => {
    projects.forEach(p => {
        p.classList.remove("d-none");
    });
}

const hideNonResume = () => {
    projects.forEach(p => {
        if (p.getAttribute("data-resume") != "True") {
            p.classList.add("d-none");
        }
    });
}

document.querySelectorAll('input[name="projectRadio"]').forEach(el => {
    el.addEventListener("click", e => {
        if (e.target.getAttribute("id") == "allRadio") {
            showAll();
        } else {
            hideNonResume();
        }
    });
});