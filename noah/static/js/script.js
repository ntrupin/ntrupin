hljs.highlightAll();

const colors = [
    "--bs-green", "--bs-blue", "--bs-red", "--bs-purple", "--bs-pink"
];
document.querySelector("#randomColor").addEventListener("click", (e) => {
    document.documentElement.style = `--root-color: var(${colors[Math.floor(Math.random()*colors.length)]});`;
});