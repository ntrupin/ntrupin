const content = document.querySelector("textarea#content");

// set height of textarea
const setHeight = () => {
  content.style.height = content.scrollHeight + 3 + "px";
}

// call on load
setHeight();
