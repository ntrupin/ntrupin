const progress = document.querySelector("#page_progress");

const setProgress = () => {
  let h = document.documentElement, 
      b = document.body,
      st = 'scrollTop',
      sh = 'scrollHeight';
  let percent = (h[st]||b[st]) / ((h[sh]||b[sh]) - h.clientHeight) * 100;
  progress.value = Math.round(percent);
}

document.addEventListener("scroll", (e) => setProgress());

setProgress();
