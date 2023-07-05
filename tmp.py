import markdown

with open("./noah/static/files/index.md", "r") as f:
    print(markdown.markdown(f.read()))