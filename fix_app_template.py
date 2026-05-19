import os

app_file = "/Users/siyang/flask_auth_app/app.py"
with open(app_file, "r") as f:
    content = f.read()

content = content.replace('render_template("users.html"', 'render_template("users_list.html"')

with open(app_file, "w") as f:
    f.write(content)
