hljs.highlightAll();

const colors = [
    "--bs-green", "--bs-blue", "--bs-red", "--bs-purple", "--bs-cyan", "--bs-orange"
];
document.querySelector("#randomColor").addEventListener("click", (e) => {
    let ds = document.documentElement.getAttribute("style") ?? "";
    const color = (ds.match(/(?<=\-\-root\-color\: var\().+?(?=\)\;)/g) ?? [""])[0];
    const set = colors.filter(c => c != color);
    document.documentElement.style = `--root-color: var(${set[Math.floor(Math.random()*set.length)]});`;
});