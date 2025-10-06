const createSidenote = (content) => {
  const sn = document.createElement("span");
  sn.classList.add(
    "sidenote",
    "ml-2",
    "text-sm",
    "text-gray-600",
    "lg:w-[10rem]",
    "lg:translate-y-[0.1rem]",
    "lg:absolute",
    "lg:left-[calc(50vw+18rem+1.5rem)]",
  );
  sn.innerHTML = content;
  return sn;
};

(() => {
  document.querySelector("div.footnote").classList.add("hidden");
  
  const fns = document.querySelector("div.footnote > ol");
  if (!fns) return;

  let i = 1;
  for (const child of fns.children) {
    let id = child.getAttribute("id");
    if (!id) continue;
    id = id.replace("fn", "fnref");
    id = id.replace(":", "\\:");

    const ref = document.querySelector(`sup#${id}`);
    if (!ref) continue;

    const sn = createSidenote(child.innerHTML);
    ref.parentNode.insertBefore(sn, ref.nextSibling);

    i += 1;
  }
})();
