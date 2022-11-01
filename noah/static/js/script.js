hljs.highlightAll();

const colors = [
    "--bs-green", "--bs-blue", "--bs-red", "--bs-purple", "--bs-cyan", "--bs-orange"
];
window.addEventListener("DOMContentLoaded", (_) => {
    const d = localStorage.getItem("color");
    if (d) {
        document.documentElement.style = `--root-color: var(${d});`;
    }
    document.querySelector("#randomColor").addEventListener("click", (_) => {
        let ds = document.documentElement.getAttribute("style") ?? "";
        const color = ds.replace(/(\-\-root\-color\: var\(|\)\;)/g, "");
        const set = colors.filter(c => c != color);
        const nc = set[Math.floor(Math.random()*set.length)];
        document.documentElement.style = `--root-color: var(${nc});`;
        localStorage.setItem("color", nc);
    });
});