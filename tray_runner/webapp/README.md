# VueJS 3 + Cognito

```bash
terraform init
```

Show credentials for the user created, needed to access the web application:

```bash
terraform output
```

Launch and access the application at <http://127.0.0.1:8000>:

```bash
python3 -m http.server -d webapp
```

While development, you can use [livereload](https://github.com/lepture/python-livereload) for live reload on changes:

```bash
pipx install livereload
livereload --port 8000 webapp
```
