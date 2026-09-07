window.va = window.va || function () {
  (window.vaq = window.vaq || []).push(arguments);
};

document.addEventListener("submit", (event) => {
  const message = event.submitter?.dataset.confirm;
  if (message && !window.confirm(message)) event.preventDefault();
});
