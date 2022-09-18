const ref = document.querySelector("#ref-el");

document.querySelectorAll("[id$='-remove']").forEach((el) => {
    el.addEventListener("click", (e) => {
        const name = e.target.id.split("-")[0];
        document.querySelector(`#${name}-group`)
            .lastChild
            .remove();
    });
});

document.querySelectorAll("[id$='-add']").forEach((el) => {
    el.addEventListener("click", (e) => {
        const name = e.target.id.split("-")[0];
        let group = document.querySelector(`#${name}-group`);
        let child = ref.cloneNode(true);
        child.id = "";
        child.name = `${name}[]`;
        child.classList.remove("d-none");
        group.appendChild(child);
    });
});