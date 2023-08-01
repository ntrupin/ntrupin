import markdown
from os import listdir, path

if __name__ == "__main__":
    for f in listdir("./noah/pages"):
        name = path.splitext(f)[0]
        with open(f"./noah/pages/{f}", "r") as i, open(f"./noah/templates/{name}.html", "w") as o:
            o.write(f"""{{% extends "base.html" %}}

{{% block title %}}Noah Trupin{' | ' + name.capitalize() if name != 'index' else ''}{{% endblock %}}

{{% block content %}} 
{markdown.markdown(i.read())}
{{% endblock %}}           
            """)
