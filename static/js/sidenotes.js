const createSidenote = (content) => {
  const sn = document.createElement("span");
  sn.classList.add(
    "sidenote",
    "ml-2",
    "text-sm",
    "text-gray-600",
    "lg:w-[12rem]",
    "lg:translate-y-[0.1rem]",
    "lg:absolute",
    "lg:left-[calc(50vw+18rem+1.5rem)]",
  );
  sn.innerHTML = content;
  return sn;
};

const calculateOverlap = (a, b) => {
  const A = a.getBoundingClientRect();
  const B = b.getBoundingClientRect();

  const overlapY = Math.max(0, Math.min(A.bottom, B.bottom) - Math.max(A.top, B.top));

  if (overlapY === 0) return 0;

  const Acy = (A.top + A.bottom) / 2;
  const Bcy = (B.top + B.bottom) / 2;

  const minSeparationY = (Bcy < Acy ? 1 : -1) * overlapY * 2 + 20;
  return minSeparationY;
}

(() => {
  document.querySelector("div.footnote").classList.add("hidden");
  
  const fns = document.querySelector("div.footnote > ol");
  if (!fns) return;

  let i = 1;
  let prevSn = null;
  for (const child of fns.children) {
    let id = child.getAttribute("id");
    if (!id) continue;
    id = id.replace("fn", "fnref");
    id = id.replace(":", "\\:");

    const ref = document.querySelector(`sup#${id}`);
    if (!ref) continue;

    const sn = createSidenote(child.innerHTML);
    ref.parentNode.insertBefore(sn, ref.nextSibling);

    if (i > 1 && calculateOverlap(sn, sn.previousSiblings) !== 0) {
      sn.previousSiblings.innerHTML += sn.innerHTML;
      sn.remove();
    }

    i += 1;
  }
})();
